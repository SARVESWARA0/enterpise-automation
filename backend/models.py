"""
Enterprise Autopilot — Shared Pydantic Models.
Contracts used by all agents and the orchestrator.
"""
from pydantic import BaseModel
from typing import Optional, Literal, Any
from datetime import datetime, timezone


class WorkflowStep(BaseModel):
    step_id: int
    name: str
    tool_name: str
    parameters: dict
    assigned_agent: str = "execution"
    depends_on: list[int] = []
    fallback: Literal["ESCALATE", "RETRY", "SKIP"] = "ESCALATE"
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "ESCALATED", "SKIPPED", "RETRIED"] = "PENDING"
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0


class WorkflowPlan(BaseModel):
    workflow_id: str
    trigger: str
    employee_name: Optional[str] = None
    steps: list[WorkflowStep] = []
    created_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class SSEEvent(BaseModel):
    event_type: str
    agent: str
    step_id: Optional[str] = None
    data: Any = None
    timestamp: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class OnboardingRequest(BaseModel):
    name: str
    email: str
    role: str
    department: str
    trigger: str = "employee_onboarding"


class WorkflowStartRequest(BaseModel):
    """Generic workflow trigger."""
    request: str
    trigger: str = "manual"
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    scheduled_at: Optional[str] = None  # ISO datetime — triggers workflow at this time instead of immediately


class MeetingToActionRequest(BaseModel):
    transcript: str
    participants: list[str] = []
    source: str = "manual"
    meeting_date: Optional[str] = None


class TaskPatchRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[Literal["pending", "in_progress", "completed", "blocked", "ambiguous"]] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    reason_for_creation: Optional[str] = None
    confidence_score: Optional[float] = None


class AssignTaskOwnerRequest(BaseModel):
    owner: str
    actor: str = "manual_reviewer"
    note: Optional[str] = None


class CreateApprovalRequest(BaseModel):
    request_type: str
    current_approver: Optional[Any] = None
    sla_deadline: str
    sla_duration_hours: Optional[int] = None
    priority: Optional[str] = "High"
    auto_trigger_monitor: bool = True
    reminder_interval_hours: Optional[int] = None
    grace_period_hours: Optional[int] = None
    allow_auto_reroute: bool = True
    if_breached: Optional[str] = None
    event_summary: Optional[str] = None


class RerouteApprovalRequest(BaseModel):
    delegate_approver: str
    reroute_reason: str
    actor: str = "manual_reviewer"
