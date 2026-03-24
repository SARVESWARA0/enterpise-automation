"""
Audit Service — deterministic system-level audit logging.
NOT an agent. Writes structured logs to the state manager.
"""
from state_manager import append_audit_log


class AuditService:
    """System service for writing structured audit entries."""

    @staticmethod
    def log_workflow_start(workflow_id: str, intent: str):
        append_audit_log(workflow_id, {
            "decision": "workflow_started",
            "reason": f"Goal: {intent}",
            "actionTaken": "Orchestrator initialized",
            "agentName": "Orchestrator",
            "status": "running",
        })

    @staticmethod
    def log_workflow_complete(workflow_id: str, total_steps: int, final_status: str):
        append_audit_log(workflow_id, {
            "decision": final_status.lower(),
            "reason": f"Workflow finished: {final_status}",
            "actionTaken": f"All {total_steps} steps processed",
            "agentName": "Orchestrator",
            "status": final_status.lower(),
        })

    @staticmethod
    def log_step_start(workflow_id: str, step_name: str, agent_name: str):
        append_audit_log(workflow_id, {
            "decision": "step_started",
            "reason": f"Starting step: {step_name}",
            "actionTaken": f"Assigned to {agent_name}",
            "agentName": agent_name,
            "status": "running",
        })

    @staticmethod
    def log_step_complete(workflow_id: str, step_name: str, agent_name: str):
        append_audit_log(workflow_id, {
            "decision": "completed",
            "reason": f"Step '{step_name}' succeeded",
            "actionTaken": "Step finished",
            "agentName": agent_name,
            "status": "completed",
        })

    @staticmethod
    def log_step_escalated(workflow_id: str, step_name: str, reason: str = ""):
        append_audit_log(workflow_id, {
            "decision": "escalated",
            "reason": f"Step '{step_name}' escalated" + (f": {reason}" if reason else ""),
            "actionTaken": "Escalated",
            "agentName": "RecoveryAgent",
            "status": "escalated",
        })

    @staticmethod
    def log_decision(workflow_id: str, step_name: str, decision: str, reason: str):
        append_audit_log(workflow_id, {
            "decision": decision,
            "reason": reason,
            "actionTaken": f"Decision for '{step_name}'",
            "agentName": "DecisionAgent",
            "status": "completed",
        })

    @staticmethod
    def log_clarification(workflow_id: str, step_name: str, summary: str):
        append_audit_log(workflow_id, {
            "decision": "awaiting_clarification",
            "reason": summary,
            "actionTaken": f"Flagged '{step_name}' for clarification",
            "agentName": "ClarificationAgent",
            "status": "awaiting_clarification",
        })

    @staticmethod
    def log_health_check(workflow_id: str, status: str, reason: str, recommendation: str):
        append_audit_log(workflow_id, {
            "decision": f"health_{status.lower()}",
            "reason": reason,
            "actionTaken": f"Recommendation: {recommendation}",
            "agentName": "HealthMonitorAgent",
            "status": status.lower(),
        })

    @staticmethod
    def log_tool_call(workflow_id: str, tool_name: str, agent_name: str, status: str):
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Tool: {tool_name}",
            "actionTaken": tool_name,
            "agentName": agent_name,
            "toolName": tool_name,
            "status": status,
        })

    @staticmethod
    def log_reroute(workflow_id: str, step_name: str, from_agent: str, to_agent: str, reason: str):
        append_audit_log(workflow_id, {
            "decision": "rerouted",
            "reason": reason,
            "actionTaken": f"Rerouted '{step_name}' from {from_agent} to {to_agent}",
            "agentName": "HealthMonitorAgent",
            "status": "rerouted",
        })
