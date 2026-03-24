"""
Clarification Agent — handles ambiguous cases by flagging them clearly
instead of guessing. Marks steps as AWAITING_CLARIFICATION.
"""
import json
import traceback

from strands import Agent
from .base import get_model


CLARIFICATION_PROMPT = """You are the Clarification Agent for an enterprise automation system.
You are called when a Decision Agent or other component cannot determine the correct action
because information is ambiguous or missing.

Your job is to:
1. Summarize what is unclear in plain language
2. Suggest possible resolutions
3. Generate a structured clarification request

Return valid JSON with these fields:
- "summary": one-sentence summary of the ambiguity
- "details": longer explanation of what is unclear
- "suggestions": list of possible resolutions (up to 3)
- "blocking": true if the workflow cannot proceed without resolution, false if it can be skipped

Example:
{"summary": "Task owner is ambiguous", "details": "The meeting transcript mentions both Alice and Bob as potential owners for the Q4 report task.", "suggestions": ["Assign to Alice (she owns similar tasks)", "Assign to Bob (he was mentioned last)", "Assign to both as co-owners"], "blocking": false}
"""


def run_clarification_agent(context: str, workflow_id: str, emit_fn) -> dict:
    """Run the Clarification Agent for ambiguous cases.

    Args:
        context: Description of the ambiguity.
        workflow_id: Current workflow ID.
        emit_fn: SSE event emitter.

    Returns:
        Clarification dict with keys: summary, details, suggestions, blocking.
    """
    emit_fn(workflow_id, "chat:agent_assigned", "ClarificationAgent",
            "🔍 Analyzing ambiguous input...")

    model = get_model()
    agent = Agent(
        model=model,
        name="ClarificationAgent",
        system_prompt=CLARIFICATION_PROMPT,
        callback_handler=None,
    )

    try:
        result = agent(f"Clarify this ambiguity: {context}")
        response_text = str(result)

        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            clarification = json.loads(response_text[start:end])
            emit_fn(workflow_id, "chat:message", "ClarificationAgent",
                    f"🔍 Clarification needed: {clarification.get('summary', 'Unknown')}")
            return clarification

        return {
            "summary": "Unable to parse clarification",
            "details": response_text[:500],
            "suggestions": [],
            "blocking": False,
        }

    except Exception as e:
        traceback.print_exc()
        emit_fn(workflow_id, "chat:error", "ClarificationAgent",
                f"Clarification failed: {str(e)[:200]}")
        return {
            "summary": f"Error during clarification: {str(e)[:100]}",
            "details": str(e),
            "suggestions": [],
            "blocking": False,
        }
