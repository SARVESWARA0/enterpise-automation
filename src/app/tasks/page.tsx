"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modal from "../components/Modal";
import Pagination from "../components/Pagination";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type TaskRow = {
  task_id: string;
  title: string;
  owner: string | null;
  status: string;
  due_date: string | null;
  priority: string;
};

type TaskDetail = {
  task: any;
  action_items: any[];
  audits: any[];
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [selected, setSelected] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [ownerInput, setOwnerInput] = useState("");
  const [showTranscriptModal, setShowTranscriptModal] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [transcriptTitle, setTranscriptTitle] = useState("");
  const [transcriptDate, setTranscriptDate] = useState("");
  const [transcriptParticipants, setTranscriptParticipants] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const router = useRouter();

  async function loadTasks() {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/tasks`);
      setTasks(await res.json());
      setPage(1);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTasks();
  }, []);

  async function openDetail(taskId: string) {
    const res = await fetch(`${API}/api/tasks/${taskId}`);
    const detail = await res.json();
    setSelected(detail);
    setOwnerInput(detail?.task?.owner ?? "");
  }

  async function assignOwner() {
    if (!selected?.task?.task_id || !ownerInput.trim()) return;
    setAssigning(true);
    try {
      await fetch(`${API}/api/tasks/${selected.task.task_id}/assign-owner`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner: ownerInput.trim(), note: "Resolved from UI" }),
      });
      await openDetail(selected.task.task_id);
      await loadTasks();
    } finally {
      setAssigning(false);
    }
  }

  async function handleTranscriptSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!transcript.trim()) return;
    setTriggering(true);
    setTriggerMsg("");
    try {
      const participants = transcriptParticipants.split(",").map((s) => s.trim()).filter(Boolean);
      const request = [
        transcriptTitle ? `Meeting Title: ${transcriptTitle}` : "",
        transcriptDate ? `Date: ${transcriptDate}` : "",
        participants.length ? `Participants: ${participants.join(", ")}` : "",
        `Transcript: ${transcript}`,
      ].filter(Boolean).join("\n");

      const res = await fetch(`${API}/api/workflows/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request,
          trigger: "meeting_action_items",
        }),
      });
      const data = await res.json();
      setShowTranscriptModal(false);
      setTranscript("");
      setTranscriptTitle("");
      setTranscriptDate("");
      setTranscriptParticipants("");
      router.push(`/workflows/${data.workflowId}`);
    } catch {
      setTriggerMsg("Failed to trigger workflow.");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Project Tracker</h1>
          <p>Tasks extracted and managed by autonomous workflows. Click a row for full details.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowTranscriptModal(true)}>
          + Process Meeting Transcript
        </button>
      </div>

      <div className="panel" style={{ overflow: "hidden" }}>
        {loading ? (
          <div className="loading-state"><div className="spinner" /></div>
        ) : tasks.length === 0 ? (
          <div className="empty-state">No tasks yet. Process a meeting transcript to get started.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Title</th>
                <th>Owner</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Due Date</th>
              </tr>
            </thead>
            <tbody>
              {tasks.slice((page - 1) * pageSize, page * pageSize).map((t) => (
                <tr key={t.task_id} onClick={() => openDetail(t.task_id)}>
                  <td className="cell-mono">{String(t.task_id).slice(0, 8)}</td>
                  <td className="cell-bright">{t.title}</td>
                  <td>{t.owner || <span style={{ color: "var(--text-muted)" }}>Unassigned</span>}</td>
                  <td>
                    <span className={`badge badge-${t.status.toLowerCase().replace(" ", "_")}`}>{t.status}</span>
                  </td>
                  <td>{t.priority || "—"}</td>
                  <td>{t.due_date ? new Date(t.due_date).toLocaleDateString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && <Pagination currentPage={page} pageSize={pageSize} totalItems={tasks.length} onPageChange={setPage} />}
      </div>

      <Modal isOpen={!!selected} onClose={() => setSelected(null)} title="Task Details">
        {selected && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div>
              <section className="detail-section">
                <h4>Basic Info</h4>
                <p><b>Title:</b> {selected.task.title}</p>
                <p><b>Description:</b> {selected.task.description || "—"}</p>
                <p><b>Owner:</b> {selected.task.owner || <span style={{ color: "#f59e0b" }}>Unassigned</span>}</p>
                <p><b>Status:</b> <span className={`badge badge-${selected.task.status}`}>{selected.task.status}</span></p>
                <p><b>Priority:</b> {selected.task.priority || "—"}</p>
                <p><b>Due Date:</b> {selected.task.due_date ? new Date(selected.task.due_date).toLocaleString() : "—"}</p>
              </section>
              <section className="detail-section">
                <h4>Agent Insight</h4>
                <p><b>Reason:</b> {selected.task.reason_for_creation || "—"}</p>
                <p><b>Confidence:</b> {selected.task.confidence_score ?? "—"}</p>
              </section>
              {selected.action_items.length > 0 && (
                <section className="detail-section">
                  <h4>Ambiguity Details</h4>
                  {selected.action_items.map((a) => (
                    <div key={a.action_item_id} style={{ padding: 10, border: "1px solid var(--border)", borderRadius: 8, marginBottom: 8 }}>
                      <p><b>Raw:</b> {a.raw_text}</p>
                      <p><b>Owner Detected:</b> {a.owner_detected || "None"}</p>
                      <p><b>Ambiguous:</b> {a.ambiguity_flag ? "Yes ⚠️" : "No"}</p>
                      <p><b>Reason:</b> {a.ambiguity_reason || "—"}</p>
                      <p><b>Possible Owners:</b> {Array.isArray(a.possible_owners) ? a.possible_owners.join(", ") : "—"}</p>
                    </div>
                  ))}
                </section>
              )}
              <section className="detail-section">
                <h4>Resolve Ambiguity</h4>
                <div style={{ display: "flex", gap: 10 }}>
                  <input value={ownerInput} onChange={(e) => setOwnerInput(e.target.value)}
                    placeholder="Assign owner name" className="input-field" style={{ maxWidth: 280 }} />
                  <button className="btn-primary" onClick={assignOwner} disabled={assigning || !ownerInput.trim()}>
                    {assigning ? "Assigning..." : "Resolve"}
                  </button>
                </div>
              </section>
            </div>

            <div>
              <section className="detail-section" style={{ height: "100%" }}>
                <h4>Audit Trail</h4>
                <div style={{ maxHeight: 420, overflowY: "auto" }}>
                  {selected.audits.length === 0 ? (
                    <p style={{ color: "var(--text-muted)" }}>No audit entries yet.</p>
                  ) : selected.audits.map((a) => (
                    <div key={a.log_id} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: "1px dashed var(--border)" }}>
                      <div className="cell-mono" style={{ marginBottom: 2 }}>{new Date(a.timestamp).toLocaleString()}</div>
                      <div className="cell-bright" style={{ fontSize: "0.85rem" }}>{a.event_type}</div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>{a.message}</div>
                    </div>
                  ))}
                </div>
                {selected.task.workflow_id && (
                  <div style={{ marginTop: 12 }}>
                    <Link href={`/workflows/${selected.task.workflow_id}`} className="btn-secondary btn-sm"
                      style={{ display: "inline-block", textDecoration: "none" }}>
                      View Full Workflow →
                    </Link>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}
      </Modal>

      <Modal isOpen={showTranscriptModal} onClose={() => setShowTranscriptModal(false)} title="Process Meeting Transcript">
        <form onSubmit={handleTranscriptSubmit} className="form-grid">
          <div className="form-row-2">
            <input placeholder="Meeting Title (optional)" value={transcriptTitle} onChange={(e) => setTranscriptTitle(e.target.value)} className="input-field" />
            <input type="date" value={transcriptDate} onChange={(e) => setTranscriptDate(e.target.value)} className="input-field" />
          </div>
          <input placeholder="Participants (comma-separated, e.g. Alice, Bob, Carol)" value={transcriptParticipants} onChange={(e) => setTranscriptParticipants(e.target.value)} className="input-field" />
          <textarea
            required
            placeholder={"Paste the full meeting transcript here...\n\nExample:\nAlice: We need to migrate the API to v2 by Friday.\nBob: I'll handle the backend changes.\nCarol: I'll update the docs and staging environment."}
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            className="input-field"
            style={{ height: 240, resize: "vertical", fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}
          />
          {triggerMsg && <div style={{ color: "#ef4444", fontSize: "0.85rem" }}>{triggerMsg}</div>}
          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={() => setShowTranscriptModal(false)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={triggering || !transcript.trim()}>
              {triggering ? "Processing..." : "Extract Action Items →"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
