"""
Verification Agent — checks whether a tool execution actually succeeded.
Returns VERIFIED or FAILED with a reason.
"""
from strands import Agent
from .base import get_model


def create_verification_agent() -> Agent:
    """Create a Verification Agent instance.

    Returns:
        A configured Strands Agent.
    """
    return Agent(
        model=get_model(),
        name="VerificationAgent",
        system_prompt="""You are a Verification Agent for an enterprise automation system.
Given a tool execution result, determine whether the operation actually succeeded.

Analyze the JSON output carefully:
- Check if "success" is true
- Check for error messages
- Check if expected data fields are present and populated

Reply with EXACTLY one of:
- VERIFIED: <reason why this succeeded>
- FAILED: <reason why this failed>

Do not add any other text.""",
        callback_handler=None,
    )
