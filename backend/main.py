"""
Enterprise Autopilot — FastAPI Application
All state in PostgreSQL via db.queries. SSE from workflow engine.
"""
import asyncio
import traceback
import os
import sys

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from dotenv import load_dotenv
load_dotenv()

# Ensure backend dir is on path
sys.path.insert(0, os.path.dirname(__file__))

from db.connection import init_db
from db import queries as db
from models import OnboardingRequest, WorkflowStartRequest
from orchestrator.workflow_engine import run_workflow, sse_stream, get_or_create_queue
from state_manager import get_stream_events

app = FastAPI(title="ET Autopilot", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Lifecycle ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    db.seed_employees()
    print("[API] Enterprise Autopilot v2 ready")


# ── Employees ────────────────────────────────────────────────────────────────

@app.get("/api/employees")
async def list_employees():
    return db.get_all_employees()


@app.get("/api/employees/{employee_id}")
async def get_employee(employee_id: str):
    emp = db.get_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    return emp


# ── Workflows ────────────────────────────────────────────────────────────────

@app.get("/api/workflows")
async def list_workflows():
    return db.get_all_workflows()

@app.post("/api/workflows/start")
async def start_workflow(req: WorkflowStartRequest, bg: BackgroundTasks):
    """
    Start a new workflow. If name/email/role/department are provided,
    creates an employee record first.
    """
    entity_id = None

    # If onboarding data is provided, get or create the employee
    if req.name and req.email:
        emp = db.get_employee_by_email(req.email)
        if not emp:
            # Fallback: try matching by name to avoid creating duplicates with guessed emails.
            emp = db.get_employee_by_name(req.name)
            if not emp:
                emp = db.create_employee(
                    name=req.name, email=req.email,
                    role=req.role or "Employee",
                    department=req.department or "General"
                )
        entity_id = emp["id"]
    elif req.name:
        # If only name exists, do not require email here; run_workflow steps can resolve it from DB.
        emp = db.get_employee_by_name(req.name)
        if emp:
            entity_id = emp["id"]

    # Create workflow record
    wf = db.create_workflow(
        workflow_type=req.trigger,
        trigger_event=req.trigger,
        entity_id=entity_id,
        input_data={"request": req.request, "name": req.name,
                     "email": req.email, "role": req.role,
                     "department": req.department}
    )

    # Ensure queue exists before background task starts
    get_or_create_queue(wf["id"])

    # Start async workflow in background
    bg.add_task(_run_workflow_bg, wf["id"], req.request)

    return {"workflowId": wf["id"], "status": "STARTED"}


async def _run_workflow_bg(workflow_id: str, user_request: str):
    """Background task wrapper."""
    try:
        await run_workflow(workflow_id, user_request)
    except Exception as e:
        traceback.print_exc()
        try:
            db.update_workflow_status(workflow_id, "FAILED")
            queue = get_or_create_queue(workflow_id)
            await queue.put({
                "event_type": "workflow_complete",
                "agent": "system",
                "data": {"status": "FAILED", "error": str(e)[:500]},
            })
        except Exception:
            pass


@app.get("/api/workflows/{workflow_id}/stream")
async def workflow_stream(workflow_id: str):
    """SSE endpoint — streams real-time workflow events."""
    return StreamingResponse(
        sse_stream(workflow_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


@app.get("/api/workflows/{workflow_id}/events")
async def get_workflow_events(workflow_id: str):
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return {"events": get_stream_events(workflow_id)}


@app.get("/api/workflows/{workflow_id}/audit")
async def get_workflow_audit(workflow_id: str):
    return db.get_audit_logs(workflow_id)


@app.get("/api/audits")
async def list_audits():
    return db.get_all_audits()


# ── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard():
    employees = db.get_all_employees()
    return {
        "employees": {
            "total": len(employees),
            "active": sum(1 for e in employees if e.get("status") == "ACTIVE"),
        },
    }


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
