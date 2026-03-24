"""
Orchestrator Engine — deterministic state machine for workflow execution.
No LLM calls here. All intelligence is delegated to specialized agents.

Flow:
1. Run WorkflowInterpreter → get step plan
2. For each step:
   a. If step type is 'decision' → run DecisionAgent
   b. If decision needs clarification → run ClarificationAgent
   c. Run step graph (Execution → Verification → Recovery)
   d. Update state in state_manager
   e. Log via audit service
   f. Emit SSE events
   g. Run HealthMonitor to check SLA
   h. If HealthMonitor flags AT_RISK/BREACH → handle accordingly
3. Final status: COMPLETED / ESCALATED / FAILED
"""
import traceback
from datetime import datetime, timezone

from state_manager import update_workflow, get_workflow
from agents.base import get_mcp_client
from agents.interpreter import run_interpreter
from agents.decision import run_decision_agent
from agents.clarification import run_clarification_agent
from agents.health_monitor import run_health_monitor
from orchestrator.streaming import emit_event
from orchestrator.step_graph import execute_step_graph
from services.audit import AuditService


async def execute_workflow(workflow_id: str):
    """Execute a workflow end-to-end: Interpret → Step-by-step graph execution with streaming.

    This is the main entry point called from main.py background tasks.
    """
    wf = get_workflow(workflow_id)
    if not wf:
        raise ValueError(f"Workflow not found: {workflow_id}")

    intent = wf.get("type", "Execute workflow")
    input_data = wf.get("inputData", {}) or {}

    # ── Build a richer intent for known trigger events ──
    if input_data.get("triggerEvent") == "employee_created":
        intent = (
            f"Onboard new employee: {input_data.get('name')} "
            f"({input_data.get('role')} in {input_data.get('department')}). "
            f"Email: {input_data.get('email')}."
        )

    # ── Mark RUNNING ──
    update_workflow(workflow_id, {"status": "RUNNING"})
    emit_event(workflow_id, "workflow:start", "Orchestrator", f"🚀 Starting: {intent}")
    AuditService.log_workflow_start(workflow_id, intent)

    # ══════════════════════════════════════
    # PHASE 1: INTERPRET — generate step plan
    # ══════════════════════════════════════
    steps = run_interpreter(intent, workflow_id, emit_event)
    if not steps:
        update_workflow(workflow_id, {"status": "FAILED"})
        emit_event(workflow_id, "workflow:failed", "Orchestrator",
                   "❌ Planning failed — no steps generated")
        return

    update_workflow(workflow_id, {"plan": steps, "steps": steps})

    # ══════════════════════════════════════
    # PHASE 2: EXECUTE — process each step
    # ══════════════════════════════════════
    mcp_client = get_mcp_client()
    has_escalation = False
    workflow_start_time = datetime.now(timezone.utc)

    try:
        for i, step in enumerate(steps):
            step_name = step.get("stepName", f"Step {i+1}")
            step_desc = step.get("stepDescription", "Execute task")
            step_type = step.get("stepType", "action")
            assigned_agent = step.get("assignedAgent", "ExecutionAgent")

            emit_event(workflow_id, "chat:step_start", "Orchestrator",
                      f"📌 Step {i+1}/{len(steps)}: {step_name}")
            AuditService.log_step_start(workflow_id, step_name, assigned_agent)

            # ── Mark step RUNNING ──
            steps[i]["status"] = "RUNNING"
            update_workflow(workflow_id, {"steps": steps})

            # ── DECISION CHECK: If step needs owner assignment ──
            if step_type == "decision" or assigned_agent == "DecisionAgent":
                decision = run_decision_agent(
                    f"Step: {step_name}\nDescription: {step_desc}\nContext: {input_data}",
                    workflow_id, emit_event,
                )

                if decision.get("needs_clarification"):
                    # ── Run Clarification Agent ──
                    clarification = run_clarification_agent(
                        decision.get("clarification_question", step_desc),
                        workflow_id, emit_event,
                    )
                    AuditService.log_clarification(workflow_id, step_name, clarification.get("summary", ""))

                    if clarification.get("blocking"):
                        steps[i]["status"] = "AWAITING_CLARIFICATION"
                        update_workflow(workflow_id, {"steps": steps})
                        emit_event(workflow_id, "chat:step_escalated", "ClarificationAgent",
                                  f"⏸️ Step '{step_name}' awaiting clarification: {clarification.get('summary')}")
                        continue  # Skip to next step; this one is blocked
                    else:
                        # Non-blocking clarification — log and continue with best guess
                        emit_event(workflow_id, "chat:message", "ClarificationAgent",
                                  f"ℹ️ Clarification noted (non-blocking): {clarification.get('summary')}")
                else:
                    AuditService.log_decision(
                        workflow_id, step_name,
                        str(decision.get("decision", "N/A")),
                        decision.get("reason", ""),
                    )

            # ── EXECUTE: Run the step graph (Exec → Verify → Recover) ──
            step_status = await execute_step_graph(
                step_name=step_name,
                step_desc=step_desc,
                workflow_id=workflow_id,
                input_data=input_data,
                mcp_client=mcp_client,
            )

            # ── Update step status ──
            steps[i]["status"] = step_status
            update_workflow(workflow_id, {"steps": steps})

            if step_status == "COMPLETED":
                emit_event(workflow_id, "chat:step_complete", "ExecutionAgent",
                          f"🎉 Completed: {step_name}")
                AuditService.log_step_complete(workflow_id, step_name, assigned_agent)
            else:
                has_escalation = True
                emit_event(workflow_id, "chat:step_escalated", "RecoveryAgent",
                          f"🚨 Escalated: {step_name}")
                AuditService.log_step_escalated(workflow_id, step_name)

            # ── HEALTH CHECK: Run HealthMonitor after each step ──
            elapsed = (datetime.now(timezone.utc) - workflow_start_time).total_seconds() / 60
            completed_count = sum(1 for s in steps if s.get("status") == "COMPLETED")
            failed_count = sum(1 for s in steps if s.get("status") in ("FAILED", "ESCALATED"))

            health = run_health_monitor({
                "total_steps": len(steps),
                "completed_steps": completed_count,
                "failed_steps": failed_count,
                "escalated_steps": sum(1 for s in steps if s.get("status") == "ESCALATED"),
                "elapsed_minutes": round(elapsed, 1),
                "current_step_name": step_name,
            }, workflow_id, emit_event)

            AuditService.log_health_check(
                workflow_id,
                health.get("status", "HEALTHY"),
                health.get("reason", ""),
                health.get("recommendation", "continue"),
            )

            # ── Handle HealthMonitor recommendations ──
            if health.get("recommendation") == "escalate":
                emit_event(workflow_id, "chat:message", "HealthMonitorAgent",
                          "🚨 Health monitor recommends escalation — workflow at risk")
            elif health.get("recommendation") == "reroute":
                bottleneck = health.get("bottleneck_step", "unknown")
                emit_event(workflow_id, "chat:message", "HealthMonitorAgent",
                          f"🔄 Health monitor recommends rerouting around: {bottleneck}")
                AuditService.log_reroute(workflow_id, bottleneck, "current", "delegate",
                                        health.get("reason", "SLA risk"))

    except Exception as e:
        print(f"Execution error: {e}")
        traceback.print_exc()
        update_workflow(workflow_id, {"status": "FAILED"})
        emit_event(workflow_id, "workflow:failed", "Orchestrator",
                  f"❌ Execution failed: {str(e)[:300]}")
        return
    finally:
        try:
            mcp_client.stop()
        except Exception:
            pass

    # ══════════════════════════════════════
    # PHASE 3: FINALIZE
    # ══════════════════════════════════════
    final_status = "ESCALATED" if has_escalation else "COMPLETED"
    update_workflow(workflow_id, {"status": final_status})

    emoji = "🎉" if final_status == "COMPLETED" else "⚠️"
    emit_event(workflow_id, "workflow:complete", "Orchestrator",
              f"{emoji} Workflow {final_status.lower()}",
              {"totalSteps": len(steps), "status": final_status})
    AuditService.log_workflow_complete(workflow_id, len(steps), final_status)
