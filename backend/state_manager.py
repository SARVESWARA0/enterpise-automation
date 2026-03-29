"""
File-based state management for Enterprise Autopilot.
All state is stored as JSON files for full transparency and audit.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

STATE_DIR = os.getenv("STATE_DIR", os.path.join(os.path.dirname(__file__), "state"))


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- Employees ----------

def create_employee(name: str, email: str, role: str, department: str) -> dict:
    emp_dir = os.path.join(STATE_DIR, "employees")
    _ensure_dir(emp_dir)
    emp_id = str(uuid.uuid4())
    emp = {
        "id": emp_id,
        "employeeId": None,
        "name": name,
        "email": email,
        "role": role,
        "department": department,
        "status": "PENDING",
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    with open(os.path.join(emp_dir, f"{emp_id}.json"), "w") as f:
        json.dump(emp, f, indent=2)
    return emp


def update_employee(emp_id: str, updates: dict) -> dict:
    emp_dir = os.path.join(STATE_DIR, "employees")
    path = os.path.join(emp_dir, f"{emp_id}.json")
    if not os.path.exists(path):
        raise ValueError(f"Employee not found: {emp_id}")
    with open(path) as f:
        emp = json.load(f)
    emp.update(updates)
    emp["updatedAt"] = _now()
    with open(path, "w") as f:
        json.dump(emp, f, indent=2)
    return emp


def get_employee(emp_id: str) -> Optional[dict]:
    path = os.path.join(STATE_DIR, "employees", f"{emp_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_employees() -> list[dict]:
    emp_dir = os.path.join(STATE_DIR, "employees")
    _ensure_dir(emp_dir)
    employees = []
    for fname in sorted(os.listdir(emp_dir), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(emp_dir, fname)) as f:
                employees.append(json.load(f))
    return employees


# ---------- Workflows ----------

def create_workflow(wf_type: str, input_data: dict, steps: list[dict], entity_id: str | None = None) -> dict:
    wf_dir = os.path.join(STATE_DIR, "workflows")
    _ensure_dir(wf_dir)
    wf_id = str(uuid.uuid4())
    if input_data is None:
        input_data = {}
    wf = {
        "id": wf_id,
        "type": wf_type,
        "entityId": entity_id,
        "triggerEvent": input_data.get("triggerEvent", "manual"),
        "inputData": input_data,
        "status": "PENDING",
        "plan": steps,
        "steps": steps,
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    with open(os.path.join(wf_dir, f"{wf_id}.json"), "w") as f:
        json.dump(wf, f, indent=2)
    return wf


def update_workflow(wf_id: str, updates: dict) -> dict:
    wf_dir = os.path.join(STATE_DIR, "workflows")
    path = os.path.join(wf_dir, f"{wf_id}.json")
    if not os.path.exists(path):
        raise ValueError(f"Workflow not found: {wf_id}")
    with open(path) as f:
        wf = json.load(f)
    wf.update(updates)
    wf["updatedAt"] = _now()
    with open(path, "w") as f:
        json.dump(wf, f, indent=2)
    return wf


def get_workflow(wf_id: str) -> Optional[dict]:
    path = os.path.join(STATE_DIR, "workflows", f"{wf_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_workflows() -> list[dict]:
    wf_dir = os.path.join(STATE_DIR, "workflows")
    _ensure_dir(wf_dir)
    workflows = []
    for fname in sorted(os.listdir(wf_dir), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(wf_dir, fname)) as f:
                workflows.append(json.load(f))
    return workflows


# ---------- Audit Logs ----------

def append_audit_log(workflow_id: str, entry: dict):
    audit_dir = os.path.join(STATE_DIR, "audit")
    _ensure_dir(audit_dir)
    entry["id"] = str(uuid.uuid4())
    entry["workflowId"] = workflow_id
    entry["timestamp"] = _now()

    # Append to workflow-specific audit file
    path = os.path.join(audit_dir, f"{workflow_id}.json")
    logs = []
    if os.path.exists(path):
        with open(path) as f:
            logs = json.load(f)
    logs.append(entry)
    with open(path, "w") as f:
        json.dump(logs, f, indent=2)
    return entry


def get_audit_logs(workflow_id: str | None = None) -> list[dict]:
    audit_dir = os.path.join(STATE_DIR, "audit")
    _ensure_dir(audit_dir)
    if workflow_id:
        path = os.path.join(audit_dir, f"{workflow_id}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return []
    # All audit logs
    all_logs = []
    for fname in sorted(os.listdir(audit_dir), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(audit_dir, fname)) as f:
                all_logs.extend(json.load(f))
    all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return all_logs


def update_step_status(workflow_id: str, step_index: int, updates: dict) -> dict | None:
    """Update a single step within a workflow's step list.

    Args:
        workflow_id: The workflow ID.
        step_index: Index of the step to update.
        updates: Dict of fields to update on the step.

    Returns:
        The updated workflow dict, or None if not found.
    """
    wf = get_workflow(workflow_id)
    if not wf:
        return None
    steps = wf.get("steps", [])
    if step_index < 0 or step_index >= len(steps):
        return None
    steps[step_index].update(updates)
    return update_workflow(workflow_id, {"steps": steps})



# ---------- Stream Events ----------

import threading

_stream_lock = threading.Lock()

def append_stream_event(workflow_id: str, event: dict):
    """Write event to a stream file for SSE polling, thread-safe."""
    stream_dir = os.path.join(STATE_DIR, "streams")
    _ensure_dir(stream_dir)
    event["timestamp"] = _now()
    path = os.path.join(stream_dir, f"{workflow_id}.json")
    
    with _stream_lock:
        events = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                try:
                    events = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        events.append(event)
        
        # Write to a temporary file then rename for atomic replacement
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(events, f)
        os.replace(temp_path, path)


def get_stream_events(workflow_id: str, after_index: int = 0) -> list[dict]:
    path = os.path.join(STATE_DIR, "streams", f"{workflow_id}.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        try:
            events = json.load(f)
        except json.JSONDecodeError:
            return []
    return events[after_index:]


# ---------- Dashboard ----------

def get_dashboard_stats() -> dict:
    employees = list_employees()
    workflows = list_workflows()
    return {
        "employees": {
            "total": len(employees),
            "active": sum(1 for e in employees if e.get("status") == "ACTIVE"),
        },
        "workflows": {
            "total": len(workflows),
            "running": sum(1 for w in workflows if w.get("status") == "RUNNING"),
            "completed": sum(1 for w in workflows if w.get("status") == "COMPLETED"),
            "failed": sum(1 for w in workflows if w.get("status") == "FAILED"),
            "escalated": sum(1 for w in workflows if w.get("status") == "ESCALATED"),
        },
        "recentActivity": get_audit_logs()[:10],
    }


# ---------- Seed initial employees ----------

def seed_employees():
    """Create initial employees if none exist."""
    if list_employees():
        return
    for name, email, role, dept in [
        ("Alice Johnson", "alice.johnson@company.com", "Software Engineer", "Engineering"),
        ("Bob Smith", "bob.smith@company.com", "Product Manager", "Product"),
        ("Carol Williams", "carol.williams@company.com", "Designer", "Design"),
        ("David Chen", "david.chen@company.com", "DevOps Engineer", "Engineering"),
        ("Eva Martinez", "eva.martinez@company.com", "HR Manager", "Human Resources"),
    ]:
        emp = create_employee(name, email, role, dept)
        update_employee(emp["id"], {"status": "ACTIVE"})
    print(f"Seeded {len(list_employees())} employees")
