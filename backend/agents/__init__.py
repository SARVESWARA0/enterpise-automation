"""
Enterprise Autopilot — Agent Package.
Exports all 4 specialized agents + shared utilities.
"""
import os
import sys

from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

from agents.model_provider import get_model

load_dotenv()


def get_mcp_client():
    """Create an MCPClient pointing at our MCP tool server via stdio."""
    python_exe = sys.executable
    mcp_server_path = os.path.join(os.path.dirname(__file__), "..", "mcp_server.py")
    return MCPClient(
        lambda: stdio_client(StdioServerParameters(
            command=python_exe,
            args=[mcp_server_path],
        ))
    )


