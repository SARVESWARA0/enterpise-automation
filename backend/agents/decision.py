"""
Decision Agent — decides owners, chooses branches, interprets context.
Never guesses if information is unclear; flags for clarification instead.
"""
import json
import traceback

from strands import Agent
from .base import get_model, PRISMA_SCHEMA


DECISION_PROMPT = f"""You are the Decision Agent for an enterprise automation system.
Your role is to make ownership and routing decisions.

You will be given a task that needs an owner/assignee or a branching decision.

RULES:
1. If you can determine the correct owner/decision with confidence, return it.
2. If information is unclear or ambiguous, DO NOT GUESS. Return needs_clarification=true.
3. Always return valid JSON with exactly these fields:
   - "decision": the chosen value (owner name, branch choice, etc.)
   - "reason": why you chose this
   - "confidence": "high", "medium", or "low"
   - "needs_clarification": true/false
   - "clarification_question": string (only if needs_clarification is true)

Database schema:
```prisma
{PRISMA_SCHEMA}
```

Example responses:
{{"decision": "alice.johnson@company.com", "reason": "Alice is in Engineering and is ACTIVE", "confidence": "high", "needs_clarification": false, "clarification_question": null}}
{{"decision": null, "reason": "Multiple candidates found, no clear indication of who should own this", "confidence": "low", "needs_clarification": true, "clarification_question": "Who should be assigned: Alice Johnson (Engineering) or David Chen (Engineering)?"}}
"""


def run_decision_agent(context: str, workflow_id: str, emit_fn) -> dict:
    """Run the Decision Agent to make an ownership or routing decision.

    Args:
        context: Description of what needs to be decided.
        workflow_id: Current workflow ID.
        emit_fn: SSE event emitter.

    Returns:
        Decision dict with keys: decision, reason, confidence, needs_clarification, clarification_question.
    """
    emit_fn(workflow_id, "chat:agent_assigned", "DecisionAgent", "🧭 Making routing decision...")

    model = get_model()
    agent = Agent(
        model=model,
        name="DecisionAgent",
        system_prompt=DECISION_PROMPT,
        callback_handler=None,
    )

    try:
        result = agent(f"Make a decision for: {context}")
        response_text = str(result)

        # Parse JSON from response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            decision = json.loads(response_text[start:end])
            emit_fn(workflow_id, "chat:message", "DecisionAgent",
                    f"🧭 Decision: {decision.get('decision', 'N/A')} (confidence: {decision.get('confidence', 'unknown')})")
            return decision

        # Fallback: return needs_clarification
        return {
            "decision": None,
            "reason": "Could not parse decision response",
            "confidence": "low",
            "needs_clarification": True,
            "clarification_question": "Unable to determine, please specify manually.",
        }

    except Exception as e:
        traceback.print_exc()
        emit_fn(workflow_id, "chat:error", "DecisionAgent", f"Decision failed: {str(e)[:200]}")
        return {
            "decision": None,
            "reason": f"Error: {str(e)[:200]}",
            "confidence": "low",
            "needs_clarification": True,
            "clarification_question": "Decision agent encountered an error.",
        }
