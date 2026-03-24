"""
Workflow Health Monitor Agent — monitors SLA, delays, and stuck steps.
Can trigger rerouting or escalation before SLA breach.
"""
import json
import traceback

from strands import Agent
from .base import get_model


HEALTH_MONITOR_PROMPT = """You are the Workflow Health Monitor Agent for an enterprise automation system.
You monitor workflow progress and detect potential SLA breaches or bottlenecks.

You will receive workflow state including:
- Total steps and completed steps
- Failed/escalated steps
- Time elapsed since workflow start
- Current step status

Analyze and return valid JSON with these fields:
- "status": one of "HEALTHY", "AT_RISK", "BREACH"
- "reason": explanation of the assessment
- "recommendation": one of "continue", "reroute", "escalate", "alert_admin"
- "bottleneck_step": name of the bottleneck step if any (null otherwise)
- "sla_hours_remaining": estimated hours until SLA breach (-1 if already breached)

Decision guidelines:
- HEALTHY: on track, no issues
- AT_RISK: more than 50% of steps failed/escalated, or elapsed time > 50% of SLA
- BREACH: SLA already breached, or all retries exhausted, or workflow stuck

Example:
{"status": "AT_RISK", "reason": "2 out of 6 steps have failed, JIRA provisioning is a bottleneck", "recommendation": "reroute", "bottleneck_step": "Create JIRA access", "sla_hours_remaining": 4}
"""


def run_health_monitor(workflow_state: dict, workflow_id: str, emit_fn) -> dict:
    """Run the Health Monitor Agent to assess workflow health.

    Args:
        workflow_state: Dict with keys: total_steps, completed_steps, failed_steps,
                        escalated_steps, elapsed_minutes, current_step_name.
        workflow_id: Current workflow ID.
        emit_fn: SSE event emitter.

    Returns:
        Health assessment dict.
    """
    emit_fn(workflow_id, "chat:agent_assigned", "HealthMonitorAgent",
            "📊 Checking workflow health...")

    model = get_model()
    agent = Agent(
        model=model,
        name="HealthMonitorAgent",
        system_prompt=HEALTH_MONITOR_PROMPT,
        callback_handler=None,
    )

    try:
        state_summary = json.dumps(workflow_state)
        result = agent(f"Assess workflow health: {state_summary}")
        response_text = str(result)

        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            assessment = json.loads(response_text[start:end])
            status = assessment.get("status", "HEALTHY")
            emoji = "✅" if status == "HEALTHY" else "⚠️" if status == "AT_RISK" else "🚨"
            emit_fn(workflow_id, "chat:message", "HealthMonitorAgent",
                    f"{emoji} Health: {status} — {assessment.get('reason', '')}")
            return assessment

        return {"status": "HEALTHY", "reason": "Unable to parse assessment",
                "recommendation": "continue", "bottleneck_step": None, "sla_hours_remaining": 24}

    except Exception as e:
        traceback.print_exc()
        emit_fn(workflow_id, "chat:error", "HealthMonitorAgent",
                f"Health check failed: {str(e)[:200]}")
        return {"status": "HEALTHY", "reason": f"Error: {str(e)[:100]}",
                "recommendation": "continue", "bottleneck_step": None, "sla_hours_remaining": 24}
