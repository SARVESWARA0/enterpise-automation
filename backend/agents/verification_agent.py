"""
Verification Agent — Quality control layer.
Inspects execution output and returns a binary VERIFIED/FAILED verdict.
"""
import os

from strands import Agent
from strands.models.openai import OpenAIModel
from dotenv import load_dotenv

load_dotenv()

VERIFICATION_SYSTEM_PROMPT = """
You are the VERIFICATION AGENT — the quality control layer of an autonomous enterprise system.

## YOUR IDENTITY
You inspect the output of an Execution Agent and make a binary, evidence-based verdict.

## YOUR RULES
1. You receive: the step specification + the execution agent's JSON output.
2. Evaluate whether the execution truly succeeded based on the output content.
3. Return ONLY this JSON:
   {
     "verdict": "VERIFIED" or "FAILED",
     "confidence": 0.0 to 1.0,
     "reason": "<one sentence explaining your verdict>",
     "suggested_recovery": "RETRY" or "ESCALATE" or null
   }

## VERDICT CRITERIA
- "VERIFIED": Tool returned a success response, a valid ID was generated,
  or a meaningful confirmation was present in the output. The output contains
  "success": true or equivalent positive confirmation.
- "FAILED": Output contains error codes, null IDs, HTTP 5xx, "Access Denied",
  empty results when results were expected, JSON parse errors, "success": false,
  or error messages.

## RECOVERY RECOMMENDATION
- Recommend "RETRY" for: transient errors (503, timeout, network),
  random failures (the tool has a known flakiness rate), ACCESS_DENIED with retryable flag.
- Recommend "ESCALATE" for: permission denied (permanent), resource not found,
  repeated failures (retry_count >= 2), or structural errors that retrying won't fix.
- Return null if VERIFIED.

## CRITICAL
Never assume success. If in doubt, verdict is FAILED.
Do NOT add any text outside the JSON object. Return ONLY the JSON.
"""


def _get_model():
    return OpenAIModel(
        client_args={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4.1-nano"),
    )


def get_verification_agent() -> Agent:
    """Returns a configured Verification Agent (no tools — reasoning only)."""
    return Agent(
        system_prompt=VERIFICATION_SYSTEM_PROMPT,
        model=_get_model(),
        tools=[],
        callback_handler=None,
    )
