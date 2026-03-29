"""
All database operations as pure functions.
Maps directly to Prisma schema tables using snake_case DB column names.
"""
import json
import uuid
from datetime import datetime, timezone, timedelta
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
                    entity_id: str = None, input_data: dict = None,
                    scheduled_at: str = None) -> dict:
    wf_id = str(uuid.uuid4())
    status = 'SCHEDULED' if scheduled_at else 'PENDING'
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO workflows (id, type, entity_id, trigger_event, input_data, status, scheduled_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s::timestamptz, NOW(), NOW())
            RETURNING *
        """, (wf_id, workflow_type, entity_id, trigger_event,
              json.dumps(input_data) if input_data else None, status, scheduled_at))
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


def update_workflow_type(workflow_id: str, workflow_type: str) -> bool:
    """Update workflow.type for governance/UI clarity."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE workflows SET type = %s, updated_at = NOW() WHERE id = %s",
            (workflow_type, workflow_id),
        )
        return cur.rowcount > 0


def get_all_workflows() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT *
            FROM workflows ORDER BY created_at DESC LIMIT 100
        """)
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def get_scheduled_pending_workflows() -> list[dict]:
    """Get workflows that are scheduled but not yet triggered."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM workflows
            WHERE scheduled_at IS NOT NULL
              AND status = 'SCHEDULED'
            ORDER BY scheduled_at ASC
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
            SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 500
        """)
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def list_pending_approvals() -> list[dict]:
    """Optimized query: fetch only pending/breached approvals for SLA daemon."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM approval_requests
            WHERE status IN ('pending', 'breached')
            ORDER BY sla_deadline ASC
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
        ("Frank Lee", "frank.lee@company.com", "Senior AI Engineer", "IT"),
        ("Grace Kim", "grace.kim@company.com", "IT Operations Lead", "IT"),
        ("Hannah Patel", "hannah.patel@company.com", "HR Coordinator", "HR"),
    ]
    for name, email, role, dept in seeds:
        emp = create_employee(name, email, role, dept)
        update_employee_status("", "ACTIVE", employee_db_id=emp["id"])
    print(f"[DB] Seeded {len(seeds)} employees")


# ── ENTERPRISE DOMAIN TABLES (Tasks/Meetings/SLA/WorkflowRun) ───────────────

def ensure_enterprise_tables():
    """Create/upgrade demo domain tables and employee hierarchy columns."""
    with get_conn() as conn:
        cur = conn.cursor()
        # Employee hierarchy/availability support for SLA reroute logic
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS manager_id TEXT")
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS availability_status TEXT DEFAULT 'available'")

        # Scheduled workflow support
        cur.execute("ALTER TABLE workflows ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ")
        
        # Add metadata json column to existing approval_requests table if needed
        cur.execute("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS metadata JSONB")
        
        # Add SCHEDULED to the enum if it doesn't exist
        try:
            cur.execute("ALTER TYPE \"WorkflowStatus\" ADD VALUE IF NOT EXISTS 'SCHEDULED'")
        except Exception as e:
            # Depending on PG version, ADD VALUE IF NOT EXISTS might not be supported in transaction blocks easily,
            # but psycopg2 with autocommit=True or outside transaction block is usually fine.
            # If it fails, fallback to ignoring it. We'll wrap this in a safe block.
            conn.rollback()
            pass

        # Prisma's @updatedAt does NOT generate a SQL DEFAULT — the column is created as
        # NOT NULL with no default, causing raw INSERT failures. Patch all affected tables.
        for tbl in ("tasks", "approval_requests", "workflow_runs", "workflow_run_steps"):
            cur.execute(f"""
                DO $$ BEGIN
                  IF EXISTS (SELECT 1 FROM information_schema.columns
                             WHERE table_name = '{tbl}' AND column_name = 'updated_at') THEN
                    ALTER TABLE {tbl} ALTER COLUMN updated_at SET DEFAULT NOW();
                  END IF;
                END $$;
            """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                meeting_id TEXT PRIMARY KEY,
                transcript TEXT NOT NULL,
                participants JSONB NOT NULL DEFAULT '[]'::jsonb,
                meeting_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT,
                status TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed','blocked','ambiguous')),
                priority TEXT NOT NULL DEFAULT 'medium',
                due_date TIMESTAMPTZ,
                source_meeting_id TEXT REFERENCES meetings(meeting_id) ON DELETE SET NULL,
                raw_text TEXT,
                parsed_intent JSONB,
                reason_for_creation TEXT,
                confidence_score DOUBLE PRECISION DEFAULT 0.0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS action_items (
                action_item_id TEXT PRIMARY KEY,
                task_id TEXT REFERENCES tasks(task_id) ON DELETE CASCADE,
                raw_text TEXT NOT NULL,
                parsed_intent JSONB,
                owner_detected TEXT,
                ambiguity_flag BOOLEAN NOT NULL DEFAULT FALSE,
                ambiguity_reason TEXT,
                possible_owners JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                approval_id TEXT PRIMARY KEY,
                request_type TEXT NOT NULL,
                current_approver TEXT,
                delegate_approver TEXT,
                status TEXT NOT NULL CHECK (status IN ('pending','approved','escalated','rerouted','breached')),
                sla_deadline TIMESTAMPTZ NOT NULL,
                last_reminder_sent_at TIMESTAMPTZ,
                email_sent_status TEXT DEFAULT 'pending',
                reroute_reason TEXT,
                metadata JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                workflow_run_id TEXT PRIMARY KEY,
                workflow_type TEXT NOT NULL,
                current_step TEXT,
                step_status TEXT NOT NULL DEFAULT 'pending',
                input_payload JSONB,
                output_payload JSONB,
                error_message TEXT,
                retry_count INT NOT NULL DEFAULT 0,
                escalation_status TEXT DEFAULT 'none',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow_run_steps (
                id TEXT PRIMARY KEY,
                workflow_run_id TEXT REFERENCES workflow_runs(workflow_run_id) ON DELETE CASCADE,
                step_name TEXT NOT NULL,
                step_status TEXT NOT NULL,
                input_payload JSONB,
                output_payload JSONB,
                error_message TEXT,
                retry_count INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS enterprise_audit_logs (
                log_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                metadata JSONB
            )
        """)

        # ── Performance Indexes ──
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status)",
            "CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status)",
            "CREATE INDEX IF NOT EXISTS idx_enterprise_audit_entity ON enterprise_audit_logs(entity_type, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_steps_workflow_id ON steps(workflow_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_workflow_id ON audit_logs(workflow_id)",
            "CREATE INDEX IF NOT EXISTS idx_workflows_scheduled ON workflows(scheduled_at) WHERE scheduled_at IS NOT NULL AND status = 'SCHEDULED'",
        ]:
            try:
                cur.execute(idx_sql)
            except Exception:
                pass  # index may already exist or table missing


def log_enterprise_audit(entity_type: str, entity_id: str, event_type: str,
                         message: str, actor: str, metadata: dict | None = None) -> dict:
    log_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO enterprise_audit_logs (log_id, entity_type, entity_id, event_type, message, actor, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (log_id, entity_type, entity_id, event_type, message, actor,
              json.dumps(metadata) if metadata is not None else None))
    return {"log_id": log_id}


def get_enterprise_audits(entity_type: str | None = None, entity_id: str | None = None, limit: int = 300) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        where = []
        vals = []
        if entity_type:
            where.append("entity_type = %s")
            vals.append(entity_type)
        if entity_id:
            where.append("entity_id = %s")
            vals.append(entity_id)
        sql = "SELECT * FROM enterprise_audit_logs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY timestamp DESC LIMIT %s"
        vals.append(limit)
        cur.execute(sql, tuple(vals))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def create_meeting(transcript: str, participants: list[str], source: str = "manual",
                   meeting_date: str | None = None) -> dict:
    meeting_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO meetings (meeting_id, transcript, participants, source, meeting_date)
            VALUES (%s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))
            RETURNING *
        """, (meeting_id, transcript, json.dumps(participants), source, meeting_date))
        return _row_to_dict(cur, cur.fetchone())


def get_meeting(meeting_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM meetings WHERE meeting_id = %s", (meeting_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def create_task(title: str, description: str, owner: str | None, status: str,
                priority: str = "medium", due_date: str | None = None,
                source_meeting_id: str | None = None, raw_text: str | None = None,
                parsed_intent: dict | None = None, reason_for_creation: str | None = None,
                confidence_score: float = 0.0) -> dict:
    task_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        # created_at and updated_at are explicit because Prisma @updatedAt does NOT add a
        # SQL DEFAULT — the column is NOT NULL without a default when created via prisma migrate.
        cur.execute("""
            INSERT INTO tasks (task_id, title, description, owner, status, priority, due_date,
                               source_meeting_id, raw_text, parsed_intent, reason_for_creation,
                               confidence_score, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING *
        """, (task_id, title, description, owner, status, priority, due_date, source_meeting_id,
              raw_text, json.dumps(parsed_intent) if parsed_intent is not None else None,
              reason_for_creation, confidence_score))
        return _row_to_dict(cur, cur.fetchone())


def update_task(task_id: str, patch: dict) -> dict | None:
    allowed = {
        "title", "description", "owner", "status", "priority", "due_date",
        "raw_text", "parsed_intent", "reason_for_creation", "confidence_score"
    }
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        return get_task(task_id)
    sets = []
    vals = []
    for k, v in fields.items():
        if k in ("parsed_intent",):
            sets.append(f"{k} = %s")
            vals.append(json.dumps(v) if v is not None else None)
        elif k == "due_date":
            sets.append("due_date = %s::timestamptz")
            vals.append(v)
        else:
            sets.append(f"{k} = %s")
            vals.append(v)
    sets.append("updated_at = NOW()")
    vals.append(task_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = %s RETURNING *", tuple(vals))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_task(task_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def list_tasks() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks ORDER BY updated_at DESC")
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def create_action_item(task_id: str, raw_text: str, parsed_intent: dict | None,
                       owner_detected: str | None, ambiguity_flag: bool,
                       ambiguity_reason: str | None = None, possible_owners: list[str] | None = None) -> dict:
    action_item_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO action_items (action_item_id, task_id, raw_text, parsed_intent, owner_detected,
                                      ambiguity_flag, ambiguity_reason, possible_owners)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (action_item_id, task_id, raw_text,
              json.dumps(parsed_intent) if parsed_intent is not None else None,
              owner_detected, ambiguity_flag, ambiguity_reason, json.dumps(possible_owners or [])))
        return _row_to_dict(cur, cur.fetchone())


def list_action_items_for_task(task_id: str) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM action_items WHERE task_id = %s ORDER BY created_at ASC", (task_id,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def create_approval_request(request_type: str, current_approver: str | None, sla_deadline: str, metadata: dict | None = None) -> dict:
    approval_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO approval_requests (approval_id, request_type, current_approver, status,
                                           sla_deadline, email_sent_status, metadata, created_at, updated_at)
            VALUES (%s, %s, %s, 'pending', %s::timestamptz, 'pending', %s, NOW(), NOW())
            RETURNING *
        """, (approval_id, request_type, current_approver, sla_deadline, json.dumps(metadata) if metadata else None))
        return _row_to_dict(cur, cur.fetchone())


def update_approval(approval_id: str, patch: dict) -> dict | None:
    allowed = {
        "request_type", "current_approver", "delegate_approver", "status",
        "sla_deadline", "last_reminder_sent_at", "email_sent_status", "reroute_reason", "metadata"
    }
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        return get_approval(approval_id)
    sets = []
    vals = []
    for k, v in fields.items():
        if k in ("sla_deadline", "last_reminder_sent_at"):
            sets.append(f"{k} = %s::timestamptz")
            vals.append(v)
        elif k == "metadata":
            sets.append(f"{k} = %s")
            vals.append(json.dumps(v) if v is not None else None)
        else:
            sets.append(f"{k} = %s")
            vals.append(v)
    sets.append("updated_at = NOW()")
    vals.append(approval_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE approval_requests SET {', '.join(sets)} WHERE approval_id = %s RETURNING *", tuple(vals))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def list_approvals() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM approval_requests ORDER BY updated_at DESC")
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def get_approval(approval_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM approval_requests WHERE approval_id = %s", (approval_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def find_delegate_for_approver(current_approver: str | None) -> dict | None:
    """
    Determine delegate via manager chain / availability.
    Rules:
      1) Current approver's manager (if available)
      2) Any active+available employee in same department, excluding current approver
      3) None (caller should escalate)
    """
    if not current_approver:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, email, role, department, manager_id, availability_status
            FROM employees
            WHERE LOWER(name) = LOWER(%s) OR LOWER(email) = LOWER(%s)
            LIMIT 1
        """, (current_approver, current_approver))
        approver = cur.fetchone()
        if not approver:
            return None
        approver_d = _row_to_dict(cur, approver)

        manager_id = approver_d.get("manager_id")
        if manager_id:
            cur.execute("""
                SELECT id, name, email, role, department, availability_status
                FROM employees
                WHERE (id = %s OR employee_id = %s)
                  AND COALESCE(availability_status, 'available') = 'available'
                LIMIT 1
            """, (manager_id, manager_id))
            manager = cur.fetchone()
            if manager:
                return _row_to_dict(cur, manager)

        cur.execute("""
            SELECT id, name, email, role, department, availability_status
            FROM employees
            WHERE LOWER(department) = LOWER(%s)
              AND COALESCE(availability_status, 'available') = 'available'
              AND LOWER(name) != LOWER(%s)
            ORDER BY created_at ASC
            LIMIT 1
        """, (approver_d.get("department"), approver_d.get("name")))
        peer = cur.fetchone()
        return _row_to_dict(cur, peer) if peer else None


def create_workflow_run(workflow_type: str, input_payload: dict | None = None) -> dict:
    workflow_run_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO workflow_runs (workflow_run_id, workflow_type, current_step, step_status,
                                       input_payload, created_at, updated_at)
            VALUES (%s, %s, '', 'pending', %s, NOW(), NOW())
            RETURNING *
        """, (workflow_run_id, workflow_type, json.dumps(input_payload) if input_payload is not None else None))
        return _row_to_dict(cur, cur.fetchone())


def update_workflow_run(workflow_run_id: str, patch: dict) -> dict | None:
    allowed = {
        "workflow_type", "current_step", "step_status", "input_payload", "output_payload",
        "error_message", "retry_count", "escalation_status"
    }
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        return get_workflow_run(workflow_run_id)
    sets = []
    vals = []
    for k, v in fields.items():
        if k in ("input_payload", "output_payload"):
            sets.append(f"{k} = %s")
            vals.append(json.dumps(v) if v is not None else None)
        else:
            sets.append(f"{k} = %s")
            vals.append(v)
    sets.append("updated_at = NOW()")
    vals.append(workflow_run_id)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE workflow_runs SET {', '.join(sets)} WHERE workflow_run_id = %s RETURNING *", tuple(vals))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_workflow_run(workflow_run_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM workflow_runs WHERE workflow_run_id = %s", (workflow_run_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_workflow_runs_for_approval(approval_id: str) -> list[dict]:
    """Find workflow runs linked to an approval via input_payload.approval_id."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM workflow_runs
            WHERE input_payload->>'approval_id' = %s
            ORDER BY created_at DESC
            """,
            (approval_id,),
        )
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def add_workflow_run_step(workflow_run_id: str, step_name: str, step_status: str,
                          input_payload: dict | None = None, output_payload: dict | None = None,
                          error_message: str | None = None, retry_count: int = 0) -> dict:
    step_id = str(uuid.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO workflow_run_steps (id, workflow_run_id, step_name, step_status,
                                            input_payload, output_payload, error_message,
                                            retry_count, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING *
        """, (
            step_id, workflow_run_id, step_name, step_status,
            json.dumps(input_payload) if input_payload is not None else None,
            json.dumps(output_payload) if output_payload is not None else None,
            error_message, retry_count
        ))
        return _row_to_dict(cur, cur.fetchone())


def list_workflow_run_steps(workflow_run_id: str) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM workflow_run_steps WHERE workflow_run_id = %s ORDER BY created_at ASC", (workflow_run_id,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def parse_meeting_action_items(transcript: str, participants: list[str]) -> list[dict]:
    """
    Deterministic parser for demo:
    - Splits by '.', ';', and newlines.
    - Keeps action-like sentences containing verbs.
    - Detects owner by name mention from participants.
    - Flags ambiguity when owner cannot be resolved.
    """
    verbs = ("update", "review", "prepare", "create", "schedule", "migrate", "fix", "send", "handle")
    parts = []
    for raw in transcript.replace("\n", ". ").split("."):
        text = raw.strip(" -\t\r\n")
        if text:
            parts.append(text)
    items = []
    for part in parts:
        lower = part.lower()
        if not any(v in lower for v in verbs):
            continue
        possible = [p for p in participants if p and p.lower() in lower]
        owner = possible[0] if len(possible) == 1 else None
        ambiguity_flag = owner is None
        ambiguity_reason = None
        if ambiguity_flag:
            if len(possible) > 1:
                ambiguity_reason = "Multiple possible owners were mentioned."
            else:
                ambiguity_reason = "No clear owner mentioned in the transcript."
        items.append({
            "raw_text": part,
            "owner_detected": owner,
            "ambiguity_flag": ambiguity_flag,
            "ambiguity_reason": ambiguity_reason,
            "possible_owners": possible,
            "confidence_score": 0.9 if owner else (0.5 if possible else 0.35),
        })
    return items


# ── HELPER ───────────────────────────────────────────────────────────────────

def _row_to_dict(cur, row) -> dict | None:
    if row is None:
        return None
    cols = [desc[0] for desc in cur.description]
    result = {}
    for col, val in zip(cols, row):
        # Convert datetime to ISO string for JSON serialization
        if isinstance(val, datetime):
            if val.tzinfo is None:
                val = val.astimezone(timezone.utc)
            result[col] = val.isoformat()
        else:
            result[col] = val
    return result
