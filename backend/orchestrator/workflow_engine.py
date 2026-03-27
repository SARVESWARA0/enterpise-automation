"""
Workflow Engine — Orchestrator that runs the Interpret → Graph(Exec→Verify→Recover) loop.
Emits SSE events at every state transition via asyncio.Queue.
Uses Strands Graph for per-step execution with streaming.
All state lives in PostgreSQL — no files.
"""
import asyncio
import json
import time
import traceback
from datetime import datetime, timezone
from typing import AsyncIterator

from models import SSEEvent, WorkflowStep
from agents.interpreter_agent import get_interpreter_agent, generate_plan
from agents.context_handling_agent import get_context_handling_agent
from agents.execution_agent import get_execution_agent
from agents.verification_agent import get_verification_agent
from agents.recovery_agent import get_recovery_agent
from agents import get_mcp_client
from db import queries as db
from orchestrator.graph import build_step_graph
from state_manager import append_stream_event, get_stream_events

# ── SSE Event Queues (in-memory, per workflow) ──
_event_queues: dict[str, asyncio.Queue] = {}


def get_or_create_queue(workflow_id: str) -> asyncio.Queue:
    if workflow_id not in _event_queues:
        _event_queues[workflow_id] = asyncio.Queue(maxsize=500)
    return _event_queues[workflow_id]


async def emit(workflow_id: str, event_type: str, agent: str,
               data, step_id: str = None):
    """Push a structured SSE event into the workflow's queue."""
    queue = get_or_create_queue(workflow_id)
    event = SSEEvent(
        event_type=event_type,
        agent=agent,
        step_id=step_id,
        data=data,
    )
    dumped = event.model_dump()
    
    # Drop token chunks if queue is backing up, never drop structural events
    structural = {"plan", "step_start", "step_complete", "step_failed", 
                  "recovery", "audit", "workflow_complete"}
    if queue.full() and event_type not in structural:
        return  # silently drop stream tokens under pressure

    try:
        await queue.put(dumped)
    except asyncio.QueueFull:
        pass
    
    # Also save to disk for historical replay
    try:
        append_stream_event(workflow_id, dumped)
    except Exception as e:
        print(f"Failed to append stream event: {e}")


async def sse_stream(workflow_id: str) -> AsyncIterator[str]:
    """FastAPI SSE generator — yields live events, or historical events for completed workflows."""
    from db import queries as db
    wf = db.get_workflow(workflow_id)
    
    # If the workflow is already finished, replay the exact historical events to hydrate the frontend
    if wf and wf.get("status") in ("COMPLETED", "FAILED", "ESCALATED"):
        try:
            historical_events = get_stream_events(workflow_id)
            for evt in historical_events:
                yield f"data: {json.dumps(evt)}\n\n"
                await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Error reading historical stream: {e}")
            yield f"data: {json.dumps({'event_type': 'workflow_complete', 'data': {'status': wf['status'], 'summary': 'Historical execution loaded.'}})}\n\n"
        return

    # Otherwise stream live from the queue
    queue = get_or_create_queue(workflow_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
                if event.get("event_type") == "workflow_complete":
                    yield f"data: {json.dumps(event)}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield 'data: {"event_type": "heartbeat"}\n\n'
    finally:
        _event_queues.pop(workflow_id, None)


# ── Main Workflow Runner ──

async def run_workflow(workflow_id: str, user_request: str,
                       state_manager=None):
    """
    Full autonomous workflow execution with Strands Graph.
    
    Flow:
      1. Interpreter generates JSON plan → save as steps in DB
      2. Build Strands Graph per step (exec → verify → recovery loop)
      3. Run each step through its graph with streaming
      4. Emit workflow_complete
    """
    emitter = lambda et, ag, data, **kw: emit(workflow_id, et, ag, data, **kw)

    # ── DB: workflow started ──
    db.update_workflow_status(workflow_id, "PLANNING")

    # ── PHASE 1: INTERPRET ──────────────────────────────────────────────────
    await emitter("agent_message", "interpreter", {
        "message": f"Analyzing request: \"{user_request}\"\nGenerating execution plan..."
    })
    await emitter("agent_active", "interpreter", {"active": True, "action": "Generating plan"})

    interpreter = await get_interpreter_agent()

    try:
        raw_steps = generate_plan(interpreter, user_request)
    except Exception as e:
        traceback.print_exc()
        db.update_workflow_status(workflow_id, "FAILED")
        await emitter("workflow_complete", "interpreter", {
            "error": f"Plan generation failed: {str(e)[:300]}",
            "status": "FAILED"
        })
        return

    if not raw_steps:
        db.update_workflow_status(workflow_id, "FAILED")
        await emitter("workflow_complete", "interpreter", {
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

    # Save plan to workflow record
    db.update_workflow_status(workflow_id, "RUNNING", plan=raw_steps)

    # Create all steps in DB
    step_db_map = {}  # plan step_id → DB step UUID
    for i, raw_step in enumerate(raw_steps):
        step_row = db.create_step(
            workflow_id=workflow_id,
            step_name=raw_step.get("name", f"Step {i+1}"),
            step_type=raw_step.get("tool_name", "unknown"),
            tool_name=raw_step.get("tool_name"),
            input_data=raw_step.get("parameters", {}),
            dependency_order=i,
            assigned_agent=raw_step.get("assigned_agent", "execution"),
            fallback_behavior=raw_step.get("fallback", "ESCALATE")
        )
        step_db_map[raw_step.get("step_id", i + 1)] = step_row["id"]

    # Emit the full plan
    await emitter("plan", "interpreter", {"steps": raw_steps, "total": len(raw_steps)})
    await emitter("agent_message", "interpreter", {
        "message": f"✅ Plan generated: {len(raw_steps)} steps identified. Beginning execution..."
    })
    await emitter("agent_active", "interpreter", {"active": False})

    # ── PHASE 2: EXECUTE EACH STEP THROUGH GRAPH ────────────────────────────
    def _mcp_client_healthy(client):
        try:
            return client._session is not None
        except Exception:
            return False

    execution_mcp_client = get_mcp_client()
    recovery_mcp_client = get_mcp_client()

    execution_agent = get_execution_agent([execution_mcp_client])
    context_handling_agent = get_context_handling_agent()
    verification_agent = get_verification_agent()
    recovery_agent = get_recovery_agent([recovery_mcp_client])

    step_results = {}
    output_accumulator = {}  # step_id → extracted data dict from tool envelope

    for raw_step in raw_steps:
        try:
            step = WorkflowStep(**raw_step)
            plan_step_id = step.step_id
            step_db_id = step_db_map.get(plan_step_id, "unknown")

            # ── Check dependencies ──
            skip = False
            for dep in step.depends_on:
                if isinstance(dep, dict):
                    dep_id = dep.get("step_id")
                    dep_type = dep.get("type", "hard")
                else:
                    dep_id = dep
                    # Planner currently emits `depends_on` as simple step IDs (no {type: ...} metadata).
                    # Defaulting to "soft" prevents cascades where a single ESCALATED/SKIPPED prerequisite
                    # blocks downstream audit/log steps and optional continuations.
                    dep_type = "soft"

                dep_result = step_results.get(dep_id, {})
                status = dep_result.get("status")
                
                if status not in ("COMPLETED", "ESCALATED", "SKIPPED"):
                    await emitter("step_failed", "orchestrator", {
                        "step_id": plan_step_id,
                        "reason": f"Dependency step {dep_id} did not complete."
                    }, step_id=str(plan_step_id))
                    step_results[plan_step_id] = {"status": "SKIPPED"}
                    db.update_step(step_db_id, status="SKIPPED")
                    skip = True
                    break
                
                if status in ("ESCALATED", "SKIPPED") and dep_type == "hard":
                    await emitter("step_failed", "orchestrator", {
                        "step_id": plan_step_id,
                        "reason": f"Required dependency step {dep_id} was {status.lower()}."
                    }, step_id=str(plan_step_id))
                    step_results[plan_step_id] = {"status": "SKIPPED"}
                    db.update_step(step_db_id, status="SKIPPED")
                    skip = True
                    break
                    
            if skip:
                continue

            # Check MCP Client Health
            if not _mcp_client_healthy(execution_mcp_client):
                try: execution_mcp_client.stop()
                except Exception: pass
                execution_mcp_client = get_mcp_client()
                execution_agent = get_execution_agent([execution_mcp_client])
            
            if not _mcp_client_healthy(recovery_mcp_client):
                try: recovery_mcp_client.stop()
                except Exception: pass
                recovery_mcp_client = get_mcp_client()
                recovery_agent = get_recovery_agent([recovery_mcp_client])

            # ── STEP START ──
            db.update_step(step_db_id, status="RUNNING")
            await emitter("step_start", "execution", {
                "step_id": plan_step_id,
                "name": step.name,
                "tool": step.tool_name,
                "parameters": step.parameters
            }, step_id=str(plan_step_id))
            await emitter("agent_active", "execution", {
                "active": True,
                "action": f"{step.tool_name}: {step.name[:60]}"
            })

            # ── BUILD & RUN GRAPH FOR THIS STEP ──
            # No static parameter resolution — the Execution Agent resolves
            # empty params using the full workflow_context (LLM intelligence).
            step_context = {
                "step_id": plan_step_id,
                "step_name": step.name,
                "tool_name": step.tool_name,
                "parameters": dict(step.parameters),
                "step_db_id": step_db_id,
                "workflow_context": dict(output_accumulator),  # shared state
            }

            start_ms = int(time.time() * 1000)

            try:
                graph, graph_state = build_step_graph(
                    context_handling_agent=context_handling_agent,
                    execution_agent=execution_agent,
                    verification_agent=verification_agent,
                    recovery_agent=recovery_agent,
                    emit_fn=emitter,
                    workflow_id=workflow_id,
                    step_context=step_context,
                    db_module=db,
                    prior_outputs=output_accumulator,
                )

                # Run the graph — stream events
                async for event in graph.stream_async(
                    f"Execute step: {step.name} using tool {step.tool_name}"
                ):
                    # Graph streaming events are handled internally by node functions
                    # via emit_fn. We just need to consume the stream to drive execution.
                    pass

            except Exception as e:
                print(f"Graph execution error for step {plan_step_id}: {e}")
                traceback.print_exc()
                await emitter("step_failed", "orchestrator", {
                    "step_id": plan_step_id,
                    "error": str(e)[:300]
                }, step_id=str(plan_step_id))
                db.update_step(step_db_id, status="FAILED",
                               output={"error": str(e)[:300]})
                graph_state = {"final_status": "FAILED"}

            duration_ms = int(time.time() * 1000) - start_ms
            final_status = graph_state.get("final_status", "FAILED")
            exec_output = graph_state.get("exec_output")
            step_results[plan_step_id] = {
                "status": final_status,
                "output": exec_output
            }

            # ── Extract data into output_accumulator (Fix 4) ──
            if final_status == "COMPLETED" and isinstance(exec_output, dict):
                raw_out = exec_output.get("output", exec_output)
                if isinstance(raw_out, str):
                    try:
                        raw_out = json.loads(raw_out)
                    except Exception:
                        raw_out = exec_output
                if isinstance(raw_out, dict):
                    # Persist both dict and list payloads so downstream steps can resolve params.
                    data = raw_out.get("data", raw_out)
                    if isinstance(data, (dict, list)):
                        output_accumulator[plan_step_id] = data

            # Log duration
            db.log_agent_action(
                workflow_id=workflow_id, step_id=step_db_id,
                agent_name="orchestrator",
                action=f"step_{final_status.lower()}",
                tool_name=step.tool_name,
                duration_ms=duration_ms,
                output={"final_status": final_status}
            )

            await emitter("agent_active", "execution", {"active": False})
            await asyncio.sleep(0.3)  # Pacing for readable stream

        except Exception as step_exc:
            print(f"CRITICAL LOOP ERROR on step {raw_step}: {step_exc}")
            traceback.print_exc()
            step_results[raw_step.get("step_id")] = {"status": "FAILED"}

    # ── Cleanup MCP ──
    try:
        execution_mcp_client.stop()
        recovery_mcp_client.stop()
    except Exception:
        pass

    # ── PHASE 3: COMPLETE ──────────────────────────────────────────────────
    completed_count = sum(1 for r in step_results.values() if r.get("status") == "COMPLETED")
    escalated_count = sum(1 for r in step_results.values() if r.get("status") == "ESCALATED")
    skipped_count = sum(1 for r in step_results.values() if r.get("status") == "SKIPPED")
    failed_count = len(raw_steps) - completed_count - escalated_count - skipped_count

    final_wf_status = "COMPLETED" if failed_count == 0 and escalated_count == 0 else (
        "ESCALATED" if escalated_count > 0 else "FAILED"
    )

    db.update_workflow_status(workflow_id, final_wf_status)

    # Update employee status if this was an onboarding workflow
    wf = db.get_workflow(workflow_id)
    if wf and wf.get("entity_id"):
        emp_status = "ACTIVE" if final_wf_status == "COMPLETED" else "ONBOARDING"
        db.update_employee_status("", emp_status, employee_db_id=wf["entity_id"])

    await emitter("workflow_complete", "orchestrator", {
        "status": final_wf_status,
        "total_steps": len(raw_steps),
        "completed": completed_count,
        "escalated": escalated_count,
        "failed": failed_count,
        "summary": (
            f"Workflow finished: {completed_count}/{len(raw_steps)} steps completed autonomously. "
            f"{escalated_count} escalated to humans."
        )
    })
