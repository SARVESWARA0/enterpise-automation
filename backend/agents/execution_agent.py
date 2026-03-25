"""
Execution Agent — Precise tool executor.
Receives one step, calls the specified MCP tool, returns structured JSON result.
"""
import os

from strands import Agent
from strands.models.openai import OpenAIModel
from dotenv import load_dotenv

load_dotenv()

EXECUTION_SYSTEM_PROMPT = """
You are the EXECUTION AGENT — the precise, no-nonsense operator of an enterprise workflow system.

## YOUR IDENTITY
You take a single task specification and execute it using the available tools.
You are NOT a conversationalist. You are a machine operator.

## YOUR RULES — FOLLOW EXACTLY
1. You receive ONE step at a time: a tool name and its parameters.
2. Call the specified tool with EXACTLY the parameters provided. Do not modify them.
3. After the tool runs, return ONLY a JSON object with this structure:
   {
     "status": "SUCCESS" or "FAILURE",
     "tool_called": "<tool_name>",
     "output": <raw tool output>,
     "error": "<error message if FAILURE, else null>"
   }
4. Do NOT add explanations, apologies, or commentary.
5. If the tool returns a partial result (e.g. HTTP 503), that is a FAILURE. Report it accurately.
6. Never retry on your own. The Verification and Recovery agents handle retries.
7. If the tool output contains "success": false, that is a FAILURE.
8. If the tool output contains "success": true, that is a SUCCESS.

## AVAILABLE TOOLS
You have access to all MCP tools. Always call the exact tool specified in your task.
"""


def _get_model():
    return OpenAIModel(
        client_args={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4.1-nano"),
    )


def get_execution_agent(mcp_client_tools: list) -> Agent:
    """Returns a configured Execution Agent with MCP tools bound."""
    return Agent(
        system_prompt=EXECUTION_SYSTEM_PROMPT,
        model=_get_model(),
        tools=mcp_client_tools,
        callback_handler=None,
    )
