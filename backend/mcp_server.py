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

from dotenv import load_dotenv
load_dotenv()

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


def _send_real_email(to_email: str, subject: str, content: str) -> None:
    import smtplib
    from email.message import EmailMessage
    
    smtp_server = os.getenv("SMTP_SERVER", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    
    if not all([smtp_server, smtp_user, smtp_pass]):
        raise ValueError("SMTP environment variables not configured.")
        
    msg = EmailMessage()
    msg.set_content(content)
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email
    
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


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
    try:
        _send_real_email(to, subject, body)
        result = {
            "success": True, "messageId": f"msg-{str(uuid.uuid4())[:8]}",
            "to": to, "subject": subject, "tool": "send_email",
            "message": f"Email sent to {to}",
        }
        status = "completed"
    except Exception as e:
        result = {"success": False, "error": str(e), "tool": "send_email"}
        status = "failed"

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Email to {to}: {subject}",
            "actionTaken": "send_email", "agentName": "ExecutionAgent",
            "toolName": "send_email", "status": status,
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
        "accountId": f"acc-{str(uuid.uuid4())[:8]}",
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
        "slaStatus": "BREACHED" if is_overdue else "COMPLIANT" ,
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


# ────────────────────────────────────────
# TOOL: create_email_account_tool
# ────────────────────────────────────────
@mcp.tool()
def create_email_account_tool(name: str, workflow_id: str = "") -> str:
    """Create a company email account for a new employee.

    Args:
        name: Full name.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.3)
    acc_id = str(uuid.uuid4())[:8]
    result = {
        "success": True,
        "message": "Email account created",
        "data": {
            "email_id": name+"@avaatar.ai",
            "account_id": f"mail-{acc_id}"
        }
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Created email account for {name}",
            "actionTaken": "create_email_account_tool", "agentName": "ExecutionAgent",
            "toolName": "create_email_account_tool", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_jira_account_tool
# ────────────────────────────────────────
@mcp.tool()
def create_jira_account_tool(name: str, email: str, workflow_id: str = "") -> str:
    """Create access for employee in JIRA system.

    Args:
        name: Employee name.
        email: Employee email.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.4)
    # Simulate failure randomly (60–70% failure rate)
    if random.random() < 0.65:
        result = {
            "success": False,
            "message": "JIRA access denied",
            "error": "ACCESS_DENIED",
            "retryable": True
        }
        status = "failed"
    else:
        result = {
            "success": True,
            "message": "JIRA account created",
            "data": {
                "jira_id": f"JIRA-{random.randint(100, 999)}"
            }
        }
        status = "completed"

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Attempt JIRA account creation for {name}",
            "actionTaken": "create_jira_account_tool", "agentName": "ExecutionAgent",
            "toolName": "create_jira_account_tool", "status": status,
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_hr_account_tool
# ────────────────────────────────────────
@mcp.tool()
def create_hr_account_tool(name: str, email: str, workflow_id: str = "") -> str:
    """Create employee record in HR system.

    Args:
        name: Employee name.
        email: Employee email.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.5)
    from state_manager import list_employees, update_employee
    
    generated_id = f"EMP-{random.randint(1000, 9999)}"
    
    # Update employee with the generated ID
    for emp in list_employees():
        if emp.get("email") == email:
            update_employee(emp["id"], {"employeeId": generated_id})
            break

    result = {
        "success": True,
        "message": "HR account created",
        "data": {
            "employee_id": generated_id
        }
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Created HR account for {name}",
            "actionTaken": "create_hr_account_tool", "agentName": "ExecutionAgent",
            "toolName": "create_hr_account_tool", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: assign_buddy_tool
# ────────────────────────────────────────
@mcp.tool()
def assign_buddy_tool(name: str, department: str = "Engineering", workflow_id: str = "") -> str:
    """Assign a mentor/buddy to the employee based on experience match.

    Args:
        name: Employee name.
        department: Employee's department.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.3)
    from state_manager import list_employees, update_employee
    
    employees = list_employees()
    # Find the employee being onboarded
    new_emp = next((e for e in employees if e.get("name") == name), None)
    
    # Find ACTIVE employees in the same department
    candidates = [
        e for e in employees 
        if e.get("department") == department 
        and e.get("status") == "ACTIVE"
        and (not new_emp or e.get("id") != new_emp["id"])
    ]
    
    # Smart Mapping: If new employee is an engineer, prefer assigning an SDE 2/3 or Senior
    if new_emp and "engineer" in new_emp.get("role", "").lower():
        senior_candidates = [
            c for c in candidates 
            if any(lvl in c.get("role", "").lower() for lvl in ["senior", "lead", "principal", "ii", "iii", "2", "3"])
        ]
        if senior_candidates:
            candidates = senior_candidates

    if candidates:
        chosen = random.choice(candidates)
        buddy_name = chosen["name"]
        buddy_email = chosen["email"]
    else:
        # Fallback buddy if none available
        buddy_name = "Alice Senior (Fallback)"
        buddy_email = "alice.fallback@company.com"

    # Update database: add 'buddy' column to the employee
    if new_emp:
        update_employee(new_emp["id"], {"buddy": buddy_name})

    result = {
        "success": True,
        "message": "Buddy assigned successfully",
        "data": {
            "buddy_name": buddy_name,
            "buddy_email": buddy_email
        }
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Assigned buddy {buddy_name} to {name}",
            "actionTaken": "assign_buddy_tool", "agentName": "ExecutionAgent",
            "toolName": "assign_buddy_tool", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: schedule_meeting_tool
# ────────────────────────────────────────
@mcp.tool()
def schedule_meeting_tool(name: str, buddy_email: str = "", workflow_id: str = "") -> str:
    """Schedule orientation meeting.

    Args:
        name: Employee name.
        buddy_email: Buddy's email.
        workflow_id: Workflow ID for audit tracking.
    """
    meeting_link = f"https://meet.avataar.ai/{str(uuid.uuid4())[:8]}"
    meeting_time = "10:00 AM"
    
    result = {
        "success": True,
        "message": "Orientation meeting scheduled",
        "data": {
            "meeting_link": meeting_link,
            "time": meeting_time
        }
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Scheduled orientation for {name} at {meeting_time}",
            "actionTaken": "schedule_meeting_tool", "agentName": "ExecutionAgent",
            "toolName": "schedule_meeting_tool", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: escalate_to_it_tool
# ────────────────────────────────────────
@mcp.tool()
def escalate_to_it_tool(issue: str, employee_name: str, workflow_id: str = "") -> str:
    """Handle escalation when system access fails.

    Args:
        issue: Description of the issue.
        employee_name: Employee name.
        workflow_id: Workflow ID for audit tracking.
    """
    ticket_id = f"IT-{random.randint(10000, 99999)}"
    
    result = {
        "success": True,
        "message": "Escalation ticket created",
        "data": {
            "ticket_id": ticket_id,
            "assigned_team": "IT Access Management"
        }
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Escalated issue: {issue}",
            "actionTaken": "escalate_to_it_tool", "agentName": "ExecutionAgent",
            "toolName": "escalate_to_it_tool", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: send_onboarding_email_tool
# ────────────────────────────────────────
@mcp.tool()
def send_onboarding_email_tool(email: str, subject: str, content: str, workflow_id: str = "") -> str:
    """Send the onboarding email to the employee using SMTP.

    Args:
        email: Employee email address.
        subject: Email subject.
        content: The onboarding email content generated by the agent.
        workflow_id: Workflow ID for audit tracking.
    """
    try:
        _send_real_email(email, subject, content)
        result = {
            "success": True,
            "message": "Onboarding email sent successfully via SMTP",
            "data": {
                "to": email,
                "subject": subject
            },
            "tool": "send_onboarding_email_tool"
        }
        status = "completed"
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "message": "Failed to send email",
            "tool": "send_onboarding_email_tool"
        }
        status = "failed"

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Sent welcome email to {email}",
            "actionTaken": "send_onboarding_email_tool", "agentName": "ExecutionAgent",
            "toolName": "send_onboarding_email_tool", "status": status,
        })
    return json.dumps(result)



# ────────────────────────────────────────
# TOOL: create_task_tool
# ────────────────────────────────────────
@mcp.tool()
def create_task_tool(title: str, description: str, assignee: str, priority: str = "medium", workflow_id: str = "") -> str:
    """Create a task from meeting action items or other sources.

    Args:
        title: Task title.
        description: Detailed task description.
        assignee: Person assigned to this task.
        priority: low, medium, high, critical.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.3)
    task_id = f"TASK-{random.randint(1000, 9999)}"

    result = {
        "success": True,
        "message": f"Task '{title}' created and assigned to {assignee}",
        "data": {
            "task_id": task_id,
            "title": title,
            "assignee": assignee,
            "priority": priority
        },
        "retryable": False
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Created task: {title} → {assignee}",
            "actionTaken": "create_task_tool", "agentName": "ExecutionAgent",
            "toolName": "create_task_tool", "status": "completed",
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: send_summary_email_tool
# ────────────────────────────────────────
@mcp.tool()
def send_summary_email_tool(to: str, summary: str, subject: str = "Meeting Summary", workflow_id: str = "") -> str:
    """Send a summary email (e.g., meeting action items summary).

    Args:
        to: Recipient email address.
        summary: The summary content to send.
        subject: Email subject line.
        workflow_id: Workflow ID for audit tracking.
    """
    try:
        _send_real_email(to, subject, summary)
        msg_id = f"msg-{str(uuid.uuid4())[:8]}"
        result = {
            "success": True,
            "message": f"Summary email sent to {to}",
            "data": {
                "message_id": msg_id,
                "to": to,
                "subject": subject
            },
            "retryable": True
        }
        status = "completed"
    except Exception as e:
        result = {"success": False, "error": str(e), "tool": "send_summary_email_tool"}
        status = "failed"

    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "tool_executed", "reason": f"Summary email to {to}: {subject}",
            "actionTaken": "send_summary_email_tool", "agentName": "ExecutionAgent",
            "toolName": "send_summary_email_tool", "status": status,
        })
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: reroute_approval_tool
# ────────────────────────────────────────
@mcp.tool()
def reroute_approval_tool(step_name: str, from_agent: str, to_agent: str, reason: str, workflow_id: str = "") -> str:
    """Reroute a stuck approval or task to a different agent or delegate.

    Args:
        step_name: Name of the step being rerouted.
        from_agent: Original assignee/agent.
        to_agent: New assignee/agent or delegate.
        reason: Reason for rerouting.
        workflow_id: Workflow ID for audit tracking.
    """
    time.sleep(0.2)

    result = {
        "success": True,
        "message": f"Rerouted '{step_name}' from {from_agent} to {to_agent}",
        "data": {
            "step_name": step_name,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "reason": reason,
            "reroute_id": f"RR-{random.randint(1000, 9999)}"
        },
        "retryable": False
    }
    if workflow_id:
        append_audit_log(workflow_id, {
            "decision": "rerouted", "reason": reason,
            "actionTaken": f"reroute_approval_tool: {from_agent} → {to_agent}",
            "agentName": "HealthMonitorAgent",
            "toolName": "reroute_approval_tool", "status": "completed",
        })
    return json.dumps(result)


# ── Entry point ──
if __name__ == "__main__":
    mcp.run(transport="stdio")
