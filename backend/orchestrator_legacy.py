"""
Enterprise Autopilot — Multi-Agent Orchestrator (Graph-Based).
Uses Strands GraphBuilder for deterministic, streaming multi-agent orchestration.

The workflow execution graph per step:

    ExecutionNode → VerificationNode ─(VERIFIED)──→ Done
                                      └─(FAILED)──→ RecoveryNode ─(RETRY)──→ [next iteration]
                                                                  └─(ESCALATE)→ Done

PlannerAgent runs outside the graph to generate the step list first.
"""
import asyncio
import json
import os
import sys
import traceback
import uuid
from dotenv import load_dotenv

from strands import Agent
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient
from strands.multiagent.graph import GraphBuilder
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

from state_manager import (
    update_workflow, get_workflow,
    append_audit_log, append_stream_event,
)

load_dotenv()

# ── Prisma Schema context ──
PRISMA_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "prisma", "schema.prisma")
try:
    with open(PRISMA_SCHEMA_PATH, "r") as f:
        PRISMA_SCHEMA = f.read()
except Exception:
    PRISMA_SCHEMA = "Prisma schema not found."


def _get_model():
    """Create OpenAI-compatible model from env."""
    return OpenAIModel(
        client_args={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4.1-nano"),
    )


# ══════════════════════════════════════════════════
# HELPER: Stream event writer
# ══════════════════════════════════════════════════

def _emit(workflow_id: str, event_type: str, agent_name: str, message: str, data: dict = None):
    """Write an SSE event to the stream file."""
    event = {
        "type": event_type,
        "workflowId": workflow_id,
        "agentName": agent_name,
        "message": message,
    }
    if data:
        event["data"] = data
    append_stream_event(workflow_id, event)


# ══════════════════════════════════════════════════
# PLANNER AGENT (runs before the graph)
# ══════════════════════════════════════════════════

def run_planner(intent: str, workflow_id: str) -> list[dict] | None:
    """Use PlannerAgent to generate workflow steps from user intent."""
    _emit(workflow_id, "chat:agent_assigned", "PlannerAgent", "📋 Planning workflow steps...")

    model = _get_model()
    planner = Agent(
        model=model,
        name="PlannerAgent",
        system_prompt=f"""You are the Planner Agent for an enterprise automation system.
Given a high-level goal, break it into concrete, actionable steps.

Available MCP tools:
- execute_sql: Run PostgreSQL queries
- send_email: Send emails
- create_email_account: Provision email accounts
- create_jira_task: Create JIRA tickets
- create_calendar_event: Schedule meetings
- update_employee_status: Update HR records
- find_delegate: Find team members
- check_sla_status: Check SLA compliance
- log_audit_entry: Write audit logs

Database schema:
```prisma
{PRISMA_SCHEMA}
```

Return ONLY a valid JSON array. Each element:
- "stepName": human-readable step name
- "stepDescription": detailed instruction mentioning which tool and exact parameters

Example:
[
  {{"stepName": "Create email account", "stepDescription": "Use create_email_account with employee_name='John', employee_email='john@co.com', department='Engineering'"}},
  {{"stepName": "Send welcome email", "stepDescription": "Use send_email with to='john@co.com', subject='Welcome!', body='Dear John, welcome aboard!'"}}
]""",
        callback_handler=None,
    )

    try:
        result = planner(f"Generate steps for: '{intent}'")
        response_text = str(result)

        _emit(workflow_id, "chat:message", "PlannerAgent", response_text[:800])

        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start >= 0 and end > start:
            raw_steps = json.loads(response_text[start:end])
            steps = []
            for i, s in enumerate(raw_steps):
                steps.append({
                    "id": str(uuid.uuid4()),
                    "stepName": s.get("stepName", f"Step {i+1}"),
                    "stepDescription": s.get("stepDescription", "Execute task"),
                    "status": "PENDING",
                    "assignedAgent": "ExecutionAgent",
                    "retryCount": 0,
                    "dependencyOrder": i,
                })
            _emit(workflow_id, "chat:plan_generated", "PlannerAgent",
                  f"✅ Generated {len(steps)}-step plan.",
                  {"steps": [{"stepName": s["stepName"], "stepDescription": s["stepDescription"]} for s in steps]})
            return steps
        return None
    except Exception as e:
        traceback.print_exc()
        _emit(workflow_id, "chat:error", "PlannerAgent", f"Planning failed: {str(e)[:300]}")
        return None


# ══════════════════════════════════════════════════
# GRAPH-BASED STEP EXECUTION
# ══════════════════════════════════════════════════

async def _execute_step_graph(
    step_name: str,
    step_desc: str,
    workflow_id: str,
    input_data: dict,
    mcp_client: MCPClient,
) -> str:
    """Execute a single step using a Strands Graph: Execute → Verify → (conditionally) Recover.

    Returns: "COMPLETED", "ESCALATED", or "FAILED"
    """
    model = _get_model()

    # ── Create 3 agent nodes ──
    exec_agent = Agent(
        model=model,
        name="ExecutionAgent",
        system_prompt=f"""You are an enterprise Execution Agent. Call the appropriate MCP tool to complete the task.
Always pass workflow_id='{workflow_id}' to tools that accept it.
Return the raw tool result. Do NOT explain — just call the tool.

Database schema:
```prisma
{PRISMA_SCHEMA}
```""",
        tools=[mcp_client],
        callback_handler=None,
    )

    verify_agent = Agent(
        model=model,
        name="VerificationAgent",
        system_prompt="""You are a verification agent.
Given a tool execution result, determine success.
Reply with EXACTLY one of:
- VERIFIED: <reason>
- FAILED: <reason>""",
        callback_handler=None,
    )

    recover_agent = Agent(
        model=model,
        name="RecoveryAgent",
        system_prompt="""You are a recovery agent.
Given a failed step, decide recovery action.
Reply with EXACTLY one of:
- RETRY: <reason>
- ESCALATE: <reason>""",
        callback_handler=None,
    )

    # ── Build the Graph ──
    builder = GraphBuilder()

    exec_node = builder.add_node(exec_agent, node_id="ExecutionAgent")
    verify_node = builder.add_node(verify_agent, node_id="VerificationAgent")
    recover_node = builder.add_node(recover_agent, node_id="RecoveryAgent")

    builder.add_edge("ExecutionAgent", "VerificationAgent")
    builder.add_edge("VerificationAgent", "RecoveryAgent",
                     condition=lambda state: _verification_failed(state))
    builder.set_entry_point("ExecutionAgent")
    builder.set_max_node_executions(6)  # Max 6 node executions (2 full cycles)
    builder.set_execution_timeout(120)  # 2 min timeout

    graph = builder.build()

    # ── Build task prompt ──
    task_prompt = (
        f"Execute: '{step_name}'\n"
        f"Instructions: {step_desc}\n"
        f"Workflow ID: {workflow_id}"
    )
    if input_data:
        task_prompt += f"\nContext: {json.dumps(input_data)}"

    # ── Stream graph execution ──
    final_status = "FAILED"
    try:
        async for event in graph.stream_async(task_prompt):
            # Debug: print raw event keys
            print(f"DEBUG: raw_event keys = {list(event.keys())}")
            if "multi_agent_node_stream" in event:
                print(f"DEBUG: inner stream keys = {list(event['multi_agent_node_stream'].get('event', {}).keys())}")
            
            # Node start
            if "multi_agent_node_start" in event:
                node_info = event["multi_agent_node_start"]
                node_id = node_info.get("node_id", "unknown")
                _emit(workflow_id, "chat:agent_assigned", node_id,
                      f"{'⚡' if 'Exec' in node_id else '🔍' if 'Verif' in node_id else '🔄'} {node_id}: Processing '{step_name}'")

            # Forwarded agent stream events
            if "multi_agent_node_stream" in event:
                stream_info = event["multi_agent_node_stream"]
                node_id = stream_info.get("node_id", "unknown")
                inner = stream_info.get("event", {})

                # Tool use
                if "current_tool_use" in inner:
                    tool_info = inner["current_tool_use"]
                    tool_name = tool_info.get("name", "unknown")
                    _emit(workflow_id, "chat:tool_call", node_id,
                          f"🔧 Calling tool: {tool_name}",
                          {"toolName": tool_name, "input": str(tool_info.get("input", ""))[:200]})

                # Text data
                if "data" in inner and isinstance(inner["data"], str) and len(inner["data"].strip()) > 2:
                    _emit(workflow_id, "chat:message", node_id, inner["data"][:500])

            # Node stop
            if "multi_agent_node_stop" in event:
                stop_info = event["multi_agent_node_stop"]
                node_id = stop_info.get("node_id", "unknown")
                node_result = stop_info.get("node_result", {})

                status = "completed"
                result_obj = getattr(node_result, 'result', None) if hasattr(node_result, 'result') else node_result.get("result", None)
                result_text = str(result_obj)[:500] if result_obj else ""

                _emit(workflow_id, "chat:tool_result", node_id,
                      f"📤 {node_id} output: {result_text[:300]}")

            # Final result
            if "result" in event:
                graph_result = event["result"]
                status_obj = getattr(graph_result, 'status', None)
                if status_obj:
                    final_status = "COMPLETED" if str(status_obj).upper() in ("COMPLETED", "STATUS.COMPLETED") else "ESCALATED"
                else:
                    final_status = "COMPLETED"

    except Exception as e:
        print(f"Graph execution error for '{step_name}': {e}")
        traceback.print_exc()
        _emit(workflow_id, "chat:error", "Graph", f"❌ Step failed: {str(e)[:300]}")
        final_status = "ESCALATED"

    return final_status


def _verification_failed(state) -> bool:
    """Condition: check if VerificationAgent output contains FAILED."""
    verify_result = state.results.get("VerificationAgent")
    if verify_result and verify_result.result:
        text = str(verify_result.result).upper()
        return "FAILED" in text
    return False


# ══════════════════════════════════════════════════
# MAIN WORKFLOW EXECUTOR
# ══════════════════════════════════════════════════

async def execute_workflow(workflow_id: str):
    """Execute a workflow end-to-end: Plan → Graph-based step execution with streaming."""
    wf = get_workflow(workflow_id)
    if not wf:
        raise ValueError(f"Workflow not found: {workflow_id}")

    intent = wf.get("type", "Execute workflow")
    input_data = wf.get("inputData", {}) or {}

    if input_data.get("triggerEvent") == "employee_created":
        intent = (
            f"Onboard new employee: {input_data.get('name')} "
            f"({input_data.get('role')} in {input_data.get('department')}). "
            f"Email: {input_data.get('email')}."
        )

    # ── Mark RUNNING ──
    update_workflow(workflow_id, {"status": "RUNNING"})
    _emit(workflow_id, "workflow:start", "Orchestrator", f"🚀 Starting: {intent}")
    append_audit_log(workflow_id, {
        "decision": "workflow_started", "reason": f"Goal: {intent}",
        "actionTaken": "Orchestrator initialized", "agentName": "Orchestrator",
        "status": "running",
    })

    # ── PHASE 1: PLAN ──
    steps = run_planner(intent, workflow_id)
    if not steps:
        update_workflow(workflow_id, {"status": "FAILED"})
        _emit(workflow_id, "workflow:failed", "Orchestrator", "❌ Planning failed — no steps generated")
        return

    update_workflow(workflow_id, {"plan": steps, "steps": steps})

    # ── PHASE 2: EXECUTE each step via Graph ──
    python_exe = sys.executable
    mcp_server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    has_escalation = False

    mcp_client = MCPClient(
        lambda: stdio_client(StdioServerParameters(
            command=python_exe,
            args=[mcp_server_path],
        ))
    )

    try:
        for i, step in enumerate(steps):
            step_name = step.get("stepName", f"Step {i+1}")
            step_desc = step.get("stepDescription", "Execute task")

            _emit(workflow_id, "chat:step_start", "Orchestrator",
                  f"📌 Step {i+1}/{len(steps)}: {step_name}")

            steps[i]["status"] = "RUNNING"
            update_workflow(workflow_id, {"steps": steps})

            # Run graph for this step
            step_status = await _execute_step_graph(
                step_name=step_name,
                step_desc=step_desc,
                workflow_id=workflow_id,
                input_data=input_data,
                mcp_client=mcp_client,
            )

            steps[i]["status"] = step_status
            update_workflow(workflow_id, {"steps": steps})

            if step_status == "COMPLETED":
                _emit(workflow_id, "chat:step_complete", "ExecutionAgent",
                      f"🎉 Completed: {step_name}")
                append_audit_log(workflow_id, {
                    "decision": "completed", "reason": f"Step '{step_name}' succeeded",
                    "actionTaken": "Step finished", "agentName": "ExecutionAgent",
                    "status": "completed",
                })
            else:
                has_escalation = True
                _emit(workflow_id, "chat:step_escalated", "RecoveryAgent",
                      f"🚨 Escalated: {step_name}")
                append_audit_log(workflow_id, {
                    "decision": "escalated", "reason": f"Step '{step_name}' escalated",
                    "actionTaken": "Escalated", "agentName": "RecoveryAgent",
                    "status": "escalated",
                })

    except Exception as e:
        print(f"Execution error: {e}")
        traceback.print_exc()
        update_workflow(workflow_id, {"status": "FAILED"})
        _emit(workflow_id, "workflow:failed", "Orchestrator",
              f"❌ Execution failed: {str(e)[:300]}")
        return
    finally:
        try:
            mcp_client.stop()
        except Exception:
            pass

    # ── FINAL STATUS ──
    final_status = "ESCALATED" if has_escalation else "COMPLETED"
    update_workflow(workflow_id, {"status": final_status})

    _emit(workflow_id, "workflow:complete", "Orchestrator",
          f"{'🎉' if final_status == 'COMPLETED' else '⚠️'} Workflow {final_status.lower()}",
          {"totalSteps": len(steps), "status": final_status})
    append_audit_log(workflow_id, {
        "decision": final_status.lower(),
        "reason": f"Workflow finished: {final_status}",
        "actionTaken": f"All {len(steps)} steps processed",
        "agentName": "Orchestrator", "status": final_status.lower(),
    })
