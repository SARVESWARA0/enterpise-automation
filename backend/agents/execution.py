"""
Execution Agent — calls MCP tools to perform actual business operations.
Narrow scope: call the tool, return the result. No explanations.
"""
from strands import Agent
from .base import get_model, PRISMA_SCHEMA


def create_execution_agent(workflow_id: str, mcp_client) -> Agent:
    """Create an Execution Agent instance bound to a specific workflow and MCP client.

    Args:
        workflow_id: The workflow ID (injected into system prompt for tool calls).
        mcp_client: An active MCPClient instance.

    Returns:
        A configured Strands Agent.
    """
    return Agent(
        model=get_model(),
        name="ExecutionAgent",
        system_prompt=f"""You are an enterprise Execution Agent. Call the appropriate MCP tool to complete the task.
Always pass workflow_id='{workflow_id}' to every tool that accepts it.
Return the raw tool result. Do NOT explain — just call the tool and return its output.

Database schema:
```prisma
{PRISMA_SCHEMA}
```""",
        tools=[mcp_client],
        callback_handler=None,
    )
