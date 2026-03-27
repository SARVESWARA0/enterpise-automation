"""
All database operations as pure functions.
Maps directly to Prisma schema tables using snake_case DB column names.
"""
import json
import uuid
from datetime import datetime, timezone
from .connection import get_conn


# ── EMPLOYEES ────────────────────────────────────────────────────────────────

def create_employee(name: str, email: str, role: str, department: str) -> dict:
    """Insert a new employee with PENDING status. Returns the full row."""
    emp_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO employees (id, name, email, role, department, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, 'PENDING', NOW(), NOW())
            RETURNING id, employee_id, name, email, role, department, status, created_at
        """, (emp_id, name, email, role, department))
        row = cur.fetchone()
        return _row_to_dict(cur, row)


def update_employee_status(employee_id: str, status: str, employee_db_id: str = None) -> bool:
    """Update employee status. Can target by UUID or employee_id string (EMP-XXXX)."""
    with get_conn() as conn:
        cur = conn.cursor()
        if employee_db_id:
            cur.execute("""
                UPDATE employees SET status = %s, updated_at = NOW()
                WHERE id = %s
            """, (status, employee_db_id))
        else:
            cur.execute("""
                UPDATE employees SET status = %s, updated_at = NOW()
                WHERE employee_id = %s
            """, (status, employee_id))
        return cur.rowcount > 0


def update_employee_fields(employee_db_id: str, fields: dict) -> bool:
    """Update arbitrary employee fields (e.g. company_email, buddy_id, employee_id)."""
    if not fields:
        return False
    set_clauses = ", ".join([f"{k} = %s" for k in fields.keys()])
    values = list(fields.values()) + [employee_db_id]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE employees SET {set_clauses}, updated_at = NOW()
            WHERE id = %s
        """, values)
        return cur.rowcount > 0


def get_all_employees() -> list[dict]:
    """Fetch all employees for the employee list page."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.employee_id, e.name, e.email, e.company_email, e.role, e.department,
                   e.buddy, e.status, e.created_at
            FROM employees e
            ORDER BY e.created_at DESC
        """)
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]


def get_employee_by_id(employee_db_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM employees WHERE id = %s", (employee_db_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_employee_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM employees WHERE email = %s", (email,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_employee_by_name(name: str) -> dict | None:
    """Case-insensitive employee lookup by name."""
    if not name:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM employees WHERE LOWER(name) = LOWER(%s) LIMIT 1",
            (name,),
        )
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_active_employees_in_dept(department: str) -> list[dict]:
    """For buddy assignment — find active colleagues in the same department."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, email, role, department FROM employees
            WHERE department = %s AND status = 'ACTIVE'
            ORDER BY RANDOM() LIMIT 5
        """, (department,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


# ── WORKFLOWS ────────────────────────────────────────────────────────────────

def create_workflow(workflow_type: str, trigger_event: str,
                    entity_id: str = None, input_data: dict = None) -> dict:
    wf_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO workflows (id, type, entity_id, trigger_event, input_data, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, 'PENDING', NOW(), NOW())
            RETURNING id, type, status, created_at
        """, (wf_id, workflow_type, entity_id, trigger_event,
              json.dumps(input_data) if input_data else None))
        return _row_to_dict(cur, cur.fetchone())


def update_workflow_status(workflow_id: str, status: str, plan: list = None) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        if plan:
            cur.execute("""
                UPDATE workflows SET status = %s, plan = %s, updated_at = NOW()
                WHERE id = %s
            """, (status, json.dumps(plan), workflow_id))
        else:
            cur.execute("""
                UPDATE workflows SET status = %s, updated_at = NOW() WHERE id = %s
            """, (status, workflow_id))
        return cur.rowcount > 0


def get_all_workflows() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type, entity_id, trigger_event, status, created_at, updated_at
            FROM workflows ORDER BY created_at DESC
        """)
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def get_workflow(workflow_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT w.*,
                   json_agg(
                       json_build_object(
                           'id', s.id,
                           'step_name', s.step_name,
                           'step_type', s.step_type,
                           'tool_name', s.tool_name,
                           'status', s.status,
                           'retry_count', s.retry_count,
                           'dependency_order', s.dependency_order,
                           'current_output', s.current_output
                       ) ORDER BY s.dependency_order
                   ) FILTER (WHERE s.id IS NOT NULL) as steps
            FROM workflows w
            LEFT JOIN steps s ON s.workflow_id = w.id
            WHERE w.id = %s
            GROUP BY w.id
        """, (workflow_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


# ── STEPS ────────────────────────────────────────────────────────────────────

def create_step(workflow_id: str, step_name: str, step_type: str,
                tool_name: str, input_data: dict,
                dependency_order: int, assigned_agent: str = "execution",
                fallback_behavior: str = "ESCALATE") -> dict:
    step_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO steps (id, workflow_id, step_name, step_type, status,
                               retry_count, max_retries, assigned_agent, tool_name,
                               input_data, dependency_order, fallback_behavior, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'PENDING', 0, 2, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id, step_name, status, tool_name
        """, (step_id, workflow_id, step_name, step_type, assigned_agent,
              tool_name, json.dumps(input_data), dependency_order, fallback_behavior))
        return _row_to_dict(cur, cur.fetchone())


def update_step(step_id: str, status: str, output: dict = None,
                retry_count: int = None) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        sets = ["status = %s", "updated_at = NOW()"]
        vals = [status]
        if output is not None:
            sets.append("current_output = %s")
            vals.append(json.dumps(output))
        if retry_count is not None:
            sets.append("retry_count = %s")
            vals.append(retry_count)
        vals.append(step_id)
        cur.execute(f"UPDATE steps SET {', '.join(sets)} WHERE id = %s", vals)
        return cur.rowcount > 0


def get_step(step_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM steps WHERE id = %s", (step_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


# ── AGENT LOGS ───────────────────────────────────────────────────────────────

def log_agent_action(workflow_id: str, agent_name: str, action: str,
                     step_id: str = None, tool_name: str = None,
                     input_data: dict = None, output: dict = None,
                     duration_ms: int = None):
    log_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO agent_logs (id, workflow_id, step_id, agent_name, action,
                                    tool_name, input, output, duration_ms, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (log_id, workflow_id, step_id, agent_name, action, tool_name,
              json.dumps(input_data) if input_data else None,
              json.dumps(output) if output else None, duration_ms))


# ── AUDIT LOGS ───────────────────────────────────────────────────────────────

def log_audit(workflow_id: str, decision: str, reason: str,
              action_taken: str, agent_name: str, step_id: str = None,
              tool_name: str = None, retry_count: int = None, status: str = None):
    log_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_logs (id, workflow_id, step_id, decision, reason,
                                    action_taken, agent_name, tool_name, retry_count,
                                    status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (log_id, workflow_id, step_id, decision, reason, action_taken,
              agent_name, tool_name, retry_count, status))
    return {"id": log_id}


def get_audit_logs(workflow_id: str) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM audit_logs WHERE workflow_id = %s ORDER BY timestamp ASC
        """, (workflow_id,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def get_all_audits() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM audit_logs ORDER BY timestamp DESC
        """)
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


# ── SEED ─────────────────────────────────────────────────────────────────────

def seed_employees():
    """Create initial employees if table is empty."""
    existing = get_all_employees()
    if existing:
        return
    seeds = [
        ("Alice Johnson", "alice.johnson@company.com", "Software Engineer", "Engineering"),
        ("Bob Smith", "bob.smith@company.com", "Product Manager", "Product"),
        ("Carol Williams", "carol.williams@company.com", "Designer", "Design"),
        ("David Chen", "david.chen@company.com", "DevOps Engineer", "Engineering"),
        ("Eva Martinez", "eva.martinez@company.com", "HR Manager", "Human Resources"),
    ]
    for name, email, role, dept in seeds:
        emp = create_employee(name, email, role, dept)
        update_employee_status("", "ACTIVE", employee_db_id=emp["id"])
    print(f"[DB] Seeded {len(seeds)} employees")


# ── HELPER ───────────────────────────────────────────────────────────────────

def _row_to_dict(cur, row) -> dict | None:
    if row is None:
        return None
    cols = [desc[0] for desc in cur.description]
    result = {}
    for col, val in zip(cols, row):
        # Convert datetime to ISO string for JSON serialization
        if isinstance(val, datetime):
            result[col] = val.isoformat()
        else:
            result[col] = val
    return result
