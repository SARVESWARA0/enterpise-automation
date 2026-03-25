"""
Workflow Engine — Core orchestrator that runs the Interpret → Execute → Verify → Recover loop.
Emits SSE events at every state transition via asyncio.Queue.
Streams raw agent tokens via stream_async() for live UI display.
"""
import asyncio
import json
import traceback
from datetime import datetime, timezone
from typing import AsyncIterator

from models import SSEEvent, WorkflowStep
from agents.interpreter_agent import get_interpreter_agent, generate_plan
from agents.execution_agent import get_execution_agent
from agents.verification_agent import get_verification_agent
from agents.recovery_agent import get_recovery_agent
from agents import get_mcp_client, TOOL_MANIFEST

# ── SSE Event Queues (in-memory, per workflow) ──
_event_queues: dict[str, asyncio.Queue] = {}


def get_or_create_queue(workflow_id: str) -> asyncio.Queue:
    if workflow_id not in _event_queues:
        _event_queues[workflow_id] = asyncio.Queue()
    return _event_queues[workflow_id]


async def emit(workflow_id: str, event_type: str, agent: str,
               data: any, step_id: int = None):
    """Push a structured SSE event into the workflow's queue."""
    queue = get_or_create_queue(workflow_id)
    event = SSEEvent(
        event_type=event_type,
        agent=agent,
        step_id=step_id,
        data=data,
    )
    await queue.put(event.model_dump())


async def sse_stream(workflow_id: str) -> AsyncIterator[str]:
    """FastAPI SSE generator — yields events as they arrive."""
    queue = get_or_create_queue(workflow_id)
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=120.0)
            if event.get("event_type") == "workflow_complete":
                yield f"data: {json.dumps(event)}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            yield 'data: {"event_type": "heartbeat"}\n\n'


def _parse_agent_json(raw_text: str) -> dict:
    """Best-effort parse JSON from an agent's text response."""
    text = raw_text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    # Find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}


async def _stream_agent(
    workflow_id: str,
    agent_name: str,
    agent,
    prompt: str,
    step_id: int = None,
) -> str:
    """
    Call an agent using stream_async() and forward every event to the SSE queue.
    Returns the full accumulated text response.
    
    Each event from Strands stream_async() looks like:
      { "data": "<text_chunk>", "complete": bool, "current_tool_use": {...}, ... }
    """
    full_text = ""
    current_tool_name = None

    try:
        async for event in agent.stream_async(prompt):
            # ── Text token chunk ──
            if "data" in event and event["data"]:
                chunk = event["data"]
                full_text += chunk
                await emit(workflow_id, "token_stream", agent_name, {
                    "chunk": chunk,
                    "tool_context": current_tool_name,
                }, step_id=step_id)

            # ── Tool use start ──
            if "current_tool_use" in event and event["current_tool_use"]:
                tool_info = event["current_tool_use"]
                tool_name = tool_info.get("name", "")
                if tool_name and tool_name != current_tool_name:
                    current_tool_name = tool_name
                    await emit(workflow_id, "agent_tool_start", agent_name, {
                        "tool": tool_name,
                        "input": tool_info.get("input", {}),
                    }, step_id=step_id)

            # ── Reasoning tokens ──
            if "reasoningText" in event and event["reasoningText"]:
                await emit(workflow_id, "token_stream", agent_name, {
                    "chunk": event["reasoningText"],
                    "is_reasoning": True,
                }, step_id=step_id)

            # ── Final result ──
            if "result" in event:
                result = event["result"]
                result_text = str(result)
                if result_text and not full_text:
                    full_text = result_text

        return full_text

    except Exception as e:
        # Fall back to synchronous call if stream_async fails
        try:
            result = await asyncio.to_thread(agent, prompt)
            return str(result)
        except Exception as e2:
            return json.dumps({
                "status": "FAILURE",
                "error": str(e2)[:300],
            })


# ── Main Workflow Runner ──

async def run_workflow(workflow_id: str, user_request: str,
                       state_manager=None):
    """
    Full autonomous workflow execution with streaming.
    """
    # ── PHASE 1: INTERPRET ──
    await emit(workflow_id, "agent_message", "interpreter", {
        "message": f"Analyzing request: \"{user_request}\"\nGenerating execution plan..."
    })

    interpreter = get_interpreter_agent(TOOL_MANIFEST)

    try:
        raw_steps = generate_plan(interpreter, user_request)
    except Exception as e:
        traceback.print_exc()
        await emit(workflow_id, "workflow_complete", "interpreter", {
            "error": f"Plan generation failed: {str(e)[:300]}",
            "status": "FAILED"
        })
        return

    if not raw_steps:
        await emit(workflow_id, "workflow_complete", "interpreter", {
            "error": "Interpreter returned empty plan.",
            "status": "FAILED"
        })
        return

    # Replace workflow_id placeholders in parameters
    for step in raw_steps:
        params = step.get("parameters", {})
        for key, val in params.items():
            if val == "__WORKFLOW_ID__":
                params[key] = workflow_id

    # Emit the full plan
    await emit(workflow_id, "plan", "interpreter", {"steps": raw_steps})
    await emit(workflow_id, "agent_message", "interpreter", {
        "message": f"✅ Plan generated: {len(raw_steps)} steps identified. Beginning execution..."
    })

    # Persist plan to state
    if state_manager:
        try:
            state_manager.update_workflow(workflow_id, {
                "plan": raw_steps,
                "steps": raw_steps,
                "status": "RUNNING",
            })
        except Exception:
            pass

    # ── PHASE 2: EXECUTE EACH STEP ──
    execution_mcp_client = get_mcp_client()
    recovery_mcp_client = get_mcp_client()

    execution_agent = get_execution_agent([execution_mcp_client])
    verification_agent = get_verification_agent()
    recovery_agent = get_recovery_agent([recovery_mcp_client])

    step_results = {}

    for raw_step in raw_steps:
        try:
            step = WorkflowStep(**raw_step)

            # ── Check dependencies ──
            skip = False
            for dep_id in step.depends_on:
                dep_result = step_results.get(dep_id, {})
                if dep_result.get("status") not in ("COMPLETED", "ESCALATED"):
                    await emit(workflow_id, "step_failed", "orchestrator", {
                        "message": f"Step {step.step_id} skipped: dependency step {dep_id} did not complete."
                    }, step_id=step.step_id)
                    step_results[step.step_id] = {"status": "SKIPPED"}
                    skip = True
                    break
            if skip:
                continue

            # ── STEP START ──
            await emit(workflow_id, "step_start", "execution", {
                "step_id": step.step_id,
                "name": step.name,
                "tool": step.tool_name,
                "parameters": step.parameters
            }, step_id=step.step_id)

            retry_count = 0
            max_retries = 2
            step_resolved = False
            current_params = dict(step.parameters)

            while not step_resolved and retry_count <= max_retries:

                # ── EXECUTION — streams live tokens ──
                await emit(workflow_id, "tool_call", "execution", {
                    "tool": step.tool_name,
                    "parameters": current_params,
                    "attempt": retry_count + 1
                }, step_id=step.step_id)

                exec_prompt = (
                    f"Execute this step:\n"
                    f"Tool: {step.tool_name}\n"
                    f"Parameters: {json.dumps(current_params)}\n"
                    f"Call the tool now and return the JSON result object only."
                )

                try:
                    exec_output = await _stream_agent(
                        workflow_id, "execution", execution_agent,
                        exec_prompt, step_id=step.step_id
                    )
                except Exception as e:
                    exec_output = json.dumps({
                        "status": "FAILURE",
                        "tool_called": step.tool_name,
                        "output": None,
                        "error": str(e)[:300]
                    })

                # Parse execution result
                exec_result = _parse_agent_json(exec_output)
                if not exec_result:
                    exec_result = {
                        "status": "FAILURE",
                        "tool_called": step.tool_name,
                        "output": exec_output[:500],
                        "error": "Could not parse execution result"
                    }

                # Determine if tool itself reported success
                output_data = exec_result.get("output", "")
                if isinstance(output_data, str):
                    try:
                        output_data = json.loads(output_data)
                    except Exception:
                        pass

                if isinstance(output_data, dict):
                    if output_data.get("success") is True:
                        exec_result["status"] = "SUCCESS"
                    elif output_data.get("success") is False:
                        exec_result["status"] = "FAILURE"
                        exec_result["error"] = output_data.get("error", "Tool returned failure")

                await emit(workflow_id, "tool_result", "execution", exec_result,
                           step_id=step.step_id)

                # ── VERIFICATION — streams live tokens ──
                await emit(workflow_id, "agent_message", "verification", {
                    "message": f"Verifying result of: {step.tool_name}..."
                }, step_id=step.step_id)

                verify_prompt = (
                    f"Step: {step.name}\n"
                    f"Tool Called: {step.tool_name}\n"
                    f"Parameters: {json.dumps(current_params)}\n"
                    f"Execution Output: {json.dumps(exec_result)}\n\n"
                    f"Provide your verification verdict JSON."
                )

                try:
                    verify_text = await _stream_agent(
                        workflow_id, "verification", verification_agent,
                        verify_prompt, step_id=step.step_id
                    )
                except Exception:
                    verify_text = ""

                verify_result = _parse_agent_json(verify_text)
                if not verify_result or "verdict" not in verify_result:
                    # Fallback: use execution status
                    if exec_result.get("status") == "SUCCESS":
                        verify_result = {"verdict": "VERIFIED", "confidence": 0.8,
                                         "reason": "Inferred from execution status", "suggested_recovery": None}
                    else:
                        verify_result = {"verdict": "FAILED", "confidence": 0.7,
                                         "reason": "Inferred from execution failure", "suggested_recovery": "RETRY"}

                await emit(workflow_id, "agent_message", "verification", {
                    "verdict": verify_result.get("verdict"),
                    "reason": verify_result.get("reason"),
                    "confidence": verify_result.get("confidence")
                }, step_id=step.step_id)

                if verify_result.get("verdict") == "VERIFIED":
                    # ── SUCCESS ──
                    step_results[step.step_id] = {
                        "status": "COMPLETED",
                        "output": exec_result.get("output")
                    }
                    await emit(workflow_id, "step_complete", "verification", {
                        "step_id": step.step_id,
                        "name": step.name,
                        "output": exec_result.get("output")
                    }, step_id=step.step_id)
                    step_resolved = True

                else:
                    # ── RECOVERY — streams live tokens ──
                    retry_count += 1
                    await emit(workflow_id, "recovery", "recovery", {
                        "message": f"Step {step.step_id} failed. Analyzing recovery options... (attempt {retry_count}/{max_retries})"
                    }, step_id=step.step_id)

                    recovery_prompt = (
                        f"Failed Step: {step.name}\n"
                        f"Tool: {step.tool_name}\n"
                        f"Parameters: {json.dumps(current_params)}\n"
                        f"Execution Output: {json.dumps(exec_result)}\n"
                        f"Verification Verdict: {json.dumps(verify_result)}\n"
                        f"Retry Count: {retry_count}\n"
                        f"Workflow ID: {workflow_id}\n"
                        f"Employee Name: {_extract_employee_name(current_params)}\n\n"
                        f"Decide recovery action. Return JSON only."
                    )

                    try:
                        recovery_text = await _stream_agent(
                            workflow_id, "recovery", recovery_agent,
                            recovery_prompt, step_id=step.step_id
                        )
                    except Exception:
                        recovery_text = ""

                    recovery_result = _parse_agent_json(recovery_text)
                    if not recovery_result or "action" not in recovery_result:
                        recovery_result = {
                            "action": "RETRY" if retry_count <= max_retries else "ESCALATE",
                            "reason": "Auto-recovery decision",
                            "audit_message": f"Auto-recovery for {step.tool_name}"
                        }

                    await emit(workflow_id, "recovery", "recovery", {
                        "action": recovery_result.get("action"),
                        "reason": recovery_result.get("reason"),
                        "audit_message": recovery_result.get("audit_message")
                    }, step_id=step.step_id)

                    action = recovery_result.get("action", "RETRY")

                    if action == "RETRY":
                        if recovery_result.get("modified_parameters"):
                            current_params = recovery_result["modified_parameters"]
                        # Loop continues

                    elif action in ("ESCALATE", "REROUTE"):
                        escalation_tool = recovery_result.get("escalation_tool")
                        escalation_params = recovery_result.get("escalation_parameters", {})

                        if escalation_tool:
                            await emit(workflow_id, "tool_call", "recovery", {
                                "tool": escalation_tool,
                                "parameters": escalation_params,
                                "reason": f"Escalation: {recovery_result.get('reason', '')}"
                            }, step_id=step.step_id)

                            esc_prompt = (
                                f"Execute this escalation step:\n"
                                f"Tool: {escalation_tool}\n"
                                f"Parameters: {json.dumps(escalation_params)}\n"
                                f"Call the tool now and return the JSON result."
                            )
                            try:
                                esc_output = await _stream_agent(
                                    workflow_id, "recovery", execution_agent,
                                    esc_prompt, step_id=step.step_id
                                )
                                esc_result = _parse_agent_json(esc_output)
                                await emit(workflow_id, "tool_result", "recovery",
                                           esc_result or {"output": esc_output[:300]},
                                           step_id=step.step_id)
                            except Exception:
                                pass

                        step_results[step.step_id] = {
                            "status": "ESCALATED",
                            "reason": recovery_result.get("reason")
                        }
                        await emit(workflow_id, "step_failed", "recovery", {
                            "step_id": step.step_id,
                            "status": "ESCALATED",
                            "action": action,
                            "reason": recovery_result.get("reason")
                        }, step_id=step.step_id)
                        step_resolved = True

                    elif action == "SKIP":
                        step_results[step.step_id] = {"status": "SKIPPED"}
                        step_resolved = True

                # Retries exhausted
                if retry_count > max_retries and not step_resolved:
                    step_results[step.step_id] = {"status": "FAILED"}
                    await emit(workflow_id, "step_failed", "recovery", {
                        "step_id": step.step_id,
                        "status": "FAILED",
                        "reason": "Max retries exceeded"
                    }, step_id=step.step_id)
                    step_resolved = True

            # Persist step status to state
            if state_manager:
                try:
                    current_steps = raw_steps.copy()
                    for s in current_steps:
                        sid = s.get("step_id")
                        if sid in step_results:
                            s["status"] = step_results[sid]["status"]
                    state_manager.update_workflow(workflow_id, {"steps": current_steps})
                except Exception:
                    pass

            # Brief pause between steps for stream readability
            await asyncio.sleep(0.3)
        except Exception as step_exc:
            print(f"CRITICAL LOOP ERROR parsing/executing raw_step {raw_step}: {step_exc}")
            traceback.print_exc()
            step_results[raw_step.get("step_id")] = {"status": "FAILED"}

    # ── Cleanup MCP ──
    try:
        execution_mcp_client.stop()
        recovery_mcp_client.stop()
    except Exception:
        pass

    # ── PHASE 3: COMPLETE ──
    completed_count = sum(1 for r in step_results.values() if r.get("status") == "COMPLETED")
    escalated_count = sum(1 for r in step_results.values() if r.get("status") == "ESCALATED")
    failed_count = len(raw_steps) - completed_count - escalated_count

    final_status = "COMPLETED" if failed_count == 0 and escalated_count == 0 else "ESCALATED" if escalated_count > 0 else "FAILED"

    if state_manager:
        try:
            state_manager.update_workflow(workflow_id, {"status": final_status})
        except Exception:
            pass

    await emit(workflow_id, "workflow_complete", "orchestrator", {
        "status": final_status,
        "total_steps": len(raw_steps),
        "completed": completed_count,
        "escalated": escalated_count,
        "failed": failed_count,
        "summary": f"Workflow finished: {completed_count}/{len(raw_steps)} steps completed autonomously. {escalated_count} escalated to humans."
    })


def _extract_employee_name(params: dict) -> str:
    """Extract employee name from step parameters."""
    return params.get("name", params.get("employee_name", "unknown"))
