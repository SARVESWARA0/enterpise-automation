"""
Enterprise Autopilot — FastAPI Backend.
Multi-Agent Autonomous Workflow System powered by Strands Agents SDK.
"""
import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from state_manager import (
    create_employee, update_employee, get_employee, list_employees,
    create_workflow, update_workflow, get_workflow, list_workflows,
    get_audit_logs, get_stream_events, get_dashboard_stats,
    seed_employees, append_stream_event,
)
from orchestrator.workflow_engine import run_workflow, sse_stream, get_or_create_queue
import state_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_employees()
    yield


app = FastAPI(
    title="ET Autopilot — PS2 Workflow Engine",
    description="Multi-Agent Autonomous Workflow System",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────── Pydantic Models ────────────

class CreateEmployeeRequest(BaseModel):
    name: str
    email: str
    role: str
    department: str


class StartWorkflowRequest(BaseModel):
    request: str


# ──────────── DASHBOARD ────────────

@app.get("/api/dashboard")
async def dashboard():
    return get_dashboard_stats()


# ──────────── EMPLOYEES ────────────

@app.get("/api/employees")
async def get_employees():
    employees = list_employees()
    workflows = list_workflows()
    for emp in employees:
        emp_workflows = [w for w in workflows if w.get("entityId") == emp["id"]]
        emp["workflows"] = emp_workflows[:1]
    return employees


@app.post("/api/employees", status_code=201)
async def post_employee(req: CreateEmployeeRequest, background_tasks: BackgroundTasks):
    emp = create_employee(req.name, req.email, req.role, req.department)

    user_request = (
        f"Onboard new employee: {emp['name']} "
        f"({emp['role']} in {emp['department']}). "
        f"Email: {emp['email']}."
    )

    wf = create_workflow("employee_onboarding", {
        "employeeId": emp["id"],
        "name": emp["name"],
        "email": emp["email"],
        "role": emp["role"],
        "department": emp["department"],
        "triggerEvent": "employee_created",
    }, steps=[], entity_id=emp["id"])

    update_employee(emp["id"], {"status": "ONBOARDING"})

    # Pre-create SSE queue
    get_or_create_queue(wf["id"])

    background_tasks.add_task(_run_workflow, wf["id"], user_request)

    return {"employee": emp, "workflowId": wf["id"]}


# ──────────── WORKFLOWS ────────────

@app.post("/api/workflows/start")
async def start_workflow(body: StartWorkflowRequest, background_tasks: BackgroundTasks):
    """Start a workflow and return workflow_id. Frontend then connects to SSE."""
    workflow_id = str(uuid.uuid4())
    user_request = body.request

    # Create workflow in state
    wf = create_workflow("custom_workflow", {
        "request": user_request,
        "triggerEvent": "manual",
    }, steps=[], entity_id=None)

    # Pre-create SSE queue so SSE can connect before runner starts
    get_or_create_queue(wf["id"])

    background_tasks.add_task(_run_workflow, wf["id"], user_request)

    return {"workflow_id": wf["id"], "status": "started"}


@app.get("/api/workflows")
async def get_workflows_list(status: Optional[str] = None, type: Optional[str] = None):
    workflows = list_workflows()
    if status:
        workflows = [w for w in workflows if w.get("status") == status]
    if type:
        workflows = [w for w in workflows if w.get("type") == type]
    for wf in workflows:
        entity_id = wf.get("entityId")
        if entity_id:
            emp = get_employee(entity_id)
            wf["employee"] = {"name": emp["name"], "email": emp["email"]} if emp else None
        else:
            wf["employee"] = None
        audit = get_audit_logs(wf["id"])
        wf["_count"] = {"auditLogs": len(audit)}
    return workflows


@app.get("/api/workflows/{workflow_id}")
async def get_workflow_detail(workflow_id: str):
    wf = get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    entity_id = wf.get("entityId")
    wf["employee"] = get_employee(entity_id) if entity_id else None
    wf["auditLogs"] = get_audit_logs(workflow_id)
    wf["agentLogs"] = []
    return wf


# ──────────── SSE STREAM ────────────

@app.get("/api/workflows/{workflow_id}/stream")
async def stream_workflow(workflow_id: str):
    """SSE endpoint — frontend connects here for live updates."""
    return StreamingResponse(
        sse_stream(workflow_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


# ──────────── AUDIT ────────────

@app.get("/api/audit")
async def audit_logs(
    workflowId: Optional[str] = None,
    agentName: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, le=500),
):
    logs = get_audit_logs(workflowId)
    if agentName:
        logs = [l for l in logs if l.get("agentName") == agentName]
    if status:
        logs = [l for l in logs if l.get("status") == status]
    return logs[:limit]


# ──────────── SLA ────────────

@app.get("/api/sla")
async def sla_monitor():
    workflows = list_workflows()
    at_risk = [w for w in workflows if w.get("status") in ("RUNNING", "ESCALATED")]

    enriched = []
    for wf in at_risk:
        steps = wf.get("steps", [])
        completed = sum(1 for s in steps if s.get("status") == "COMPLETED")
        failed = sum(1 for s in steps if s.get("status") in ("FAILED", "ESCALATED"))
        total = len(steps)

        from datetime import datetime, timezone
        created = datetime.fromisoformat(wf.get("createdAt", datetime.now(timezone.utc).isoformat()))
        hours_elapsed = max(0, int((datetime.now(timezone.utc) - created).total_seconds() / 3600))

        wf["sla"] = {
            "completedSteps": completed,
            "failedSteps": failed,
            "totalSteps": total,
            "progress": round((completed / total * 100)) if total > 0 else 0,
            "hoursElapsed": hours_elapsed,
            "riskLevel": "critical" if failed > 0 else "high" if hours_elapsed > 24 else "medium" if hours_elapsed > 8 else "low",
        }

        entity = wf.get("entityId")
        if entity:
            emp = get_employee(entity)
            wf["employee"] = {"name": emp["name"]} if emp else None
        else:
            wf["employee"] = None
        enriched.append(wf)
    return enriched


# ──────────── Background Runner ────────────

def _run_workflow(workflow_id: str, user_request: str):
    """Run the orchestrator in a background thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_workflow(
            workflow_id=workflow_id,
            user_request=user_request,
            state_manager=state_manager,
        ))
    except Exception as e:
        print(f"Workflow execution error: {e}")
        import traceback
        traceback.print_exc()
        try:
            update_workflow(workflow_id, {"status": "FAILED"})
            append_stream_event(workflow_id, {
                "type": "workflow:failed",
                "workflowId": workflow_id,
                "message": f"Workflow failed: {str(e)}",
            })
        except Exception:
            pass
    finally:
        loop.close()


# ──────────── Run ────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
