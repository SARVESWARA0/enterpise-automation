"""
Workflow Interpreter Agent — converts user intent into a structured step plan.
Replaces the old PlannerAgent. Supports all 3 mandatory scenarios + surprise workflows.
"""
import json
import uuid
import traceback

from strands import Agent
from .base import get_model, PRISMA_SCHEMA


INTERPRETER_PROMPT = f"""You are the Workflow Interpreter Agent for an enterprise automation system.
Your job is to convert any high-level goal into a structured, executable step plan.

Available MCP tools (use these names in toolName):
- execute_sql: Run PostgreSQL queries
- send_email: Send emails
- create_email_account: Provision email accounts
- create_email_account_tool: Create company email
- create_jira_task: Create JIRA tickets
- create_jira_account_tool: Create JIRA access
- create_hr_account_tool: Create HR records
- create_calendar_event: Schedule meetings
- schedule_meeting_tool: Schedule orientation meetings
- assign_buddy_tool: Assign mentor/buddy
- update_employee_status: Update HR records
- find_delegate: Find team members
- check_sla_status: Check SLA compliance
- escalate_to_it_tool: Escalate IT issues
- send_onboarding_email_tool: Send onboarding emails
- send_summary_email_tool: Send summary emails
- create_task_tool: Create tasks
- reroute_approval_tool: Reroute stuck approvals
- log_audit_entry: Write audit logs

Database schema:
```prisma
{PRISMA_SCHEMA}
```

RULES:
1. Return ONLY a valid JSON array. No explanatory text before or after.
2. Each element must have exactly these fields:
   - "stepName": human-readable step name
   - "stepDescription": detailed instruction mentioning which tool and exact parameters
   - "stepType": one of "action", "decision", "verification", "notification"
   - "assignedAgent": one of "ExecutionAgent", "DecisionAgent", "VerificationAgent"
   - "toolName": the MCP tool name to use (or null if no tool needed)
   - "dependencyOrder": integer starting from 0
   - "fallbackBehavior": one of "retry", "escalate", "skip", "reroute"

3. For employee onboarding, include: create email, create JIRA access, create HR record, assign buddy, schedule orientation, send onboarding email
4. For meeting-to-action, include: extract tasks from transcript, decide owners (use DecisionAgent), create tasks, send summary
5. For SLA breach prevention, include: check SLA status, find bottleneck, reroute if needed, log audit
6. For any other intent, dynamically create appropriate steps

Example:
[
  {{"stepName": "Create email account", "stepDescription": "Use create_email_account_tool with name='John Doe'", "stepType": "action", "assignedAgent": "ExecutionAgent", "toolName": "create_email_account_tool", "dependencyOrder": 0, "fallbackBehavior": "retry"}},
  {{"stepName": "Verify email created", "stepDescription": "Check the result of email creation", "stepType": "verification", "assignedAgent": "VerificationAgent", "toolName": null, "dependencyOrder": 1, "fallbackBehavior": "escalate"}}
]"""


def run_interpreter(intent: str, workflow_id: str, emit_fn) -> list[dict] | None:
    """Generate workflow steps from user intent.

    Args:
        intent: The high-level goal / workflow description.
        workflow_id: Current workflow ID for event emission.
        emit_fn: Callable(workflow_id, event_type, agent_name, message, data) for SSE.

    Returns:
        List of step dicts, or None on failure.
    """
    emit_fn(workflow_id, "chat:agent_assigned", "InterpreterAgent", "📋 Interpreting workflow intent...")

    model = get_model()
    interpreter = Agent(
        model=model,
        name="InterpreterAgent",
        system_prompt=INTERPRETER_PROMPT,
        callback_handler=None,
    )

    try:
        result = interpreter(f"Generate steps for: '{intent}'")
        response_text = str(result)

        emit_fn(workflow_id, "chat:message", "InterpreterAgent", response_text[:800])

        # Extract JSON array from response
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
                    "stepType": s.get("stepType", "action"),
                    "assignedAgent": s.get("assignedAgent", "ExecutionAgent"),
                    "toolName": s.get("toolName"),
                    "dependencyOrder": s.get("dependencyOrder", i),
                    "fallbackBehavior": s.get("fallbackBehavior", "retry"),
                    "status": "PENDING",
                    "retryCount": 0,
                })

            emit_fn(
                workflow_id, "chat:plan_generated", "InterpreterAgent",
                f"✅ Generated {len(steps)}-step plan.",
                {"steps": [{"stepName": s["stepName"], "stepDescription": s["stepDescription"],
                            "stepType": s["stepType"], "assignedAgent": s["assignedAgent"]} for s in steps]},
            )
            return steps

        emit_fn(workflow_id, "chat:error", "InterpreterAgent", "❌ No valid JSON plan found in response")
        return None

    except Exception as e:
        traceback.print_exc()
        emit_fn(workflow_id, "chat:error", "InterpreterAgent", f"Planning failed: {str(e)[:300]}")
        return None
