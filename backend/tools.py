"""
Enterprise tools as Strands @tool decorated functions.
These are REAL tools that the LLM agents can call — they read/write state files.
"""
import json
import random
import time
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from strands import tool
from state_manager import (
    create_employee, update_employee, get_employee, list_employees,
    append_audit_log, append_stream_event
)

# Parse standard Postgres connect string from .env
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/enterprise_autopilot")

def _json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

@tool
def execute_sql(query: str, workflow_id: str = "") -> str:
    """Execute any SQL querying or manipulation against the PostgreSQL database.
    
    Args:
        query: The SQL query to execute (SELECT, INSERT, UPDATE, DELETE).
        workflow_id: The workflow ID for audit tracking.
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        
        # If it's a SELECT returning data, fetch rows
        rows = []
        if cursor.description:
            rows = cursor.fetchall()
            
        conn.commit()
        cursor.close()
        conn.close()
        
        result = {
            "success": True,
            "rowCount": cursor.rowcount,
            "data": rows,
            "tool": "execute_sql"
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "tool": "execute_sql"
        }

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Executed SQL: {query[:50]}...",
            "actionTaken": "execute_sql",
            "agentName": "ExecutionAgent",
            "toolName": "execute_sql",
            "status": "completed" if result["success"] else "failed"
        })

    return json.dumps(result, default=_json_serial)


@tool
def send_email(to: str, subject: str, body: str, workflow_id: str = "") -> str:
    """Send an email to the specified recipient. Used for welcome emails, notifications, account creation confirmations.

    Args:
        to: Email address of the recipient.
        subject: Subject line of the email.
        body: Body text of the email.
        workflow_id: The workflow ID for audit tracking.
    """
    # Simulate realistic email sending with slight delay
    time.sleep(0.5)

    # 10% simulated failure rate to test recovery
    if random.random() < 0.10:
        return json.dumps({
            "success": False,
            "error": "SMTP connection timeout — mail server temporarily unavailable",
            "tool": "send_email"
        })

    result = {
        "success": True,
        "messageId": f"msg-{uuid.uuid4().hex[:8]}",
        "to": to,
        "subject": subject,
        "tool": "send_email",
        "message": f"Email sent successfully to {to}"
    }

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Sent email to {to}: {subject}",
            "actionTaken": "send_email",
            "agentName": "ExecutionAgent",
            "toolName": "send_email",
            "status": "completed"
        })

    return json.dumps(result)


@tool
def create_email_account(employee_name: str, employee_email: str, department: str, workflow_id: str = "") -> str:
    """Create an enterprise email account for a new employee.

    Args:
        employee_name: Full name of the employee.
        employee_email: Desired email address.
        department: The department the employee belongs to.
        workflow_id: The workflow ID for audit tracking.
    """
    time.sleep(0.8)

    if random.random() < 0.10:
        return json.dumps({
            "success": False,
            "error": "Active Directory sync failed — cannot provision email account",
            "tool": "create_email_account"
        })

    result = {
        "success": True,
        "email": employee_email,
        "accountId": f"acc-{uuid.uuid4().hex[:8]}",
        "message": f"Email account created for {employee_name} ({employee_email}) in {department}",
        "tool": "create_email_account"
    }

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Created email account: {employee_email}",
            "actionTaken": "create_email_account",
            "agentName": "ExecutionAgent",
            "toolName": "create_email_account",
            "status": "completed"
        })

    return json.dumps(result)


@tool
def create_calendar_event(title: str, attendees: str, date: str, duration_minutes: int = 60, workflow_id: str = "") -> str:
    """Schedule a calendar event / meeting.

    Args:
        title: Title of the meeting/event.
        attendees: Comma-separated list of attendee emails.
        date: Date/time for the event (ISO format or descriptive).
        duration_minutes: Duration in minutes.
        workflow_id: The workflow ID for audit tracking.
    """
    time.sleep(0.6)

    if random.random() < 0.15:
        return json.dumps({
            "success": False,
            "error": "Calendar service unavailable — Google Calendar API rate limited",
            "tool": "create_calendar_event"
        })

    result = {
        "success": True,
        "eventId": f"evt-{uuid.uuid4().hex[:8]}",
        "title": title,
        "attendees": attendees,
        "date": date,
        "duration_minutes": duration_minutes,
        "message": f"Calendar event '{title}' scheduled with {attendees}",
        "tool": "create_calendar_event"
    }

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Scheduled: {title} with {attendees}",
            "actionTaken": "create_calendar_event",
            "agentName": "ExecutionAgent",
            "toolName": "create_calendar_event",
            "status": "completed"
        })

    return json.dumps(result)


@tool
def create_jira_task(title: str, description: str, assignee: str, priority: str = "medium", workflow_id: str = "") -> str:
    """Create a JIRA task / ticket in the project tracker.

    Args:
        title: Title of the task.
        description: Description of what needs to be done.
        assignee: Email or name of the person assigned.
        priority: Priority level: low, medium, high, critical.
        workflow_id: The workflow ID for audit tracking.
    """
    time.sleep(0.7)

    if random.random() < 0.15:
        return json.dumps({
            "success": False,
            "error": "JIRA API returned 503 — service temporarily unavailable",
            "tool": "create_jira_task"
        })

    result = {
        "success": True,
        "taskId": f"TASK-{random.randint(1000, 9999)}",
        "title": title,
        "assignee": assignee,
        "priority": priority,
        "message": f"JIRA task '{title}' created and assigned to {assignee}",
        "tool": "create_jira_task"
    }

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Created JIRA task: {title} → {assignee}",
            "actionTaken": "create_jira_task",
            "agentName": "ExecutionAgent",
            "toolName": "create_jira_task",
            "status": "completed"
        })

    return json.dumps(result)


@tool
def update_employee_status(employee_id: str, new_status: str, workflow_id: str = "") -> str:
    """Update an employee's status in the HR system.

    Args:
        employee_id: UUID of the employee.
        new_status: New status: PENDING, ONBOARDING, ACTIVE, FAILED.
        workflow_id: The workflow ID for audit tracking.
    """
    time.sleep(0.3)

    try:
        emp = update_employee(employee_id, {"status": new_status})
        result = {
            "success": True,
            "employeeId": employee_id,
            "name": emp.get("name", ""),
            "newStatus": new_status,
            "message": f"Employee {emp.get('name', employee_id)} status updated to {new_status}",
            "tool": "update_employee_status"
        }
    except ValueError as e:
        result = {"success": False, "error": str(e), "tool": "update_employee_status"}

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Employee status → {new_status}",
            "actionTaken": "update_employee_status",
            "agentName": "ExecutionAgent",
            "toolName": "update_employee_status",
            "status": "completed" if result["success"] else "failed"
        })

    return json.dumps(result)


@tool
def find_delegate(department: str, role: str = "", workflow_id: str = "") -> str:
    """Find a suitable delegate/buddy in a department for mentoring or task handoff.

    Args:
        department: Department to search in.
        role: Optional preferred role to match.
        workflow_id: The workflow ID for audit tracking.
    """
    time.sleep(0.4)

    employees = list_employees()
    candidates = [e for e in employees if e.get("department") == department and e.get("status") == "ACTIVE"]

    if not candidates:
        return json.dumps({
            "success": False,
            "error": f"No active employees found in {department}",
            "tool": "find_delegate"
        })

    chosen = random.choice(candidates)
    result = {
        "success": True,
        "delegateId": chosen["id"],
        "delegateName": chosen["name"],
        "delegateEmail": chosen["email"],
        "department": department,
        "message": f"Found delegate: {chosen['name']} ({chosen['email']})",
        "tool": "find_delegate"
    }

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"Found delegate {chosen['name']} in {department}",
            "actionTaken": "find_delegate",
            "agentName": "ExecutionAgent",
            "toolName": "find_delegate",
            "status": "completed"
        })

    return json.dumps(result)


@tool
def check_sla_status(task_type: str, deadline: str = "", workflow_id: str = "") -> str:
    """Check SLA compliance status for a task or process.

    Args:
        task_type: Type of task to check SLA for.
        deadline: Optional deadline to check against.
        workflow_id: The workflow ID for audit tracking.
    """
    time.sleep(0.3)

    is_overdue = random.random() < 0.3  # 30% chance overdue
    result = {
        "success": True,
        "taskType": task_type,
        "slaStatus": "BREACHED" if is_overdue else "COMPLIANT",
        "hoursRemaining": -2 if is_overdue else random.randint(4, 48),
        "riskLevel": "critical" if is_overdue else "low",
        "message": f"SLA {'BREACHED' if is_overdue else 'COMPLIANT'} for {task_type}",
        "tool": "check_sla_status"
    }

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed",
            "reason": f"SLA check: {task_type} → {'BREACHED' if is_overdue else 'COMPLIANT'}",
            "actionTaken": "check_sla_status",
            "agentName": "ExecutionAgent",
            "toolName": "check_sla_status",
            "status": "completed"
        })

    return json.dumps(result)


@tool
def log_audit_entry(workflow_id: str, decision: str, reason: str, action_taken: str, agent_name: str = "", tool_name: str = "", status: str = "info") -> str:
    """Write an entry to the enterprise audit trail.

    Args:
        workflow_id: The workflow this entry belongs to.
        decision: The decision made (e.g., step_started, completed, escalated).
        reason: Why this decision was made.
        action_taken: What action was performed.
        agent_name: Which agent made this decision.
        tool_name: Which tool was used, if any.
        status: Status of the action (info, completed, failed, escalated).
    """
    entry = append_audit_log(workflow_id, {
        "decision": decision,
        "reason": reason,
        "actionTaken": action_taken,
        "agentName": agent_name,
        "toolName": tool_name,
        "status": status,
    })
    return json.dumps({"success": True, "auditId": entry["id"], "message": "Audit entry recorded"})


# All tools as a list for easy import
ALL_ENTERPRISE_TOOLS = [
    execute_sql,
    send_email,
    create_email_account,
    create_calendar_event,
    create_jira_task,
    update_employee_status,
    find_delegate,
    check_sla_status,
    log_audit_entry,
]
