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
