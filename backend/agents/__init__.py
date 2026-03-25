"""
Enterprise Autopilot — Agent Package.
Exports all 4 specialized agents + shared utilities.
"""
import os
import sys

from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()


def get_model():
    """Create an OpenAI-compatible model from environment variables."""
    return OpenAIModel(
        client_args={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4.1-nano"),
    )


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


# ── Tool manifest for the Interpreter Agent ──
TOOL_MANIFEST = [
    {"name": "execute_sql", "description": "Execute any SQL query against the PostgreSQL database."},
    {"name": "send_email", "description": "Send an email to the specified recipient."},
    {"name": "create_email_account", "description": "Create an enterprise email account for a new employee."},
    {"name": "create_email_account_tool", "description": "Create a company email account for a new employee."},
    {"name": "create_jira_task", "description": "Create a JIRA task / ticket."},
    {"name": "create_jira_account_tool", "description": "Create access for employee in JIRA system."},
    {"name": "create_hr_account_tool", "description": "Create employee record in HR system."},
    {"name": "assign_buddy_tool", "description": "Assign a mentor/buddy to the employee based on experience match."},
    {"name": "schedule_meeting_tool", "description": "Schedule orientation meeting."},
    {"name": "escalate_to_it_tool", "description": "Handle escalation when system access fails."},
    {"name": "send_onboarding_email_tool", "description": "Send the onboarding welcome email to the employee using SMTP."},
    {"name": "create_task_tool", "description": "Create a task from meeting action items or other sources."},
    {"name": "send_summary_email_tool", "description": "Send a summary email (e.g., meeting action items summary)."},
    {"name": "reroute_approval_tool", "description": "Reroute a stuck approval or task to a different agent or delegate."},
    {"name": "check_sla_status", "description": "Check SLA compliance for a task or process."},
    {"name": "find_delegate", "description": "Find a suitable delegate/buddy in a department."},
    {"name": "update_employee_status", "description": "Update an employee's status in the HR system."},
    {"name": "log_audit_entry", "description": "Write an entry to the enterprise audit trail."},
]
