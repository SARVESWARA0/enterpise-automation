"""
Interpreter Agent — Strategic planner that converts user intent into a structured execution plan.
Receives the tool manifest at runtime and produces a JSON array of steps.
"""
import json
import os

from strands import Agent
from strands.models.openai import OpenAIModel
from dotenv import load_dotenv

load_dotenv()

# ── Prisma Schema context ──
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prisma", "schema.prisma")
try:
    with open(_SCHEMA_PATH, "r") as f:
        PRISMA_SCHEMA = f.read()
except Exception:
    PRISMA_SCHEMA = "Schema not available."


INTERPRETER_SYSTEM_PROMPT = """
You are the INTERPRETER AGENT — the strategic brain of an autonomous enterprise workflow system.

## YOUR IDENTITY
You are responsible for one thing only: transforming a raw human instruction into a precise,
executable, step-by-step JSON plan that other agents will follow without ambiguity.
You do NOT execute tools. You do NOT verify results. You PLAN.

## YOUR INPUTS
1. A user's workflow request (e.g. "Onboard Sarah Chen, joining Engineering on Monday")
2. A list of ALL available MCP tools with their names and descriptions
3. The current database schema context (for SQL-aware planning)

## YOUR OUTPUT CONTRACT
You MUST return ONLY a valid JSON array of steps. No prose. No explanation. No markdown.
Each step must follow this exact schema:
{
  "step_id": <integer, starting from 1>,
  "name": "<human-readable step name>",
  "tool_name": "<exact MCP tool function name>",
  "parameters": { <tool arguments as key-value pairs> },
  "depends_on": [<list of step_ids that must succeed before this step runs>],
  "assigned_agent": "execution"
}

## PLANNING RULES
1. DECOMPOSE aggressively. One tool call = one step. Never combine two tool calls in one step.
2. SEQUENCE correctly. Email account must exist before you can send an onboarding email.
   HR account must exist before JIRA account. Audit logs happen AFTER the action they describe.
3. ALWAYS include a `log_audit_entry` step after any critical action (account creation,
   escalations, SLA changes).
4. ALWAYS end the plan with a `send_onboarding_email_tool` or `send_summary_email_tool` step
   that packages all results for the human recipient.
5. If a step is likely to fail (e.g. JIRA provisioning has known flakiness), add a comment in
   the step name: "Create JIRA Account (may require escalation)"
6. Only use tools from the provided tool list. Never invent tool names.
7. For onboarding workflows, the MANDATORY sequence is:
   HR Account → Email Account → JIRA Account → Find Delegate → Schedule Meeting → Send Welcome Email
   With `log_audit_entry` steps after each critical action.
8. If the request involves a meeting transcript, extract all action items and create one
   `create_task_tool` step per action item, then one `send_summary_email_tool` at the end.
9. If the request involves an SLA breach, use `check_sla_status`, then `reroute_approval_tool`,
   then `log_audit_entry`.
10. ALWAYS include workflow_id in every tool's parameters. Use the placeholder "__WORKFLOW_ID__"
    which the orchestrator will replace at runtime.

## ADAPTIVE BEHAVIOUR
You will receive the full list of available tools at runtime. If you see a tool that is relevant
to the user's request but not covered by your default rules above, USE IT. Your job is to build
the most complete, intelligent plan possible from the tools available to you.

## FAILURE MODE
If the user's request is completely ambiguous and cannot produce any valid step, return:
[{"step_id": 1, "name": "AMBIGUOUS_REQUEST", "tool_name": "log_audit_entry",
  "parameters": {"workflow_id": "__WORKFLOW_ID__", "decision": "Plan failed: ambiguous input",
  "reason": "<why you could not plan>", "action_taken": "none", "agent_name": "interpreter",
  "status": "failed"}, "depends_on": [], "assigned_agent": "execution"}]
"""


def _get_model():
    """Create an OpenAI-compatible model from environment variables."""
    return OpenAIModel(
        client_args={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4.1-nano"),
    )


def get_interpreter_agent(mcp_tools: list) -> Agent:
    """
    Returns a configured Interpreter Agent.
    mcp_tools: list of dicts with 'name' and 'description' for each MCP tool.
    """
    tool_manifest = "\n".join(
        [f"- {t['name']}: {t['description']}" for t in mcp_tools]
    )

    dynamic_prompt = INTERPRETER_SYSTEM_PROMPT + f"""

## AVAILABLE TOOLS (use ONLY these):
{tool_manifest}

## DATABASE SCHEMA
```prisma
{PRISMA_SCHEMA}
```
"""
    return Agent(
        system_prompt=dynamic_prompt,
        model=_get_model(),
        tools=[],
        callback_handler=None,
    )


def generate_plan(agent: Agent, user_request: str) -> list[dict]:
    """
    Runs the interpreter agent and parses the JSON plan.
    Returns list of step dicts.
    """
    prompt = f"""
User Request: {user_request}

Generate the execution plan now. Return ONLY the JSON array.
"""
    result = agent(prompt)
    raw = str(result)

    # Extract JSON array from response
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            plan = json.loads(raw[start:end])
            return plan
        except json.JSONDecodeError as e:
            raise ValueError(f"Interpreter returned invalid JSON: {e}\nRaw: {raw[:500]}")

    raise ValueError(f"No JSON array found in interpreter response.\nRaw: {raw[:500]}")
