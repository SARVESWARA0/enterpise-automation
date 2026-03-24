"""
Step Graph — uses Strands GraphBuilder for per-step execution.

Graph topology per step:
    ExecutionAgent → VerificationAgent ─(VERIFIED)──→ Done
                                        └─(FAILED)──→ RecoveryAgent ─(RETRY)──→ [re-execute]
                                                                      └─(ESCALATE)→ Done
"""
import json
import traceback

from strands.multiagent.graph import GraphBuilder

from agents.execution import create_execution_agent
from agents.verification import create_verification_agent
from agents.recovery import create_recovery_agent
from orchestrator.streaming import emit_event


def _verification_failed(state) -> bool:
    """Condition: check if VerificationAgent output contains FAILED."""
    verify_result = state.results.get("VerificationAgent")
    if verify_result and verify_result.result:
        text = str(verify_result.result).upper()
        return "FAILED" in text
    return False


async def execute_step_graph(
    step_name: str,
    step_desc: str,
    workflow_id: str,
    input_data: dict,
    mcp_client,
) -> str:
    """Execute a single step using the Strands Graph: Execute → Verify → Recover.

    Args:
        step_name: Human-readable step name.
        step_desc: Detailed step description/instructions.
        workflow_id: The workflow ID.
        input_data: Contextual input data for the step.
        mcp_client: An active MCPClient instance.

    Returns:
        Final status: "COMPLETED", "ESCALATED", or "FAILED".
    """
    # ── Create agent instances ──
    exec_agent = create_execution_agent(workflow_id, mcp_client)
    verify_agent = create_verification_agent()
    recover_agent = create_recovery_agent()

    # ── Build the Graph ──
    builder = GraphBuilder()

    builder.add_node(exec_agent, node_id="ExecutionAgent")
    builder.add_node(verify_agent, node_id="VerificationAgent")
    builder.add_node(recover_agent, node_id="RecoveryAgent")

    builder.add_edge("ExecutionAgent", "VerificationAgent")
    builder.add_edge("VerificationAgent", "RecoveryAgent",
                     condition=lambda state: _verification_failed(state))
    builder.set_entry_point("ExecutionAgent")
    builder.set_max_node_executions(6)  # Max 6 node executions (2 full retry cycles)
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
            # Node start
            if "multi_agent_node_start" in event:
                node_info = event["multi_agent_node_start"]
                node_id = node_info.get("node_id", "unknown")
                emoji = "⚡" if "Exec" in node_id else "🔍" if "Verif" in node_id else "🔄"
                emit_event(workflow_id, "chat:agent_assigned", node_id,
                          f"{emoji} {node_id}: Processing '{step_name}'")

            # Forwarded agent stream events
            if "multi_agent_node_stream" in event:
                stream_info = event["multi_agent_node_stream"]
                node_id = stream_info.get("node_id", "unknown")
                inner = stream_info.get("event", {})

                # Tool use
                if "current_tool_use" in inner:
                    tool_info = inner["current_tool_use"]
                    tool_name = tool_info.get("name", "unknown")
                    emit_event(workflow_id, "chat:tool_call", node_id,
                              f"🔧 Calling tool: {tool_name}",
                              {"toolName": tool_name, "input": str(tool_info.get("input", ""))[:200]})

                # Text data
                if "data" in inner and isinstance(inner["data"], str) and len(inner["data"].strip()) > 2:
                    emit_event(workflow_id, "chat:message", node_id, inner["data"][:500])

            # Node stop
            if "multi_agent_node_stop" in event:
                stop_info = event["multi_agent_node_stop"]
                node_id = stop_info.get("node_id", "unknown")
                node_result = stop_info.get("node_result", {})

                result_obj = getattr(node_result, 'result', None) if hasattr(node_result, 'result') else node_result.get("result", None)
                result_text = str(result_obj)[:500] if result_obj else ""

                emit_event(workflow_id, "chat:tool_result", node_id,
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
        emit_event(workflow_id, "chat:error", "Graph", f"❌ Step failed: {str(e)[:300]}")
        final_status = "ESCALATED"

    return final_status
