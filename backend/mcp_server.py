"""
Enterprise Autopilot — MCP Tool Server.
Exposes all enterprise tools via the Model Context Protocol (fastmcp).
Run as a subprocess via stdio transport; consumed by the ExecutionAgent via MCPClient.
"""
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, date

import psycopg2
from psycopg2.extras import RealDictCursor
from fastmcp import FastMCP

# ── Ensure state_manager is importable ──
sys.path.insert(0, os.path.dirname(__file__))
from state_manager import (
    update_employee, list_employees,
    append_audit_log, append_stream_event,
)

mcp = FastMCP("Enterprise Autopilot Tools")

DB_URL = os.getenv("DATABASE_URL", os.getenv("DB_URL", "postgresql://postgres:1234@localhost:5432/enterprise_autopilot"))


def _json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# ────────────────────────────────────────
# TOOL: execute_sql
# ────────────────────────────────────────
@mcp.tool()
def execute_sql(query: str, workflow_id: str = "") -> str:
    """Execute any SQL query against the PostgreSQL database.

    Args:
        query: The SQL query to execute (SELECT, INSERT, UPDATE, DELETE).
        workflow_id: The workflow ID for audit tracking.
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        rows = []
        if cursor.description:
            rows = cursor.fetchall()
        conn.commit()
        cursor.close()
        conn.close()
        result = {"success": True, "rowCount": cursor.rowcount, "data": rows, "tool": "execute_sql"}
    except Exception as e:
        result = {"success": False, "error": str(e), "tool": "execute_sql"}

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"SQL: {query[:80]}",
            "actionTaken": "execute_sql", "agentName": "ExecutionAgent",
            "toolName": "execute_sql", "status": "completed" if result["success"] else "failed",
        })
    return json.dumps(result, default=_json_serial)


# ────────────────────────────────────────
# TOOL: send_email
# ────────────────────────────────────────
@mcp.tool()
def send_email(to: str, subject: str, body: str, workflow_id: str = "") -> str:
    """Send an email to the specified recipient.

    Args:
        to: Recipient email address.
        subject: Subject line.
        body: Email body text.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.3)
    if random.random() < 0.10:
        return json.dumps({"success": False, "error": "SMTP timeout", "tool": "send_email"})

    result = {
        "success": True, "messageId": f"msg-{uuid.uuid4().hex[:8]}",
        "to": to, "subject": subject, "tool": "send_email",
        "message": f"Email sent to {to}",
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Email to {to}: {subject}",
            "actionTaken": "send_email", "agentName": "ExecutionAgent",
            "toolName": "send_email", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_email_account
# ────────────────────────────────────────
@mcp.tool()
def create_email_account(employee_name: str, employee_email: str, department: str, workflow_id: str = "") -> str:
    """Create an enterprise email account for a new employee.

    Args:
        employee_name: Full name.
        employee_email: Desired email address.
        department: Department of the employee.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.4)
    if random.random() < 0.10:
        return json.dumps({"success": False, "error": "AD sync failed", "tool": "create_email_account"})

    result = {
        "success": True, "email": employee_email,
        "accountId": f"acc-{uuid.uuid4().hex[:8]}",
        "message": f"Email account created for {employee_name} ({employee_email}) in {department}",
        "tool": "create_email_account",
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Created email: {employee_email}",
            "actionTaken": "create_email_account", "agentName": "ExecutionAgent",
            "toolName": "create_email_account", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_calendar_event
# ────────────────────────────────────────
@mcp.tool()
def create_calendar_event(title: str, attendees: str, date: str, duration_minutes: int = 60, workflow_id: str = "") -> str:
    """Schedule a calendar event / meeting.

    Args:
        title: Title of the event.
        attendees: Comma-separated attendee emails.
        date: Date/time in ISO format.
        duration_minutes: Duration in minutes.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.3)
    if random.random() < 0.15:
        return json.dumps({"success": False, "error": "Calendar API rate limited", "tool": "create_calendar_event"})

    result = {
        "success": True, "eventId": f"evt-{uuid.uuid4().hex[:8]}",
        "title": title, "attendees": attendees, "date": date,
        "duration_minutes": duration_minutes,
        "message": f"Event '{title}' scheduled with {attendees}",
        "tool": "create_calendar_event",
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Scheduled: {title}",
            "actionTaken": "create_calendar_event", "agentName": "ExecutionAgent",
            "toolName": "create_calendar_event", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_jira_task
# ────────────────────────────────────────
@mcp.tool()
def create_jira_task(title: str, description: str, assignee: str, priority: str = "medium", workflow_id: str = "") -> str:
    """Create a JIRA task / ticket.

    Args:
        title: Task title.
        description: Description of the task.
        assignee: Person assigned.
        priority: low, medium, high, critical.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.4)
    if random.random() < 0.15:
        return json.dumps({"success": False, "error": "JIRA 503", "tool": "create_jira_task"})

    result = {
        "success": True, "taskId": f"TASK-{random.randint(1000, 9999)}",
        "title": title, "assignee": assignee, "priority": priority,
        "message": f"JIRA task '{title}' assigned to {assignee}",
        "tool": "create_jira_task",
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"JIRA: {title} → {assignee}",
            "actionTaken": "create_jira_task", "agentName": "ExecutionAgent",
            "toolName": "create_jira_task", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: update_employee_status
# ────────────────────────────────────────
@mcp.tool()
def update_employee_status(employee_id: str, new_status: str, workflow_id: str = "") -> str:
    """Update an employee's status in the HR system.

    Args:
        employee_id: UUID of the employee.
        new_status: New status: PENDING, ONBOARDING, ACTIVE, FAILED.
        workflow_id: Workflow ID for audit tracking.
    """
    try:
        emp = update_employee(employee_id, {"status": new_status})
        result = {
            "success": True, "employeeId": employee_id,
            "name": emp.get("name", ""), "newStatus": new_status,
            "message": f"Employee {emp.get('name', employee_id)} → {new_status}",
            "tool": "update_employee_status",
        }
    except ValueError as e:
        result = {"success": False, "error": str(e), "tool": "update_employee_status"}

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Status → {new_status}",
            "actionTaken": "update_employee_status", "agentName": "ExecutionAgent",
            "toolName": "update_employee_status", "status": "completed" if result["success"] else "failed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: find_delegate
# ────────────────────────────────────────
@mcp.tool()
def find_delegate(department: str, role: str = "", workflow_id: str = "") -> str:
    """Find a suitable delegate/buddy in a department.

    Args:
        department: Department to search in.
        role: Optional preferred role to match.
        workflow_id: Workflow ID for audit tracking.
    """
    employees = list_employees()
    candidates = [e for e in employees if e.get("department") == department and e.get("status") == "ACTIVE"]
    if not candidates:
        return json.dumps({"success": False, "error": f"No active employees in {department}", "tool": "find_delegate"})

    chosen = random.choice(candidates)
    result = {
        "success": True, "delegateId": chosen["id"],
        "delegateName": chosen["name"], "delegateEmail": chosen["email"],
        "department": department,
        "message": f"Delegate: {chosen['name']} ({chosen['email']})",
        "tool": "find_delegate",
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Delegate: {chosen['name']}",
            "actionTaken": "find_delegate", "agentName": "ExecutionAgent",
            "toolName": "find_delegate", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: check_sla_status
# ────────────────────────────────────────
@mcp.tool()
def check_sla_status(task_type: str, deadline: str = "", workflow_id: str = "") -> str:
    """Check SLA compliance for a task or process.

    Args:
        task_type: Type of task.
        deadline: Optional deadline (ISO).
        workflow_id: Workflow ID for audit tracking.
    """
    is_overdue = random.random() < 0.3
    result = {
        "success": True, "taskType": task_type,
        "slaStatus": "BREACHED" if is_overdue else "COMPLIANT",
        "hoursRemaining": -2 if is_overdue else random.randint(4, 48),
        "riskLevel": "critical" if is_overdue else "low",
        "message": f"SLA {'BREACHED' if is_overdue else 'COMPLIANT'} for {task_type}",
        "tool": "check_sla_status",
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"SLA: {task_type}",
            "actionTaken": "check_sla_status", "agentName": "ExecutionAgent",
            "toolName": "check_sla_status", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: log_audit_entry
# ────────────────────────────────────────
@mcp.tool()
def log_audit_entry(workflow_id: str, decision: str, reason: str, action_taken: str, agent_name: str = "", tool_name: str = "", status: str = "info") -> str:
    """Write an entry to the enterprise audit trail.

    Args:
        workflow_id: The workflow this entry belongs to.
        decision: The decision made.
        reason: Why this decision was made.
        action_taken: What action was performed.
        agent_name: Which agent made this decision.
        tool_name: Which tool was used.
        status: Status of the action.
    """
    entry = append_audit_log(workflow_id, {
        "decision": decision, "reason": reason,
        "actionTaken": action_taken, "agentName": agent_name,
        "toolName": tool_name, "status": status,
    })
    return json.dumps({"success": True, "auditId": entry["id"], "message": "Audit entry recorded"})


# ── Entry point ──
if __name__ == "__main__":
    mcp.run(transport="stdio")
