"""
Enterprise Autopilot — FastAPI Application
All state in PostgreSQL via db.queries. SSE from workflow engine.
"""
import asyncio
import traceback
import os
import sys
import json
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse

from dotenv import load_dotenv
load_dotenv()

# Ensure backend dir is on path
sys.path.insert(0, os.path.dirname(__file__))

from db.connection import init_db
from db import queries as db
from models import (
    OnboardingRequest, WorkflowStartRequest, MeetingToActionRequest, TaskPatchRequest,
    AssignTaskOwnerRequest, CreateApprovalRequest, RerouteApprovalRequest
)
from orchestrator.workflow_engine import run_workflow, sse_stream, get_or_create_queue
from state_manager import get_stream_events
from mcp_server import send_email as send_email_tool
from document_processor import extract_metadata, validate_against_employee


def _parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _get_or_create_sla_workflow_run(approval_id: str, approval: dict) -> dict:
    runs = db.get_workflow_runs_for_approval(approval_id)
    if runs:
        return runs[0]
    return db.create_workflow_run(
        workflow_type="SLA_BREACH_PREVENTION",
        input_payload={
            "approval_id": approval_id,
            "request_type": approval.get("request_type"),
            "current_approver": approval.get("current_approver"),
        },
    )

app = FastAPI(title="ET Autopilot", version="2.0.0")
_sla_monitor_task: asyncio.Task | None = None
_onboarding_scheduler_task: asyncio.Task | None = None

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
    global _sla_monitor_task, _onboarding_scheduler_task
    init_db()
    db.ensure_enterprise_tables()
    db.seed_employees()
    if _sla_monitor_task is None or _sla_monitor_task.done():
        _sla_monitor_task = asyncio.create_task(_sla_monitor_daemon())
    if _onboarding_scheduler_task is None or _onboarding_scheduler_task.done():
        _onboarding_scheduler_task = asyncio.create_task(_onboarding_scheduler_daemon())
    print("[API] Enterprise Autopilot v2 ready")


@app.on_event("shutdown")
async def shutdown():
    global _sla_monitor_task, _onboarding_scheduler_task
    for task in (_sla_monitor_task, _onboarding_scheduler_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except Exception:
                pass


async def _sla_monitor_daemon():
    """Background SLA daemon: auto-monitors overdue pending approvals."""
    print("[SLA Daemon] Started background monitor loop.")
    while True:
        try:
            now = datetime.now(timezone.utc)
            pending = db.list_pending_approvals()
            if pending:
                print(f"[SLA Daemon] Checking {len(pending)} pending/breached approvals at {now.isoformat()}")
            for a in pending:
                try:
                    deadline = _parse_iso_datetime(a.get("sla_deadline"))
                except Exception as e:
                    print(f"[SLA Daemon] Parse error for {a.get('approval_id')}: {e}")
                    continue
                if now > deadline:
                    print(f"[SLA Daemon] >>> TRIGGERING monitor for {a['approval_id']}")
                    try:
                        result = await _run_approval_monitor(a["approval_id"])
                        print(f"[SLA Daemon] Monitor result: {result.get('action', 'completed')}")
                    except Exception as monitor_err:
                        print(f"[SLA Daemon] Monitor failed for {a['approval_id']}: {monitor_err}")
                        traceback.print_exc()
        except asyncio.CancelledError:
            print("[SLA Daemon] Cancelled.")
            raise
        except Exception as e:
            print(f"[SLA Daemon] CRITICAL ERROR: {e}")
            traceback.print_exc()
        await asyncio.sleep(30)


async def _onboarding_scheduler_daemon():
    """Background daemon: auto-triggers SCHEDULED workflows when their scheduled_at time arrives."""
    print("[Scheduler] Started onboarding scheduler loop.")
    while True:
        try:
            now = datetime.now(timezone.utc)
            scheduled = db.get_scheduled_pending_workflows()
            for wf in scheduled:
                try:
                    sched_at = _parse_iso_datetime(wf.get("scheduled_at"))
                except Exception as e:
                    print(f"[Scheduler] Parse error for {wf.get('id')}: {e}")
                    continue
                if now >= sched_at:
                    wf_id = wf["id"]
                    input_data = wf.get("input_data") or {}
                    if isinstance(input_data, str):
                        input_data = json.loads(input_data)
                    user_request = input_data.get("request", "")
                    print(f"[Scheduler] >>> TRIGGERING scheduled workflow: {wf_id}")
                    try:
                        # Move status from SCHEDULED → PENDING so it starts
                        db.update_workflow_status(wf_id, "PENDING")
                        get_or_create_queue(wf_id)
                        db.log_enterprise_audit(
                            "workflow", wf_id, "WORKFLOW_AUTO_TRIGGERED",
                            f"Scheduled workflow triggered at {now.isoformat()}.",
                            "onboarding_scheduler",
                            {"scheduled_at": wf.get("scheduled_at")}
                        )
                        await _run_workflow_bg(wf_id, user_request)
                        print(f"[Scheduler] Workflow {wf_id[:8]}... completed.")
                    except Exception as run_err:
                        print(f"[Scheduler] Workflow {wf_id[:8]}... failed: {run_err}")
                        traceback.print_exc()
        except asyncio.CancelledError:
            print("[Scheduler] Cancelled.")
            raise
        except Exception as e:
            print(f"[Scheduler] CRITICAL ERROR: {e}")
            traceback.print_exc()
        await asyncio.sleep(30)


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

# ── Employee Documents ───────────────────────────────────────────────────────

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


@app.post("/api/employees/{employee_id}/documents")
async def upload_employee_document(employee_id: str, file: UploadFile = File(...)):
    """Upload a document for an employee, extract metadata, and validate."""
    emp = db.get_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(404, "Employee not found")

    # Validate file type
    allowed_types = {
        "application/pdf": "pdf",
        "image/png": "image",
        "image/jpeg": "image",
        "image/jpg": "image",
        "image/webp": "image",
    }
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise HTTPException(400, f"Unsupported file type: {content_type}. Allowed: PDF, PNG, JPG, WebP")

    file_type = allowed_types[content_type]

    # Save file
    import uuid as _uuid
    ext = os.path.splitext(file.filename or "doc")[1] or (".pdf" if file_type == "pdf" else ".png")
    saved_filename = f"{_uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOADS_DIR, saved_filename)

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    file_size = len(contents)

    # Extract metadata
    try:
        extraction = extract_metadata(filepath, file_type, file.filename or "")
    except Exception as e:
        extraction = {"category": "unknown", "fields": {}, "error": str(e)}

    # Validate against employee record
    try:
        validation = validate_against_employee(extraction, emp)
    except Exception as e:
        validation = {"status": "pending", "score": 0, "fields": {}, "error": str(e)}

    # Save document record
    doc = db.create_employee_document(
        employee_id=employee_id,
        filename=saved_filename,
        original_name=file.filename or "unknown",
        file_type=file_type,
        file_size=file_size,
        document_category=extraction.get("category"),
        extracted_data=extraction,
        validation_status=validation.get("status", "pending"),
        validation_details=validation,
    )

    # Audit log
    db.log_enterprise_audit(
        "employee_document", doc["id"], "DOCUMENT_UPLOADED",
        f"Document '{file.filename}' uploaded for {emp['name']}. Category: {extraction.get('category')}. Validation: {validation.get('status')}.",
        "document_api",
        {"employee_id": employee_id, "category": extraction.get("category"),
         "validation_status": validation.get("status"), "score": validation.get("score")},
    )

    return {"document": doc, "extraction": extraction, "validation": validation}


@app.get("/api/employees/{employee_id}/documents")
async def list_employee_documents(employee_id: str):
    """List all documents for an employee."""
    emp = db.get_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    docs = db.get_documents_for_employee(employee_id)
    return {"employee": emp, "documents": docs}


@app.get("/api/documents/{doc_id}/file")
async def serve_document_file(doc_id: str):
    """Serve an uploaded document file."""
    doc = db.get_employee_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    filepath = os.path.join(UPLOADS_DIR, doc["filename"])
    if not os.path.exists(filepath):
        raise HTTPException(404, "File not found on disk")
    return FileResponse(filepath, filename=doc["original_name"])


# ── Onboarding Document Processing (Parallel, Isolated from Agent Pipeline) ──

async def _process_onboarding_docs_bg(employee_id: str, filepaths: list[tuple[str, str, str]]):
    """
    Background task: processes uploaded documents via local Ollama (llama3).
    Runs IN PARALLEL with the onboarding workflow but is COMPLETELY ISOLATED.
    Document content NEVER enters the agent orchestration pipeline.

    Args:
        employee_id:  ID of the newly created employee
        filepaths:    list of (saved_filename, original_name, file_type)
    """
    emp = db.get_employee_by_id(employee_id)
    if not emp:
        return

    for saved_filename, original_name, file_type in filepaths:
        filepath = os.path.join(UPLOADS_DIR, saved_filename)
        try:
            print(f"[DocBg] Processing {original_name} for {emp['name']}...")

            # Extract metadata via local Ollama — isolated from orchestrator
            extraction = extract_metadata(filepath, file_type, original_name)

            # Validate name/email against employee record
            validation = validate_against_employee(extraction, emp)

            # Store in DB (only structured metadata, never raw text)
            doc = db.create_employee_document(
                employee_id=employee_id,
                filename=saved_filename,
                original_name=original_name,
                file_type=file_type,
                file_size=os.path.getsize(filepath),
                document_category=extraction.get("category"),
                extracted_data=extraction,
                validation_status=validation.get("status", "pending"),
                validation_details=validation,
            )

            db.log_enterprise_audit(
                "employee_document", doc["id"], "ONBOARDING_DOC_PROCESSED",
                f"Document '{original_name}' processed via Ollama for {emp['name']}. "
                f"Category: {extraction.get('category')}. "
                f"Validation: {validation.get('status')} (score: {validation.get('score', 0):.0%}). "
                f"Method: {extraction.get('extraction_method')}.",
                "document_processor",
                {
                    "employee_id": employee_id,
                    "category": extraction.get("category"),
                    "extraction_method": extraction.get("extraction_method"),
                    "validation_status": validation.get("status"),
                    "score": validation.get("score"),
                },
            )

            print(f"[DocBg] ✓ {original_name} → {extraction.get('category')} | {validation.get('status')}")

        except Exception as e:
            print(f"[DocBg] ✗ Failed processing {original_name}: {e}")
            try:
                db.log_enterprise_audit(
                    "employee_document", employee_id, "ONBOARDING_DOC_FAILED",
                    f"Failed to process document '{original_name}': {str(e)[:300]}",
                    "document_processor",
                    {"employee_id": employee_id, "original_name": original_name},
                )
            except Exception:
                pass


@app.post("/api/onboarding/start-with-docs")
async def start_onboarding_with_docs(
    bg: BackgroundTasks,
    name: str = Form(None),
    email: str = Form(None),
    role: str = Form(None),
    department: str = Form(None),
    onboarding_date: str = Form(None),
    onboarding_time: str = Form(None),
    trigger_mode: str = Form("immediate"),
    files: list[UploadFile] = File(default=[]),
):
    """
    Start an onboarding workflow AND upload identity documents in one request.

    The two operations run in PARALLEL and are ISOLATED:
      • Workflow engine receives only form data (name, email, role, dept)
      • Ollama doc processor receives only file bytes
      • Raw document content never enters the agent pipeline

    Accepts: multipart/form-data with any combination of:
      - Aadhaar PDF/image
      - PAN card PDF/image
      - Passport PDF/image
      + employee details as form fields
    """
    import uuid as _uuid
    files = files or []

    # 1. Get or create employee record
    emp = db.get_employee_by_email(email) if email else None
    if not emp and name:
        emp = db.get_employee_by_name(name)
    if not emp and name and email:
        emp = db.create_employee(
            name=name, email=email,
            role=role or "Employee",
            department=department or "General",
        )

    employee_id = emp["id"] if emp else None

    # 2. Save all uploaded files (just bytes → disk, no processing yet)
    allowed_types = {
        "application/pdf": "pdf",
        "image/png": "image",
        "image/jpeg": "image",
        "image/jpg": "image",
        "image/webp": "image",
    }
    saved_files = []
    for upload in files:
        ct = upload.content_type or ""
        if ct not in allowed_types:
            continue
        ext = os.path.splitext(upload.filename or "doc")[1] or ".pdf"
        saved_name = f"{_uuid.uuid4().hex}{ext}"
        fpath = os.path.join(UPLOADS_DIR, saved_name)
        content = await upload.read()
        with open(fpath, "wb") as f:
            f.write(content)
        saved_files.append((saved_name, upload.filename or "document", allowed_types[ct]))

    # 3. Build the workflow request string (NO document content)
    request_str = (
        f"Onboard {name} as a new {role} in the {department} department. "
        f"Email: {email}."
    )
    if onboarding_date and onboarding_time:
        request_str += f" Onboarding scheduled for {onboarding_date} at {onboarding_time}."

    scheduled_at = None
    if trigger_mode == "scheduled" and onboarding_date and onboarding_time:
        try:
            scheduled_at = datetime.fromisoformat(
                f"{onboarding_date}T{onboarding_time}"
            ).astimezone(timezone.utc).isoformat()
        except Exception:
            pass

    # 4. Create workflow record (agent gets ONLY metadata, never doc content)
    wf = db.create_workflow(
        workflow_type="employee_onboarding",
        trigger_event="employee_onboarding",
        entity_id=employee_id,
        input_data={
            "request": request_str,
            "name": name, "email": email,
            "role": role, "department": department,
            "doc_count": len(saved_files),  # only count, not content
        },
        scheduled_at=scheduled_at,
    )

    # 5a. Launch Ollama doc processing in background (ISOLATED from workflow)
    if employee_id and saved_files:
        bg.add_task(_process_onboarding_docs_bg, employee_id, saved_files)

    # 5b. Launch agent workflow in background (receives NO doc content)
    if not scheduled_at:
        get_or_create_queue(wf["id"])
        bg.add_task(_run_workflow_bg, wf["id"], request_str)
        status = "STARTED"
    else:
        db.log_enterprise_audit(
            "workflow", wf["id"], "WORKFLOW_SCHEDULED",
            f"Onboarding workflow scheduled for {scheduled_at}.",
            "workflow_api",
            {"scheduled_at": scheduled_at, "name": name},
        )
        status = "SCHEDULED"

    return {
        "workflowId": wf["id"],
        "employeeId": employee_id,
        "status": status,
        "scheduled_at": scheduled_at,
        "docs_queued": len(saved_files),
        "message": (
            f"Onboarding started. {len(saved_files)} document(s) queued for "
            f"local Ollama processing (isolated from agent pipeline)."
        ),
    }


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
                     "department": req.department},
        scheduled_at=req.scheduled_at,
    )

    # If scheduled for the future, don't start now
    if req.scheduled_at:
        db.log_enterprise_audit(
            "workflow", wf["id"], "WORKFLOW_SCHEDULED",
            f"Onboarding workflow scheduled for {req.scheduled_at}.",
            "workflow_api",
            {"scheduled_at": req.scheduled_at, "name": req.name}
        )
        return {"workflowId": wf["id"], "status": "SCHEDULED", "scheduled_at": req.scheduled_at}

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


@app.get("/api/enterprise-audits")
async def list_enterprise_audits():
    return db.get_enterprise_audits()


# ── Enterprise Domain APIs (Tasks / Meetings / SLA / Workflow Runs) ─────────

@app.post("/api/meetings/process")
async def process_meeting_to_action(req: MeetingToActionRequest):
    if not req.transcript.strip():
        raise HTTPException(400, "Transcript is required")

    meeting = db.create_meeting(
        transcript=req.transcript,
        participants=req.participants,
        source=req.source,
        meeting_date=req.meeting_date,
    )
    db.log_enterprise_audit(
        "meeting",
        meeting["meeting_id"],
        "MEETING_INGESTED",
        "Meeting transcript was ingested for action extraction.",
        "meeting_processor",
        {"participants": req.participants, "source": req.source},
    )

    parsed_items = db.parse_meeting_action_items(req.transcript, req.participants)
    created_tasks = []
    ambiguous_count = 0
    for item in parsed_items:
        status = "ambiguous" if item["ambiguity_flag"] else "pending"
        if status == "ambiguous":
            ambiguous_count += 1
        task = db.create_task(
            title=item["raw_text"][:120],
            description=item["raw_text"],
            owner=item["owner_detected"],
            status=status,
            priority="medium",
            source_meeting_id=meeting["meeting_id"],
            raw_text=item["raw_text"],
            parsed_intent={"intent": item["raw_text"]},
            reason_for_creation="Extracted from meeting transcript",
            confidence_score=item["confidence_score"],
        )
        db.create_action_item(
            task_id=task["task_id"],
            raw_text=item["raw_text"],
            parsed_intent={"intent": item["raw_text"]},
            owner_detected=item["owner_detected"],
            ambiguity_flag=item["ambiguity_flag"],
            ambiguity_reason=item["ambiguity_reason"],
            possible_owners=item["possible_owners"],
        )
        db.log_enterprise_audit(
            "task",
            task["task_id"],
            "TASK_CREATED",
            "Task was created from meeting transcript.",
            "meeting_processor",
            {
                "owner": task["owner"],
                "status": task["status"],
                "ambiguity_flag": item["ambiguity_flag"],
                "ambiguity_reason": item["ambiguity_reason"],
                "possible_owners": item["possible_owners"],
            },
        )
        created_tasks.append(task)

    summary = {
        "total_action_items": len(parsed_items),
        "tasks_created": len(created_tasks),
        "ambiguous_tasks": ambiguous_count,
        "clear_assignments": len(created_tasks) - ambiguous_count,
    }
    db.log_enterprise_audit(
        "meeting",
        meeting["meeting_id"],
        "MEETING_PROCESSED",
        "Meeting-to-action processing completed.",
        "meeting_processor",
        summary,
    )
    return {"meeting": meeting, "summary": summary, "tasks": created_tasks}


@app.get("/api/meetings/{meeting_id}")
async def get_meeting_details(meeting_id: str):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    tasks = [t for t in db.list_tasks() if t.get("source_meeting_id") == meeting_id]
    audits = db.get_enterprise_audits(entity_type="meeting", entity_id=meeting_id)
    return {"meeting": meeting, "tasks": tasks, "audits": audits}


@app.get("/api/tasks")
async def list_tasks():
    return db.list_tasks()


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    action_items = db.list_action_items_for_task(task_id)
    audits = db.get_enterprise_audits(entity_type="task", entity_id=task_id)
    return {"task": task, "action_items": action_items, "audits": audits}


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: str, req: TaskPatchRequest):
    patch = req.model_dump(exclude_none=True)
    updated = db.update_task(task_id, patch)
    if not updated:
        raise HTTPException(404, "Task not found")
    db.log_enterprise_audit(
        "task", task_id, "TASK_UPDATED",
        "Task fields were updated.", "task_api", patch
    )
    return updated


@app.post("/api/tasks/{task_id}/assign-owner")
async def assign_task_owner(task_id: str, req: AssignTaskOwnerRequest):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    updated = db.update_task(task_id, {"owner": req.owner, "status": "pending"})
    db.log_enterprise_audit(
        "task",
        task_id,
        "AMBIGUITY_RESOLVED",
        f"Ambiguous owner assignment resolved to {req.owner}.",
        req.actor,
        {"note": req.note, "previous_owner": task.get("owner")},
    )
    return updated


@app.post("/api/approvals")
async def create_approval(req: CreateApprovalRequest):
    approver_val = req.current_approver
    if isinstance(approver_val, dict):
        approver_str = approver_val.get("name") or approver_val.get("email") or str(approver_val)
    else:
        approver_str = approver_val

    metadata = req.model_dump()
    approval = db.create_approval_request(
        request_type=req.request_type,
        current_approver=approver_str,
        sla_deadline=req.sla_deadline,
        metadata=metadata
    )
    db.log_enterprise_audit(
        "approval",
        approval["approval_id"],
        "APPROVAL_CREATED",
        "Approval request created.",
        "approval_api",
        {
            "current_approver": req.current_approver,
            "sla_deadline": req.sla_deadline,
            "event_summary": req.event_summary,
            "auto_trigger_monitor": req.auto_trigger_monitor,
        },
    )
    run = _get_or_create_sla_workflow_run(approval["approval_id"], approval)
    db.add_workflow_run_step(
        workflow_run_id=run["workflow_run_id"],
        step_name="approval_created",
        step_status="completed",
        input_payload=req.model_dump(),
        output_payload={"approval_id": approval["approval_id"]},
    )
    # If auto-monitor is enabled, trigger monitor immediately (monitor function
    # itself decides whether it's overdue and what action is needed).
    try:
        if req.auto_trigger_monitor:
            monitor_result = await _run_approval_monitor(approval["approval_id"])
            return {
                "approval": monitor_result.get("approval", approval),
                "auto_monitored": True,
                "monitor_result": monitor_result,
                "workflow_run_id": run["workflow_run_id"],
            }
    except Exception:
        pass
    return {"approval": approval, "auto_monitored": False, "workflow_run_id": run["workflow_run_id"]}


@app.get("/api/approvals")
async def list_approvals():
    return db.list_approvals()


@app.get("/api/approvals/{approval_id}")
async def get_approval(approval_id: str):
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, "Approval not found")
    audits = db.get_enterprise_audits(entity_type="approval", entity_id=approval_id)
    runs = db.get_workflow_runs_for_approval(approval_id)
    workflow_run = None
    if runs:
        run = runs[0]
        workflow_run = {
            "run": run,
            "steps": db.list_workflow_run_steps(run["workflow_run_id"]),
            "audits": db.get_enterprise_audits(entity_type="workflow_run", entity_id=run["workflow_run_id"]),
        }
    return {"approval": approval, "audits": audits, "workflow_run": workflow_run}


@app.post("/api/approvals/{approval_id}/monitor")
async def monitor_approval(approval_id: str):
    return await _run_approval_monitor(approval_id)


async def _run_approval_monitor(approval_id: str):
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, "Approval not found")
    run = _get_or_create_sla_workflow_run(approval_id, approval)
    db.add_workflow_run_step(
        workflow_run_id=run["workflow_run_id"],
        step_name="monitor_invoked",
        step_status="in_progress",
        input_payload={"approval_id": approval_id},
    )

    if approval["status"] in ("approved", "escalated", "rerouted"):
        db.add_workflow_run_step(
            workflow_run_id=run["workflow_run_id"],
            step_name="terminal_state_skip",
            step_status="completed",
            output_payload={"status": approval["status"]},
        )
        return {"approval": approval, "message": "No monitoring action needed for terminal state."}

    now = datetime.now(timezone.utc)
    sla_deadline = _parse_iso_datetime(approval["sla_deadline"])
    is_overdue = now > sla_deadline

    if not is_overdue:
        db.log_enterprise_audit(
            "approval", approval_id, "SLA_CHECK_OK",
            "SLA check completed; request still within deadline.",
            "sla_monitor", {"deadline": approval["sla_deadline"]}
        )
        db.add_workflow_run_step(
            workflow_run_id=run["workflow_run_id"],
            step_name="sla_check_ok",
            step_status="completed",
            output_payload={"overdue": False},
        )
        return {"approval": approval, "overdue": False, "action": "none"}

    already_breached = approval["status"] == "breached"
    
    if not already_breached:
        approval = db.update_approval(approval_id, {"status": "breached"})
        db.log_enterprise_audit(
            "approval", approval_id, "SLA_BREACHED",
            "SLA deadline exceeded.",
            "sla_monitor", {"deadline": approval["sla_deadline"]}
        )
        db.add_workflow_run_step(
            workflow_run_id=run["workflow_run_id"],
            step_name="sla_breached",
            step_status="completed",
            output_payload={"status": "breached"},
        )

    # If there are AI instructions on breach, trigger a workflow instead of fixed escalation
    metadata = approval.get("metadata") or {}
    if_breached_instructions = metadata.get("if_breached")
    event_summary = metadata.get("event_summary", "No contextual summary.")

    if if_breached_instructions and not already_breached:
        prompt = (
            f"SLA Breach recorded for Approval {approval_id} ({approval.get('request_type')}).\n"
            f"Expected Approver: {approval.get('current_approver')}\n"
            f"Event Summary: {event_summary}\n\n"
            f"BREACH INSTRUCTIONS TO EXECUTE:\n{if_breached_instructions}"
        )
        
        # Create an official agent workflow so it's trackable
        wf = db.create_workflow(
            workflow_type="SLA_BREACH_RESPONSE",
            trigger_event="sla_monitor",
            input_data={"request": prompt, "approval_id": approval_id}
        )
        db.log_enterprise_audit(
            "approval", approval_id, "AGENT_WORKFLOW_TRIGGERED",
            "Agent triggered to resolve SLA breach based on if_breached instructions.",
            "sla_monitor",
            {"workflow_id": wf["id"], "instructions": if_breached_instructions}
        )
        db.add_workflow_run_step(
            workflow_run_id=run["workflow_run_id"],
            step_name="agent_workflow_triggered",
            step_status="completed",
            output_payload={"workflow_id": wf["id"]},
        )

        get_or_create_queue(wf["id"])
        asyncio.create_task(_run_workflow_bg(wf["id"], prompt))

        return {"approval": approval, "overdue": True, "action": "agent_workflow_started", "workflow_id": wf["id"]}
    elif if_breached_instructions and already_breached:
        # We already triggered the agent; do nothing
        return {"approval": approval, "overdue": True, "action": "agent_already_running"}

    # Fallback to standard email reminder -> delegation -> escalation
    approver = None
    approver_key = approval.get("current_approver")
    if approver_key:
        approver = db.get_employee_by_name(approver_key) or db.get_employee_by_email(approver_key)
    approver_is_active = bool(approver and str(approver.get("status", "")).upper() == "ACTIVE")

    # If current approver is ACTIVE: send reminder email first.
    if approver_is_active and not approval.get("last_reminder_sent_at"):
        to_email = approver.get("email")
        subject = f"[SLA BREACH] Action required: {approval.get('request_type')}"
        body = (
            f"Approval '{approval.get('request_type')}' has crossed the SLA deadline.\n"
            f"Please take action immediately.\n\n"
            f"Approval ID: {approval_id}\n"
            f"SLA Deadline: {approval.get('sla_deadline')}"
        )
        email_ok = False
        email_error = None
        if to_email:
            try:
                send_result = json.loads(send_email_tool(to=to_email, subject=subject, body=body, workflow_id=""))
                email_ok = bool(send_result.get("success"))
                email_error = send_result.get("error")
            except Exception as e:
                email_error = str(e)

        reminder_time = now.isoformat()
        approval = db.update_approval(
            approval_id,
            {
                "last_reminder_sent_at": reminder_time,
                "email_sent_status": "sent" if email_ok else "failed",
            },
        )
        db.log_enterprise_audit(
            "approval", approval_id, "REMINDER_SENT" if email_ok else "REMINDER_FAILED",
            f"Reminder attempted to current approver: {approval.get('current_approver')}.",
            "sla_monitor",
            {"email_sent_status": "sent" if email_ok else "failed", "error": email_error}
        )
        db.add_workflow_run_step(
            workflow_run_id=run["workflow_run_id"],
            step_name="notify_current_approver",
            step_status="completed" if email_ok else "failed",
            output_payload={"to": to_email, "email_sent_status": "sent" if email_ok else "failed"},
            error_message=email_error if not email_ok else None,
        )
        return {"approval": approval, "overdue": True, "action": "reminder_sent" if email_ok else "reminder_failed"}

    # If current approver is not ACTIVE, directly delegate.
    if not approver_is_active:
        db.log_enterprise_audit(
            "approval", approval_id, "APPROVER_INACTIVE",
            "Current approver is not ACTIVE. Delegating immediately.",
            "sla_monitor",
            {"current_approver": approval.get("current_approver"), "approver_status": approver.get("status") if approver else "not_found"}
        )
        db.add_workflow_run_step(
            workflow_run_id=run["workflow_run_id"],
            step_name="approver_inactive",
            step_status="completed",
            output_payload={"current_approver": approval.get("current_approver")},
        )
        delegate = db.find_delegate_for_approver(approval.get("current_approver"))
        if delegate:
            approval = db.update_approval(
                approval_id,
                {
                    "current_approver": delegate["name"],
                    "delegate_approver": delegate["name"],
                    "status": "rerouted",
                    "reroute_reason": "Current approver inactive/unavailable; delegated immediately.",
                },
            )
            # Notify delegate about takeover.
            email_ok = False
            email_error = None
            delegate_email = delegate.get("email")
            if delegate_email:
                try:
                    send_result = json.loads(send_email_tool(
                        to=delegate_email,
                        subject=f"[SLA TAKEOVER] {approval.get('request_type')}",
                        body=(
                            f"You have been assigned as delegate approver for '{approval.get('request_type')}'.\n"
                            f"Reason: previous approver inactive/unavailable.\n"
                            f"Approval ID: {approval_id}\n"
                            f"SLA Deadline: {approval.get('sla_deadline')}"
                        ),
                        workflow_id="",
                    ))
                    email_ok = bool(send_result.get("success"))
                    email_error = send_result.get("error")
                except Exception as e:
                    email_error = str(e)

            approval = db.update_approval(
                approval_id,
                {"email_sent_status": "sent" if email_ok else "failed"},
            )
            db.log_enterprise_audit(
                "approval", approval_id, "APPROVAL_REROUTED",
                f"Approval rerouted to delegate {delegate['name']}.",
                "sla_monitor",
                {
                    "delegate_email": delegate.get("email"),
                    "delegate_id": delegate.get("id"),
                    "notification_status": "sent" if email_ok else "failed",
                    "notification_error": email_error,
                }
            )
            db.add_workflow_run_step(
                workflow_run_id=run["workflow_run_id"],
                step_name="delegate_rerouted_and_notified",
                step_status="completed" if email_ok else "failed",
                output_payload={
                    "delegate": delegate.get("name"),
                    "notification_status": "sent" if email_ok else "failed",
                },
                error_message=email_error if not email_ok else None,
            )
            return {"approval": approval, "overdue": True, "action": "rerouted", "delegate": delegate}

    # Reminder already sent and still breached -> reroute using hierarchy
    delegate = db.find_delegate_for_approver(approval.get("current_approver"))
    if delegate:
        approval = db.update_approval(
            approval_id,
            {
                "delegate_approver": delegate["name"],
                "status": "rerouted",
                "reroute_reason": "Current approver unresponsive/overdue; rerouted via manager hierarchy.",
            },
        )
        db.log_enterprise_audit(
            "approval", approval_id, "APPROVAL_REROUTED",
            f"Approval rerouted to delegate {delegate['name']}.",
            "sla_monitor",
            {"delegate_email": delegate.get("email"), "delegate_id": delegate.get("id")}
        )
        db.add_workflow_run_step(
            workflow_run_id=run["workflow_run_id"],
            step_name="delegate_rerouted",
            step_status="completed",
            output_payload={"delegate": delegate.get("name")},
        )
        return {"approval": approval, "overdue": True, "action": "rerouted", "delegate": delegate}

    approval = db.update_approval(
        approval_id,
        {
            "status": "escalated",
            "reroute_reason": "No valid delegate found in hierarchy; escalated.",
            "email_sent_status": "escalated",
        },
    )
    db.log_enterprise_audit(
        "approval", approval_id, "APPROVAL_ESCALATED",
        "Could not determine delegate from hierarchy; escalated instead of guessing.",
        "sla_monitor",
        {"current_approver": approval.get("current_approver")}
    )
    db.add_workflow_run_step(
        workflow_run_id=run["workflow_run_id"],
        step_name="escalated_no_delegate",
        step_status="escalated",
        output_payload={"status": "escalated"},
    )
    return {"approval": approval, "overdue": True, "action": "escalated"}


@app.post("/api/approvals/{approval_id}/reroute")
async def reroute_approval(approval_id: str, req: RerouteApprovalRequest):
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, "Approval not found")
    updated = db.update_approval(
        approval_id,
        {
            "delegate_approver": req.delegate_approver,
            "status": "rerouted",
            "reroute_reason": req.reroute_reason,
        },
    )
    db.log_enterprise_audit(
        "approval", approval_id, "APPROVAL_REROUTED_MANUAL",
        f"Approval rerouted manually to {req.delegate_approver}.",
        req.actor, {"reason": req.reroute_reason}
    )
    return updated


@app.post("/api/workflow-runs")
async def create_workflow_run(workflow_type: str, input_payload: dict | None = None):
    run = db.create_workflow_run(workflow_type, input_payload)
    db.log_enterprise_audit("workflow_run", run["workflow_run_id"], "WORKFLOW_RUN_CREATED",
                            f"Workflow run created for type {workflow_type}.",
                            "workflow_run_api", {"input_payload": input_payload})
    return run


@app.get("/api/workflow-runs/{workflow_run_id}")
async def get_workflow_run(workflow_run_id: str):
    run = db.get_workflow_run(workflow_run_id)
    if not run:
        raise HTTPException(404, "Workflow run not found")
    steps = db.list_workflow_run_steps(workflow_run_id)
    audits = db.get_enterprise_audits(entity_type="workflow_run", entity_id=workflow_run_id)
    return {"run": run, "steps": steps, "audits": audits}


@app.post("/api/workflow-runs/{workflow_run_id}/steps")
async def mark_workflow_step(workflow_run_id: str, step_name: str, step_status: str,
                             input_payload: dict | None = None, output_payload: dict | None = None,
                             error_message: str | None = None, retry_count: int = 0):
    run = db.get_workflow_run(workflow_run_id)
    if not run:
        raise HTTPException(404, "Workflow run not found")
    step = db.add_workflow_run_step(
        workflow_run_id=workflow_run_id,
        step_name=step_name,
        step_status=step_status,
        input_payload=input_payload,
        output_payload=output_payload,
        error_message=error_message,
        retry_count=retry_count,
    )
    db.update_workflow_run(
        workflow_run_id,
        {
            "current_step": step_name,
            "step_status": step_status,
            "output_payload": output_payload,
            "error_message": error_message,
            "retry_count": retry_count,
            "escalation_status": "escalated" if step_status == "escalated" else run.get("escalation_status", "none"),
        },
    )
    db.log_enterprise_audit(
        "workflow_run", workflow_run_id, "WORKFLOW_STEP_UPDATED",
        f"Workflow step '{step_name}' marked as {step_status}.",
        "workflow_run_api",
        {"error_message": error_message, "retry_count": retry_count}
    )
    return step


@app.get("/api/enterprise-audits")
async def list_enterprise_audits(entity_type: str | None = None, entity_id: str | None = None, limit: int = 300):
    return db.get_enterprise_audits(entity_type=entity_type, entity_id=entity_id, limit=limit)


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
