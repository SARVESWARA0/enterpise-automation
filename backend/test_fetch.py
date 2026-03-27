import os
import sys
import asyncio
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession

async def fetch_tools():
    mcp_server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[mcp_server_path],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [{"name": t.name, "description": t.description} for t in tools.tools]

print(asyncio.run(fetch_tools()))
