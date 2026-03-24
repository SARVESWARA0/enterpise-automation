"""
Recovery Agent — handles failures by deciding to retry or escalate.
Enhanced to use escalation tools when appropriate.
"""
from strands import Agent
from .base import get_model


def create_recovery_agent() -> Agent:
    """Create a Recovery Agent instance.

    Returns:
        A configured Strands Agent.
    """
    return Agent(
        model=get_model(),
        name="RecoveryAgent",
        system_prompt="""You are a Recovery Agent for an enterprise automation system.
Given a failed step, analyze the failure and decide the recovery action.

Consider:
- Transient errors (network timeout, rate limit, 503) → RETRY
- Permanent errors (access denied, invalid config, missing prerequisites) → ESCALATE
- If retry count is already at 2 or more → always ESCALATE

Reply with EXACTLY one of:
- RETRY: <reason why a retry might succeed>
- ESCALATE: <reason why this needs human/IT intervention>

Do not add any other text.""",
        callback_handler=None,
    )
