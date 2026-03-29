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

# ── Ensure db package is importable ──
sys.path.insert(0, os.path.dirname(__file__))
from db.connection import init_db, get_conn
from db import queries as db

mcp = FastMCP("Enterprise Autopilot Tools")

DB_URL = os.getenv("DATABASE_URL", os.getenv("DB_URL", "postgresql://postgres:1234@localhost:5432/enterprise_autopilot"))


def _json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _tool_envelope(success: bool, message: str, data=None,
                   error=None, tool_name: str = "", retryable: bool = False) -> str:
    """Standardized tool return envelope. Every tool should use this."""
    return json.dumps({
        "success": success,
        "message": message,
        "data": data,
        "error": error,
        "tool": tool_name,
        "retryable": retryable
    }, default=_json_serial)


# ────────────────────────────────────────
# TOOL: execute_sql
# ────────────────────────────────────────
@mcp.tool()
def execute_sql(query: str, workflow_id: str = "") -> str:
    """Universal SQL executor — the primary interface to the enterprise database.

    This is the most versatile tool in the system. Use it for ANY situation requiring
    data lookup, mutation, or intelligence that no other tool covers directly.

    DATABASE TABLES (snake_case column names):
      employees   — id, employee_id, name, email, company_email, role, department,
                    buddy, status (PENDING|ONBOARDING|ACTIVE|FAILED), created_at
      workflows   — id, type, entity_id (FK→employees), trigger_event, status, plan, created_at
      steps       — id, workflow_id, step_name, tool_name, status, current_output, dependency_order
      audit_logs  — id, workflow_id, step_id, decision, reason, action_taken, agent_name,
                    tool_name, retry_count, status, timestamp
      agent_logs  — id, workflow_id, step_id, agent_name, action, tool_name, input, output, duration_ms

    CRITICAL QUERY RULES:
      - Always use LOWER() or ILIKE for name/role/department comparisons (case may vary in DB).
      - Empty result (rowCount=0, data=[]) on SELECT is NOT a failure — it means no matching rows.
      - Use LIMIT 1 when you need the single best match.
      - Parameterize values by constructing the full SQL string (no bind params in this interface).

    USE CASES — this tool replaces all of these when no dedicated tool exists:

    1. LOOK UP EMPLOYEE EMAIL BY NAME:
       SELECT name, email, company_email, role, department
       FROM employees WHERE LOWER(name) = LOWER('Alice')

    2. FIND BEST MENTOR / BUDDY (no find_buddy tool needed):
       SELECT name, email, role FROM employees
       WHERE LOWER(department) = LOWER('Engineering')
         AND status = 'ACTIVE'
         AND LOWER(name) != LOWER('new_hire_name')
       ORDER BY created_at ASC LIMIT 1

    3. ASSIGN BUDDY — persist selection:
       UPDATE employees SET buddy = 'mentor_name', updated_at = NOW()
       WHERE LOWER(name) = LOWER('new_hire_name')

    4. FIND COLLEAGUES IN SAME ROLE (to notify about new hire):
       SELECT name, email FROM employees
       WHERE LOWER(role) ILIKE '%engineer%' AND status = 'ACTIVE'

    5. CHECK EMPLOYEE STATUS:
       SELECT status, employee_id, company_email FROM employees
       WHERE LOWER(name) = LOWER('John')

    6. UPDATE EMPLOYEE ONBOARDING STATUS:
       UPDATE employees SET status = 'ACTIVE', updated_at = NOW()
       WHERE LOWER(name) = LOWER('new_hire_name')

    7. AUDIT TRAIL QUERY:
       SELECT decision, reason, action_taken, timestamp FROM audit_logs
       WHERE workflow_id = 'some-uuid' ORDER BY timestamp ASC

    8. FIND DELEGATE WHEN APPROVER IS UNAVAILABLE:
       SELECT name, email FROM employees
       WHERE LOWER(department) = LOWER('Finance')
         AND status = 'ACTIVE'
         AND LOWER(name) != LOWER('unavailable_approver')
       ORDER BY RANDOM() LIMIT 1

    Returns JSON:
      { "success": true/false, "rowCount": N, "data": [...rows], "tool": "execute_sql" }
      On error: { "success": false, "error": "...", "tool": "execute_sql" }

    Args:
        query: Full SQL query string (SELECT, INSERT, UPDATE, DELETE).
               Use ILIKE for case-insensitive string matching.
        workflow_id: Workflow UUID for audit tracking (optional but recommended).
    """
    try:
        with get_conn() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            rows = []
            if cursor.description:
                rows = [dict(r) for r in cursor.fetchall()]
            row_count = cursor.rowcount if cursor.rowcount is not None else len(rows)
        result = {
            "success": True,
            "rowCount": row_count,
            "data": rows,
            "tool": "execute_sql",
            "message": f"Query executed successfully. {len(rows)} row(s) returned." if rows else
                       f"Query executed successfully. {row_count} row(s) affected.",
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "rowCount": 0,
            "data": [],
            "tool": "execute_sql",
        }

    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"SQL: {query[:120]}", action_taken="execute_sql",
            agent_name="ExecutionAgent", tool_name="execute_sql",
            status="completed" if result["success"] else "failed"
        )
    return json.dumps(result, default=_json_serial)


def _generate_ics(summary: str, description: str, meeting_link: str, start_str: str, duration_minutes: int = 60) -> str:
    """Generate an ICS calendar invite string."""
    from datetime import datetime as dt, timedelta
    uid = str(uuid.uuid4())
    # Parse start time — try ISO format first, fallback to simple time
    try:
        start_dt = dt.fromisoformat(start_str)
    except Exception:
        # If just a time like "10:00 AM", assume tomorrow
        try:
            start_dt = dt.strptime(start_str, "%I:%M %p")
            tomorrow = dt.now() + timedelta(days=1)
            start_dt = start_dt.replace(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day)
        except Exception:
            tomorrow = dt.now() + timedelta(days=1)
            start_dt = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    fmt = "%Y%m%dT%H%M%S"
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//EnterpriseAutopilot//Onboarding//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dt.utcnow().strftime(fmt)}
DTSTART:{start_dt.strftime(fmt)}
DTEND:{end_dt.strftime(fmt)}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{meeting_link}
END:VEVENT
END:VCALENDAR
"""


def _send_html_email(to_email: str, subject: str, html_body: str, ics_content: str = "") -> None:
    """Send an HTML email with optional ICS calendar invite attachment."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_server = os.getenv("SMTP_SERVER", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()

    if not all([smtp_server, smtp_user, smtp_pass]):
        raise ValueError("SMTP environment variables not configured.")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email

    # HTML body
    msg.attach(MIMEText(html_body, "html"))

    # ICS calendar invite (if provided)
    if ics_content:
        ics_part = MIMEText(ics_content, "calendar;method=REQUEST")
        msg.attach(ics_part)

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


# ────────────────────────────────────────
# TOOL: send_email
# ────────────────────────────────────────
@mcp.tool()
def send_email(to: str, subject: str, body: str, workflow_id: str = "") -> str:
    """Send a plain or HTML email to any recipient. General-purpose email delivery.

    USE CASES:
      - Notify a manager about an escalated issue.
      - Send a custom alert or status update to any stakeholder.
      - Deliver ad-hoc messages not covered by onboarding/orientation-specific tools.
      - Forward audit summaries to compliance officers.
      - Send SLA breach notifications to department heads.

    TIP: Use send_onboarding_email_tool for welcome emails (it includes ICS invite and rich HTML).
         Use send_summary_email_tool for meeting action-item summaries.
         Use this tool for everything else.

    Returns: { "success": true, "messageId": "msg-xxxx", "to": "...", "subject": "..." }

    Args:
        to: Recipient email address (must be a valid address from employees table or known stakeholder).
        subject: Subject line — be specific and entity-rich (include names, IDs).
        body: Email body. Can be plain text or HTML string.
        workflow_id: Workflow UUID for audit tracking.
    """
    try:
        _send_html_email(to, subject, body)
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
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Email to {to}: {subject}", action_taken="send_email",
            agent_name="ExecutionAgent", tool_name="send_email", status=status
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_email_account
# ────────────────────────────────────────
@mcp.tool()
def create_email_account(employee_name: str, employee_email: str, department: str, workflow_id: str = "") -> str:
    """Provision an enterprise email account for a new employee and persist it to the database.

    This tool simulates Active Directory (AD) account creation. On success it writes the
    company_email field into the employees table so subsequent steps can reference it.

    USE CASES:
      - Onboarding: provision company email for a new hire after HR account is created.
      - Re-provisioning: recreate an account if the first attempt failed (retryable).
      - Any workflow step that needs a company_email to exist before sending emails.

    NOTE: There is a ~10% random AD sync failure rate (retryable). The recovery agent
          will automatically retry transient failures.

    Returns: { "success": true, "data": { "company_email": "...", "accountId": "acc-xxxx" } }

    Args:
        employee_name: Full name of the employee (used for display/logging).
        employee_email: The email address to provision as the company email.
        department: Employee's department — used for AD group assignment.
        workflow_id: Workflow UUID for audit tracking.
    """
    time.sleep(0.4)
    if random.random() < 0.10:
        return json.dumps({"success": False, "error": "AD sync failed", "tool": "create_email_account", "retryable": True})

    company_email = employee_email
    account_id = f"acc-{str(uuid.uuid4())[:8]}"

    # Persist company_email to DB
    emp = db.get_employee_by_email(employee_email)
    if emp:
        db.update_employee_fields(emp["id"], {"company_email": company_email})

    result = {
        "success": True,
        "message": f"Email account created for {employee_name} ({company_email}) in {department}",
        "tool": "create_email_account",
        "retryable": False,
        "data": {
            "company_email": company_email,
            "accountId": account_id
        }
    }
    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Created email: {company_email}", action_taken="create_email_account",
            agent_name="ExecutionAgent", tool_name="create_email_account", status="completed"
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: update_employee_status (internal — not exposed to agents)
# ────────────────────────────────────────
def update_employee_status(employee_id: str, new_status: str, workflow_id: str = "") -> str:
    """Update an employee's status in the HR system. Internal use only."""
    try:
        ok = db.update_employee_status(employee_id, new_status, employee_db_id=employee_id)
        emp = db.get_employee_by_id(employee_id)
        name = emp.get("name", employee_id) if emp else employee_id
        result = {
            "success": ok, "employeeId": employee_id,
            "name": name, "newStatus": new_status,
            "message": f"Employee {name} → {new_status}",
            "tool": "update_employee_status",
        }
    except Exception as e:
        result = {"success": False, "error": str(e), "tool": "update_employee_status"}

    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Status → {new_status}", action_taken="update_employee_status",
            agent_name="ExecutionAgent", tool_name="update_employee_status",
            status="completed" if result["success"] else "failed"
        )
    return json.dumps(result)



# ────────────────────────────────────────
# TOOL: check_sla_status
# ────────────────────────────────────────
@mcp.tool()
def check_sla_status(task_type: str, deadline: str = "", workflow_id: str = "") -> str:
    """Check whether a task or process is within its SLA deadline.

    USE CASES:
      - Before routing an approval: verify if it is still within SLA or already breached.
      - In SLA breach workflows: confirm breach status before escalating.
      - Post-task audit: record whether SLA was maintained for compliance.
      - Proactive monitoring: check SLA health for any ticket type.

    Returns: {
      "slaStatus": "BREACHED" | "COMPLIANT",
      "hoursRemaining": N,   (negative means already overdue)
      "riskLevel": "critical" | "low"
    }

    Args:
        task_type: Human-readable task type string e.g. "onboarding", "approval", "PROD-4521".
        deadline: Optional ISO 8601 deadline timestamp. If omitted, simulates based on type.
        workflow_id: Workflow UUID for audit tracking.
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
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"SLA: {task_type}", action_taken="check_sla_status",
            agent_name="ExecutionAgent", tool_name="check_sla_status", status="completed"
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: log_audit_entry
# ────────────────────────────────────────
@mcp.tool()
def log_audit_entry(workflow_id: str, decision: str, reason: str, action_taken: str, agent_name: str = "", tool_name: str = "", status: str = "info") -> str:
    """Write a compliance-grade entry to the enterprise audit trail.

    This tool is the authoritative record keeper. Use it to document any significant
    decision, escalation, delegation, or workflow outcome for traceability.

    USE CASES:
      - Record that a step was escalated and why.
      - Document that an approver was substituted (rerouting).
      - Log that an SLA was breached and action was taken.
      - Write a summary at the end of a workflow for compliance.
      - Record when a buddy/mentor was assigned and who was selected.
      - Document any manual override or human intervention trigger.

    AUDIT MESSAGE FORMAT BEST PRACTICE:
      decision:     "ESCALATED" | "COMPLETED" | "REROUTED" | "BUDDY_ASSIGNED" | "SLA_BREACHED" etc.
      reason:       One precise sentence — what happened and why.
      action_taken: What the system or human did in response.

    Returns: { "success": true, "auditId": "uuid" }

    Args:
        workflow_id: Workflow UUID — required for traceability.
        decision: The classification of this audit event (e.g. "ESCALATED", "COMPLETED").
        reason: Why this event occurred — cite entity names, tool names, error codes.
        action_taken: What action was executed or triggered as a result.
        agent_name: Agent that generated this entry (e.g. "recovery", "orchestrator").
        tool_name: Tool involved in the event (optional).
        status: "completed" | "failed" | "info" | "RECOVERY" | "ESCALATED".
    """
    entry = db.log_audit(
        workflow_id=workflow_id, decision=decision, reason=reason,
        action_taken=action_taken, agent_name=agent_name,
        tool_name=tool_name, status=status
    )
    return json.dumps({"success": True, "auditId": entry["id"], "message": "Audit entry recorded"})


# ────────────────────────────────────────
# TOOL: create_jira_account_tool
# ────────────────────────────────────────
@mcp.tool()
def create_jira_account_tool(name: str, email: str, workflow_id: str = "") -> str:
    """Provision a JIRA account and project access for an employee.

    USE CASES:
      - Onboarding: give new hires access to the project management system.
      - Role change: extend JIRA access when an employee changes teams.
      - Access restoration: re-provision after account expiry.

    NOTE: This tool has a high (~65%) random ACCESS_DENIED failure rate to simulate
          real-world permission issues. The recovery agent will escalate to IT
          via escalate_to_it_tool when ACCESS_DENIED occurs (not retryable).
          Transient infrastructure errors ARE retryable.

    Returns:
      Success: { "success": true, "data": { "jira_id": "JIRA-xxx" } }
      Failure: { "success": false, "error": "ACCESS_DENIED", "retryable": true }

    Args:
        name: Employee full name.
        email: Employee email address (used as JIRA login identity).
        workflow_id: Workflow UUID for audit tracking.
    """
    time.sleep(0.4)
    # Simulate failure randomly (60–70% failure rate)
    if random.random() < 0.90:
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
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Attempt JIRA account creation for {name}", action_taken="create_jira_account_tool",
            agent_name="ExecutionAgent", tool_name="create_jira_account_tool", status=status
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_hr_account_tool (merged: create + generate ID + set status)
# ────────────────────────────────────────
@mcp.tool()
def create_hr_account_tool(name: str, email: str, role: str = "", department: str = "", workflow_id: str = "") -> str:
    """Create or update an employee HR record — the foundational onboarding step.

    WORKFLOW SCOPE:
      - ✅ EMPLOYEE ONBOARDING / TRANSFER / OFFBOARDING preparation
      - ❌ MEETING-TO-ACTION (do not create HR records for meeting participants)
      - ❌ SLA monitoring (unless you are explicitly onboarding a new approver)

    This tool:
      1. Looks up existing employee by email, then by name (case-insensitive) to avoid duplicates.
      2. Generates a unique employee ID (EMP-XXXX) if not already assigned.
      3. Persists role, department, and sets status to ACTIVE.
      4. Returns the full employee data including employee_id and employee_db_id (internal UUID).

    USE CASES:
      - First step in any employee onboarding workflow.
      - Update role/department when an employee transfers teams.
      - Re-run if a prior attempt failed — it is idempotent (will update, not duplicate).

    IMPORTANT: Always call this BEFORE create_email_account, create_jira_account_tool,
               schedule_meeting_tool, and send_onboarding_email_tool. Those steps depend
               on the employee existing in the database.

    Returns:
      { "success": true, "data": {
          "employee_id": "EMP-4821",
          "employee_db_id": "uuid...",
          "name": "...", "email": "...", "role": "...", "department": "..."
      }}

    Args:
        name: Employee full name (case-insensitive match attempted against existing records).
        email: Employee personal email. Used to find existing record or create new one.
        role: Job title e.g. "Software Engineer". Written to DB.
        department: Department e.g. "Engineering". Written to DB.
        workflow_id: Workflow UUID for audit tracking.
    """
    time.sleep(0.5)
    generated_id = f"EMP-{random.randint(1000, 9999)}"

    # Create employee if not exists, otherwise update.
    # IMPORTANT: do not create duplicate "mock" employees when the correct employee already exists
    # by name but the passed email is placeholder/guessed.
    emp = None
    email_to_use = email

    if email:
        emp = db.get_employee_by_email(email)

    # Fallback: match by name (case-insensitive) to preserve the stored email.
    if not emp:
        emp = db.get_employee_by_name(name)
        if emp:
            email_to_use = emp.get("email", email_to_use)

    if not emp:
        if not email_to_use:
            raise ValueError("Cannot create HR account: missing email and no existing employee by name.")
        emp = db.create_employee(name, email_to_use, role or "Unspecified", department or "General")

    # Update: set employee_id, role, department, status
    update_fields = {"employee_id": generated_id, "status": "ACTIVE"}
    if role:
        update_fields["role"] = role
    if department:
        update_fields["department"] = department
    db.update_employee_fields(emp["id"], update_fields)

    result = {
        "success": True,
        "message": f"HR account created for {name} ({generated_id}) — status set to ACTIVE",
        "tool": "create_hr_account_tool",
        "retryable": False,
        "data": {
            "employee_id": generated_id,
            "employee_db_id": emp["id"],
            "name": name,
            "email": email_to_use,
            "role": role,
            "department": department
        }
    }
    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Created HR account for {name} ({generated_id}), status → ACTIVE",
            action_taken="create_hr_account_tool",
            agent_name="ExecutionAgent", tool_name="create_hr_account_tool", status="completed"
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: schedule_meeting_tool
# ────────────────────────────────────────
@mcp.tool()
def schedule_meeting_tool(name: str, workflow_id: str = "", meeting_time: str = "10:00 AM") -> str:
    """Schedule a virtual meeting and generate a unique meeting link.

    USE CASES:
      - Schedule the new hire orientation/onboarding meeting.
      - Set up a 1:1 with the assigned buddy/mentor.
      - Create any ad-hoc meeting link for a workflow participant.
      - Schedule a review or SLA-breach discussion.

    The meeting_link returned should be passed to:
      - send_onboarding_email_tool (included in welcome email + ICS calendar invite)
      - send_orientation_email_tool (included in colleague notification)

    Returns:
      { "success": true, "data": { "meeting_link": "https://meet.avataar.ai/xxxxxxxx",
                                   "meeting_time": "next Monday 09:00 AM" } }

    Args:
        name: Name of the primary attendee (the new hire, or subject of the meeting).
        meeting_time: Time string e.g. "next Monday 09:00 AM", "10:00 AM", "2026-04-01T10:00:00".
        workflow_id: Workflow UUID for audit tracking.
    """
    meeting_link = f"https://meet.avataar.ai/{str(uuid.uuid4())[:8]}"
    meeting_time = meeting_time
    
    result = {
        "success": True,
        "message": "Orientation meeting scheduled",
        "data": {
            "meeting_link": meeting_link,
            "meeting_time": meeting_time
        }
    }
    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Scheduled orientation for {name} at {meeting_time}",
            action_taken="schedule_meeting_tool", agent_name="ExecutionAgent",
            tool_name="schedule_meeting_tool", status="completed"
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: escalate_to_it_tool
# ────────────────────────────────────────
@mcp.tool()
def escalate_to_it_tool(issue: str, employee_name: str, workflow_id: str = "") -> str:
    """Create an IT escalation ticket when a system access or provisioning step fails.

    USE CASES:
      - JIRA account creation returned ACCESS_DENIED → escalate to IT for permission grant.
      - Email account provisioning failed after retries → escalate to IT for AD sync fix.
      - Any tool failure that requires human IT intervention to resolve.
      - System is unavailable and cannot self-recover.

    This tool generates a unique IT ticket (IT-XXXXX) assigned to "IT Access Management".
    The ticket ID should be included in the audit log entry for traceability.

    Returns:
      { "success": true, "data": { "ticket_id": "IT-93534", "assigned_team": "IT Access Management" } }

    Args:
        issue: Clear description of the failure — include tool name, error message, and employee.
               Example: "create_jira_account_tool returned ACCESS_DENIED for Alice Johnson [step 3]"
        employee_name: Name of the affected employee (for ticket assignment context).
        workflow_id: Workflow UUID for audit tracking.
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
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Escalated issue: {issue}", action_taken="escalate_to_it_tool",
            agent_name="ExecutionAgent", tool_name="escalate_to_it_tool", status="completed"
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: lookup_tool_reliability
# ────────────────────────────────────────
@mcp.tool()
def lookup_tool_reliability(tool_name: str, workflow_id: str = "") -> str:
    """Query audit logs to get real-time success/failure statistics for any tool.

    USE CASES:
      - Before choosing a recovery strategy: check if a tool is consistently failing
        (suggests ESCALATE) vs. occasionally failing (suggests RETRY).
      - Planner intelligence: if a tool has a known low reliability, plan an alternate path.
      - Post-incident analysis: understand how many times a tool failed in a workflow.
      - Compliance reporting: get tool-level success rates for audit.

    INTERPRETATION:
      success_rate = -1       → No data available in the last 24h
      success_rate >= 50%     → RETRY is recommended (transient failures)
      success_rate <  50%     → ESCALATE is recommended (systemic failures)

    Returns:
      { "success": true, "data": {
          "tool_name": "...",
          "success_count": N,
          "failure_count": N,
          "total_calls": N,
          "success_rate": 75.0,
          "recommendation": "RETRY" | "ESCALATE" | "UNKNOWN"
      }}

    Args:
        tool_name: Exact tool name to check e.g. "create_jira_account_tool".
        workflow_id: Workflow UUID for audit tracking (optional).
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') as success_count,
                COUNT(*) FILTER (WHERE status = 'failed') as failure_count,
                COUNT(*) as total_count
            FROM audit_logs
            WHERE tool_name = %s
            AND timestamp > NOW() - INTERVAL '24 hours'
        """, (tool_name,))
        row = cursor.fetchone()
        conn.close()

        success = row[0] or 0
        failures = row[1] or 0
        total = row[2] or 0
        rate = round(success / total * 100, 1) if total > 0 else -1  # -1 = no data

        result = {
            "success": True,
            "tool": "lookup_tool_reliability",
            "data": {
                "tool_name": tool_name,
                "success_count": success,
                "failure_count": failures,
                "total_calls": total,
                "success_rate": rate,
                "recommendation": "RETRY" if rate >= 50 else ("ESCALATE" if rate >= 0 else "UNKNOWN")
            }
        }
    except Exception as e:
        result = {"success": False, "error": str(e), "tool": "lookup_tool_reliability"}

    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: get_workflow_context_tool
# ────────────────────────────────────────
@mcp.tool()
def get_workflow_context_tool(workflow_id: str) -> str:
    """Retrieve all completed step outputs for the current workflow from the database.

    USE CASES:
      - When a later step needs data produced by an earlier step but it wasn't passed forward.
      - Recovery: re-read what the prior step produced before retrying.
      - Context enrichment: pull meeting_link, employee_id, buddy_name set in earlier steps.
      - Debugging: understand exactly what each step in the workflow produced.

    IMPORTANT DISTINCTION:
      - Use this tool to retrieve WORKFLOW STEP OUTPUTS (what tools returned).
      - Use execute_sql to query EMPLOYEE / AUDIT / WORKFLOW DATABASE RECORDS directly.
      - Do NOT use this tool to query external systems or look up employee emails.

    Returns:
      { "success": true, "data": {
          "<step_name>": { "tool": "...", "status": "COMPLETED", "output": { ... } },
          ...
      }}

    Args:
        workflow_id: Workflow UUID — required.
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT step_name, tool_name, status, current_output
            FROM steps
            WHERE workflow_id = %s
            ORDER BY dependency_order ASC
        """, (workflow_id,))
        rows = cursor.fetchall()
        conn.close()

        context = {}
        for step_name, tool_name, status, output in rows:
            parsed = output
            if isinstance(parsed, str):
                try:
                    parsed = json.loads(parsed)
                except Exception:
                    pass
            context[step_name or tool_name] = {
                "tool": tool_name,
                "status": status,
                "output": parsed
            }

        result = {
            "success": True,
            "tool": "get_workflow_context_tool",
            "message": f"Retrieved context for {len(context)} steps",
            "data": context
        }
    except Exception as e:
        result = {"success": False, "error": str(e), "tool": "get_workflow_context_tool"}

    return json.dumps(result, default=_json_serial)


# ────────────────────────────────────────
# TOOL: send_onboarding_email_tool
# ────────────────────────────────────────
@mcp.tool()
def send_onboarding_email_tool(
    employee_name: str,
    employee_email: str,
    company_email: str = "",
    buddy_name: str = "",
    buddy_email: str = "",
    meeting_link: str = "",
    meeting_time: str = "10:00 AM",
    role: str = "",
    department: str = "",
    workflow_id: str = ""
) -> str:
    """Send a rich HTML welcome email to a new employee with ICS calendar invite attached.

    This is the primary employee-facing communication for onboarding. It includes:
      - Personalized welcome message with role and department.
      - Company email credentials section.
      - Orientation meeting link and time with .ics calendar attachment.
      - Buddy/mentor details with contact info.

    USE CASES:
      - Final onboarding step: send after HR account, email account, meeting, and buddy are set up.
      - Partial onboarding: send even if some fields are empty — tool handles gracefully.
      - Re-send: safe to call again if first attempt failed (SMTP retryable).

    PARAMETER RESOLUTION GUIDE (use execute_sql or prior step outputs):
      employee_email → SELECT email FROM employees WHERE LOWER(name) = LOWER('<name>')
      company_email  → SELECT company_email FROM employees WHERE LOWER(name) = LOWER('<name>')
      buddy_name     → SELECT buddy FROM employees WHERE LOWER(name) = LOWER('<name>')
      buddy_email    → SELECT email FROM employees WHERE LOWER(name) = LOWER('<buddy_name>')
      meeting_link   → from schedule_meeting_tool output
      meeting_time   → from schedule_meeting_tool output

    Returns:
      { "success": true, "data": { "to": "...", "subject": "...", "meeting_link": "...",
                                   "buddy": "...", "ics_attached": true } }

    Args:
        employee_name: Full name of the new employee (appears in greeting).
        employee_email: Personal email to send the welcome to — REQUIRED, must be non-empty.
        company_email: Company email provisioned (shown in email). Optional.
        buddy_name: Assigned mentor name. Optional.
        buddy_email: Assigned mentor email. Optional.
        meeting_link: URL from schedule_meeting_tool. Optional.
        meeting_time: Orientation time string or ISO datetime. Optional.
        role: Job title. Optional.
        department: Department name. Optional.
        workflow_id: Workflow UUID for audit tracking.
    """
    # Build the rich HTML body
    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; border-radius: 12px; overflow: hidden; border: 1px solid #e0e0e0;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 32px 24px; text-align: center;">
            <h1 style="color: #fff; margin: 0; font-size: 28px;">🎉 Welcome to the Team!</h1>
            <p style="color: rgba(255,255,255,0.85); margin: 8px 0 0; font-size: 15px;">We're thrilled to have you aboard</p>
        </div>

        <!-- Body -->
        <div style="padding: 28px 24px; background: #fff;">
            <p style="font-size: 16px; color: #333;">Hello <b>{employee_name}</b>,</p>
            <p style="font-size: 15px; color: #555; line-height: 1.7;">
                Welcome to <b>Avataar AI</b>! We are excited to have you join us as a
                <b>{role or 'team member'}</b> in the <b>{department or 'team'}</b>.
                Below you'll find everything you need to get started on Day 1.
            </p>

            <!-- Company Email -->
            <div style="background: #eef2ff; border-left: 4px solid #667eea; padding: 14px 18px; border-radius: 6px; margin: 18px 0;">
                <p style="margin: 0; font-size: 14px; color: #667eea; font-weight: 600;">📧 Your Company Email</p>
                <p style="margin: 6px 0 0; font-size: 16px; color: #333; font-weight: bold;">{company_email or 'Will be shared shortly'}</p>
            </div>

            <!-- Orientation Meeting -->
            <div style="background: #f0fdf4; border-left: 4px solid #22c55e; padding: 14px 18px; border-radius: 6px; margin: 18px 0;">
                <p style="margin: 0; font-size: 14px; color: #16a34a; font-weight: 600;">📅 Orientation Meeting</p>
                <p style="margin: 6px 0 0; font-size: 15px; color: #333;">⏰ <b>Time:</b> {meeting_time}</p>
                <p style="margin: 4px 0 0; font-size: 15px; color: #333;">🔗 <b>Link:</b> <a href="{meeting_link}" style="color: #2563eb;">{meeting_link or 'TBD'}</a></p>
                <p style="margin: 6px 0 0; font-size: 12px; color: #888;">A calendar invite is attached to this email.</p>
            </div>

            <!-- Buddy / Mentor -->
            <div style="background: #fefce8; border-left: 4px solid #eab308; padding: 14px 18px; border-radius: 6px; margin: 18px 0;">
                <p style="margin: 0; font-size: 14px; color: #ca8a04; font-weight: 600;">🤝 Your Buddy / Mentor</p>
                <p style="margin: 6px 0 0; font-size: 15px; color: #333;"><b>{buddy_name or 'To be assigned'}</b></p>
                <p style="margin: 4px 0 0; font-size: 14px; color: #555;">📧 {buddy_email or ''}</p>
                <p style="margin: 6px 0 0; font-size: 13px; color: #888;">Your buddy will help you settle in and answer any questions during your first weeks.</p>
            </div>

            <p style="font-size: 15px; color: #555; line-height: 1.7; margin-top: 20px;">
                If you have any questions before your start date, don't hesitate to reach out.
                We look forward to seeing you!
            </p>

            <p style="font-size: 15px; color: #333; margin-top: 24px;">Best regards,<br><b>HR Team — Avataar AI</b></p>
        </div>

        <!-- Footer -->
        <div style="background: #f1f5f9; padding: 16px 24px; text-align: center; font-size: 12px; color: #94a3b8;">
            This is an automated email from Enterprise Autopilot.
        </div>
    </div>
    """

    # Generate ICS calendar invite
    ics_content = _generate_ics(
        summary=f"Orientation Meeting — {employee_name}",
        description=f"Welcome orientation for {employee_name} ({role}). Buddy: {buddy_name}.",
        meeting_link=meeting_link or "https://meet.avataar.ai/orientation",
        start_str=meeting_time
    )

    try:
        _send_html_email(employee_email, f"🎉 Welcome to Avataar AI, {employee_name}!", html_body, ics_content)
        result = {
            "success": True,
            "message": "Onboarding email sent successfully via SMTP",
            "data": {
                "to": employee_email,
                "subject": f"Welcome to Avataar AI, {employee_name}!",
                "meeting_link": meeting_link,
                "buddy": buddy_name,
                "ics_attached": True
            },
            "tool": "send_onboarding_email_tool"
        }
        status = "completed"
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "message": "Failed to send onboarding email",
            "tool": "send_onboarding_email_tool"
        }
        status = "failed"

    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Sent welcome email to {employee_email}", action_taken="send_onboarding_email_tool",
            agent_name="ExecutionAgent", tool_name="send_onboarding_email_tool", status=status
        )
    return json.dumps(result)



# ────────────────────────────────────────
# TOOL: send_orientation_email_tool
# ────────────────────────────────────────
@mcp.tool()
def send_orientation_email_tool(
    recipient_emails: str,
    new_employee_name: str,
    role: str = "",
    department: str = "",
    meeting_link: str = "",
    meeting_time: str = "10:00 AM",
    workflow_id: str = ""
) -> str:
    """Send orientation notification emails to colleagues/team about a new hire joining.

    Notifies existing employees that a new team member is starting. Includes orientation
    meeting details and an ICS calendar invite so colleagues can attend.

    USE CASES:
      - Notify the whole department about a new hire's orientation.
      - Alert same-role colleagues so they can help the new hire onboard.
      - Send a single notification to the buddy/mentor about their new mentee.
      - Broadcast to a specific set of stakeholders about a new team member.

    HOW TO GET recipient_emails (use execute_sql before this step):
      SELECT email FROM employees
      WHERE LOWER(department) = LOWER('<department>')
        AND status = 'ACTIVE'
        AND LOWER(name) != LOWER('<new_hire_name>')
      → collect all emails, join as comma-separated string.

    NOTE: recipient_emails is a COMMA-SEPARATED string of email addresses.
          Example: "alice@co.com,bob@co.com,carol@co.com"

    Returns:
      { "success": true, "data": { "sent": ["..."], "failed": [...], "ics_attached": true } }

    Args:
        recipient_emails: Comma-separated email addresses of all recipients.
        new_employee_name: Name of the new hire (appears in email body).
        role: New hire's role/title.
        department: New hire's department.
        meeting_link: Orientation meeting URL from schedule_meeting_tool output.
        meeting_time: Orientation meeting time string.
        workflow_id: Workflow UUID for audit tracking.
    """
    emails = [e.strip() for e in recipient_emails.split(",") if e.strip()]
    if not emails:
        return json.dumps({"success": False, "error": "No recipient emails provided", "tool": "send_orientation_email_tool"})

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8f9fa; border-radius: 12px; overflow: hidden; border: 1px solid #e0e0e0;">
        <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 28px 24px; text-align: center;">
            <h1 style="color: #fff; margin: 0; font-size: 24px;">👋 New Team Member Joining!</h1>
        </div>
        <div style="padding: 24px; background: #fff;">
            <p style="font-size: 15px; color: #333;">Hi there,</p>
            <p style="font-size: 15px; color: #555; line-height: 1.7;">
                We're excited to let you know that <b>{new_employee_name}</b> is joining as a
                <b>{role or 'new team member'}</b> in <b>{department or 'the team'}</b>.
            </p>
            <p style="font-size: 15px; color: #555; line-height: 1.7;">
                An orientation meeting has been scheduled. Since you work in a related field,
                your presence will help them settle in quickly!
            </p>
            <div style="background: #f0fdf4; border-left: 4px solid #22c55e; padding: 14px 18px; border-radius: 6px; margin: 18px 0;">
                <p style="margin: 0; font-size: 14px; color: #16a34a; font-weight: 600;">📅 Orientation Details</p>
                <p style="margin: 6px 0 0; font-size: 15px; color: #333;">⏰ <b>Time:</b> {meeting_time}</p>
                <p style="margin: 4px 0 0; font-size: 15px; color: #333;">🔗 <b>Link:</b> <a href="{meeting_link}" style="color: #2563eb;">{meeting_link or 'TBD'}</a></p>
            </div>
            <p style="font-size: 14px; color: #888;">Please make yourself available to welcome {new_employee_name}!</p>
            <p style="font-size: 15px; color: #333; margin-top: 20px;">Best,<br><b>HR Team — Avataar AI</b></p>
        </div>
        <div style="background: #f1f5f9; padding: 12px 24px; text-align: center; font-size: 12px; color: #94a3b8;">
            Automated notification from Enterprise Autopilot.
        </div>
    </div>
    """

    ics_content = _generate_ics(
        summary=f"Orientation — Welcome {new_employee_name}",
        description=f"{new_employee_name} is joining as {role}. Please attend the orientation.",
        meeting_link=meeting_link or "https://meet.avataar.ai/orientation",
        start_str=meeting_time
    )

    sent = []
    failed = []
    for email_addr in emails:
        try:
            _send_html_email(email_addr, f"👋 New Team Member: {new_employee_name} — Orientation Invite", html_body, ics_content)
            sent.append(email_addr)
        except Exception as e:
            failed.append({"email": email_addr, "error": str(e)})

    result = {
        "success": len(failed) == 0,
        "message": f"Orientation emails sent to {len(sent)}/{len(emails)} colleagues",
        "data": {"sent": sent, "failed": failed, "ics_attached": True},
        "tool": "send_orientation_email_tool"
    }

    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Sent orientation emails for {new_employee_name} to {len(sent)} colleagues",
            action_taken="send_orientation_email_tool",
            agent_name="ExecutionAgent", tool_name="send_orientation_email_tool",
            status="completed" if not failed else "partial"
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: create_task_tool
# ────────────────────────────────────────
@mcp.tool()
def create_task_tool(title: str, description: str, assignee: str = "", priority: str = "medium", reason: str = "", workflow_id: str = "") -> str:
    """Create and assign an action-item task to a person.

    USE CASES:
      - Convert meeting action items into trackable tasks (one task per action item).
      - Assign onboarding tasks to HR, IT, or the buddy/mentor.
      - Create follow-up tasks after a workflow escalation (e.g. "Grant JIRA access for Alice").
      - Any ad-hoc work item that needs to be tracked and assigned.

    NOTE: This is distinct from create_jira_account_tool (which creates a JIRA USER ACCOUNT).
          create_task_tool creates a TASK/TICKET assigned to a person.

    IMPORTANT: If the owner/assignee is unclear or ambiguous, pass assignee="" (empty string).
    The task will be created with status="ambiguous" and flagged for human review.
    NEVER fabricate or guess an assignee — an empty assignee is always better than a wrong one.

    Returns:
      { "success": true, "data": { "task_id": "TASK-XXXX", "title": "...", "assignee": "...", "priority": "..." } }

    Args:
        title: Short task title e.g. "UI Refresh implementation".
        description: Detailed description of what needs to be done and why.
        assignee: Email of the person responsible (from identity table). Pass "" if unknown/ambiguous.
        priority: "low" | "medium" | "high" | "critical"
        reason: WHY this person is assigned and HOW this task was identified. Be specific:
                - Quote the transcript line that created the task (e.g. "sarveswaran said 'we should track deployment metrics'")
                - Explain the assignment basis (e.g. "Assigned to sarveswaran because he explicitly volunteered: 'I can take responsibility for testing'")
                - For ambiguous tasks: state what role/context suggests ownership (e.g. "No explicit owner; HR suggested by context")
                NEVER use generic strings like 'Created by tool during workflow execution'.
        workflow_id: Workflow UUID for audit tracking.
    """
    time.sleep(0.3)
    effective_reason = reason.strip() if reason.strip() else (
        f"Assigned to {assignee} based on workflow context." if assignee
        else "No explicit owner identified; task flagged for human review."
    )
    try:
        task_row = db.create_task(
            title=title,
            description=description,
            owner=assignee or None,
            status="pending" if assignee else "ambiguous",
            priority=priority,
            source_meeting_id=None,
            raw_text=description,
            parsed_intent={"title": title, "description": description},
            reason_for_creation=effective_reason,
            confidence_score=0.95 if assignee else 0.4,
        )
        try:
            db.log_enterprise_audit(
                entity_type="task",
                entity_id=task_row["task_id"],
                event_type="TASK_CREATED_BY_TOOL",
                message=effective_reason,
                actor="execution_agent",
                metadata={"workflow_id": workflow_id, "priority": priority, "ambiguous": not bool(assignee)},
            )
        except Exception:
            pass  # audit failure must never block task creation

        result = {
            "success": True,
            "message": f"Task '{title}' created and assigned to {assignee or 'unassigned (ambiguous)'}",
            "tool": "create_task_tool",
            "data": {
                "task_id": task_row["task_id"],
                "title": task_row["title"],
                "assignee": task_row["owner"],
                "priority": task_row["priority"],
                "status": task_row["status"],
            },
            "retryable": False,
        }
    except Exception as e:
        result = {
            "success": False,
            "error": f"Failed to create task: {str(e)}",
            "tool": "create_task_tool",
            "retryable": False,
        }
    if workflow_id:
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Created task: {title} → {assignee or '(ambiguous)'}", action_taken="create_task_tool",
            agent_name="ExecutionAgent", tool_name="create_task_tool", status="completed"
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: send_summary_email_tool
# ────────────────────────────────────────
@mcp.tool()
def send_summary_email_tool(to: str, summary: str, subject: str = "Meeting Summary", workflow_id: str = "") -> str:
    """Send a structured summary email to a stakeholder or group.

    USE CASES:
      - Send meeting action items summary to all participants after processing a transcript.
      - Deliver an onboarding completion summary to HR.
      - Send a post-incident report after an SLA breach was handled.
      - Notify a manager with a workflow execution summary.
      - Share audit results or compliance reports with team leads.

    HOW TO GET recipient email (use execute_sql if not known):
      SELECT email FROM employees WHERE LOWER(name) = LOWER('<recipient_name>')

    Returns:
      { "success": true, "data": { "message_id": "msg-xxxx", "to": "...", "subject": "..." } }

    Args:
        to: Recipient email address — must be a real, deliverable address.
        summary: The full content of the summary. Can be plain text or HTML.
                 For meeting action items: include who is responsible for what and by when.
        subject: Email subject line. Default: "Meeting Summary". Be specific when possible.
        workflow_id: Workflow UUID for audit tracking.
    """
    try:
        _send_html_email(to, subject, summary)
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
        db.log_audit(
            workflow_id=workflow_id, decision="tool_executed",
            reason=f"Summary email to {to}: {subject}", action_taken="send_summary_email_tool",
            agent_name="ExecutionAgent", tool_name="send_summary_email_tool", status=status
        )
    return json.dumps(result)


# ────────────────────────────────────────
# TOOL: reroute_approval_tool
# ────────────────────────────────────────
@mcp.tool()
def reroute_approval_tool(step_name: str, from_agent: str, to_agent: str, reason: str, workflow_id: str = "") -> str:
    """Reroute a stuck or failed approval/task to a different person or agent.

    USE CASES:
      - Approver is on leave → find a delegate via execute_sql, then reroute the approval.
      - Agent exhausted retries on a step → reroute to a human or different system.
      - SLA about to breach → fast-track the task to a senior approver.
      - Load balancing: redistribute a task pile-up across available team members.

    HOW TO FIND A DELEGATE (use execute_sql):
      SELECT name, email FROM employees
      WHERE LOWER(department) = LOWER('<department>')
        AND status = 'ACTIVE'
        AND LOWER(name) != LOWER('<original_approver>')
      LIMIT 1

    Returns:
      { "success": true, "data": {
          "step_name": "...", "from_agent": "...", "to_agent": "...",
          "reason": "...", "reroute_id": "RR-XXXX"
      }}

    Args:
        step_name: The name of the workflow step being rerouted.
        from_agent: Original assignee or responsible agent/person.
        to_agent: New assignee, person, or system to handle the step.
        reason: Clear explanation — why is this being rerouted? Cite SLA, absence, error.
        workflow_id: Workflow UUID for audit tracking.
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
        db.log_audit(
            workflow_id=workflow_id, decision="rerouted", reason=reason,
            action_taken=f"reroute_approval_tool: {from_agent} → {to_agent}",
            agent_name="HealthMonitorAgent", tool_name="reroute_approval_tool", status="completed"
        )
    return json.dumps(result)




# ── Entry point ──
if __name__ == "__main__":
    # Initialize DB for direct tool usage
    try:
        init_db()
    except Exception:
        pass
    mcp.run(transport="stdio")
