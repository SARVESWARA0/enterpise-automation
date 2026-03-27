"""
Shared database schema context for all agents.
Imported by interpreter, execution, and context-handling agents so they all have
an accurate model of what data exists and how to query it via execute_sql.
"""

DB_SCHEMA_CONTEXT = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATABASE SCHEMA  (PostgreSQL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TABLE: employees
  id            UUID PRIMARY KEY
  employee_id   TEXT          — generated HR code e.g. "EMP-4821" (may be NULL before HR account creation)
  name          TEXT          — full name, stored as-is (case may vary)
  email         TEXT UNIQUE   — personal/contact email
  company_email TEXT          — company provisioned email (may be NULL before email account creation)
  role          TEXT          — job title e.g. "Software Engineer"
  department    TEXT          — team/department e.g. "Engineering"
  buddy         TEXT          — assigned buddy/mentor name (may be NULL)
  status        ENUM          — PENDING | ONBOARDING | ACTIVE | FAILED
  created_at    TIMESTAMP
  updated_at    TIMESTAMP

TABLE: workflows
  id            UUID PRIMARY KEY
  type          TEXT          — workflow kind e.g. "employee_onboarding"
  entity_id     UUID          — FK to employees.id (nullable)
  trigger_event TEXT
  input_data    JSON
  status        ENUM          — PENDING | PLANNING | RUNNING | COMPLETED | FAILED | ESCALATED
  plan          JSON
  created_at    TIMESTAMP
  updated_at    TIMESTAMP

TABLE: steps
  id               UUID PRIMARY KEY
  workflow_id      UUID FK → workflows.id
  step_name        TEXT
  step_type        TEXT
  status           ENUM — PENDING | RUNNING | COMPLETED | FAILED | RETRIED | ESCALATED | SKIPPED
  retry_count      INT
  max_retries      INT
  assigned_agent   TEXT
  tool_name        TEXT
  input_data       JSON
  current_output   JSON
  dependency_order INT
  created_at       TIMESTAMP
  updated_at       TIMESTAMP

TABLE: audit_logs
  id            UUID PRIMARY KEY
  workflow_id   UUID FK → workflows.id
  step_id       UUID FK → steps.id (nullable)
  decision      TEXT  — e.g. "tool_executed", "ESCALATED", "COMPLETED"
  reason        TEXT
  action_taken  TEXT
  agent_name    TEXT
  tool_name     TEXT
  retry_count   INT
  status        TEXT  — "completed" | "failed" | "info" | "RECOVERY" etc.
  timestamp     TIMESTAMP

TABLE: agent_logs
  id            UUID PRIMARY KEY
  workflow_id   UUID
  step_id       UUID (nullable)
  agent_name    TEXT
  action        TEXT
  tool_name     TEXT
  input         JSON
  output        JSON
  duration_ms   INT
  timestamp     TIMESTAMP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPORTANT QUERY RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Always use LOWER() or ILIKE for name comparisons — names may be stored in mixed case.
- Prefer ILIKE '%value%' for fuzzy name/role/department matching.
- Use LIMIT when you need a single best match.
- You can JOIN employees → workflows via entity_id.
- execute_sql supports SELECT, INSERT, UPDATE, DELETE and multi-row results.
- Empty result set (rowCount=0, data=[]) is NOT an error for SELECT; it means no matching rows.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE: Intelligent buddy / mentor selection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When there is no dedicated "find_buddy" tool, use execute_sql intelligently:

  -- Find best mentor: same department, ACTIVE, not the new hire, most senior (earliest created_at)
  SELECT id, name, email, role, department
  FROM employees
  WHERE department ILIKE '<department>'
    AND status = 'ACTIVE'
    AND LOWER(name) != LOWER('<new_hire_name>')
  ORDER BY created_at ASC
  LIMIT 1;

  -- Then update the new hire's buddy field:
  UPDATE employees
  SET buddy = '<mentor_name>', updated_at = NOW()
  WHERE LOWER(name) = LOWER('<new_hire_name>');

EXAMPLE: Look up employee email by name (case-insensitive)
  SELECT email, name, role, department, company_email
  FROM employees
  WHERE LOWER(name) = LOWER('<employee_name>')
  LIMIT 1;

EXAMPLE: Get all active employees in a department
  SELECT name, email, role
  FROM employees
  WHERE LOWER(department) = LOWER('<department>')
    AND status = 'ACTIVE';

EXAMPLE: Count audit failures for a tool in last 24h
  SELECT COUNT(*) as failure_count
  FROM audit_logs
  WHERE tool_name = '<tool_name>'
    AND status = 'failed'
    AND timestamp > NOW() - INTERVAL '24 hours';
"""
