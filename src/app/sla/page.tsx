"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import Modal from "../components/Modal";
import Pagination from "../components/Pagination";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Approval = {
  approval_id: string;
  request_type: string;
  current_approver: string | null;
  delegate_approver: string | null;
  status: string;
  sla_deadline: string;
  last_reminder_sent_at: string | null;
  email_sent_status: string | null;
  reroute_reason: string | null;
};

export default function SlaPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [monitoring, setMonitoring] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const [form, setForm] = useState({
    request_type: "",
    current_approver_name: "",
    current_approver_email: "",
    sla_deadline: "",
    sla_duration_hours: 24,
    priority: "High",
    event_summary: "",
    breach_instructions: "",
    auto_monitor_overdue: true,
  });

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/approvals`);
      const rows = await r.json();
      setApprovals(rows);
      setPage(1);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function openRow(id: string) {
    const r = await fetch(`${API}/api/approvals/${id}`);
    setDetail(await r.json());
  }

  async function monitor(id: string) {
    setMonitoring(id);
    try {
      const r = await fetch(`${API}/api/approvals/${id}/monitor`, { method: "POST" });
      const data = await r.json();
      setMessage(`Monitor: ${data.action || "completed"}`);
      await load();
      await openRow(id);
    } finally {
      setMonitoring(null);
    }
  }

  async function createEvent(e: FormEvent) {
    e.preventDefault();
    if (!form.request_type || !form.sla_deadline) {
      setMessage("Request type and SLA deadline are required.");
      return;
    }
    setCreating(true);
    setMessage("");
    try {
      const [ymd, hm] = form.sla_deadline.split("T");
      const [y, m, d] = ymd.split("-").map(Number);
      const [h, min] = hm.split(":").map(Number);
      const localDate = new Date(y, m - 1, d, h, min);
      const isoDeadline = localDate.toISOString();

      const payload = {
        request_type: form.request_type,
        current_approver: {
          name: form.current_approver_name,
          email: form.current_approver_email
        },
        sla_deadline: isoDeadline,
        sla_duration_hours: form.sla_duration_hours,
        priority: form.priority,
        event_summary: form.event_summary,
        if_breached: form.breach_instructions,
        auto_trigger_monitor: form.auto_monitor_overdue,
        allow_auto_reroute: true,
        reminder_interval_hours: 12,
        grace_period_hours: 12
      };

      const r = await fetch(`${API}/api/approvals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      const approval = data.approval || data;
      setMessage(
        data.auto_monitored
          ? `Event created and auto-monitored: ${data.monitor_result?.action || "done"}`
          : "Event created. Monitor will auto-trigger when deadline passes."
      );
      setForm({ request_type: "", current_approver_name: "", current_approver_email: "", sla_deadline: "", sla_duration_hours: 24, priority: "High", event_summary: "", breach_instructions: "", auto_monitor_overdue: true });
      await load();
      if (approval?.approval_id) await openRow(approval.approval_id);
    } finally {
      setCreating(false);
    }
  }

  const isOverdue = (deadline: string) => new Date() > new Date(deadline);

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <h1>SLA Breach Prevention</h1>
          <p>Track approvals, reminders, reroutes, and escalations with full auditability.</p>
        </div>
      </div>

      {/* Create Form */}
      <div className="panel" style={{ padding: "var(--card-padding)", marginBottom: 16 }}>
        <h3 style={{ marginTop: 0, color: "var(--text-bright)", fontSize: "1rem", fontWeight: 700, marginBottom: 14 }}>Add SLA Event</h3>
        <form onSubmit={createEvent} className="form-grid">
          <div className="form-row-3">
            <input placeholder="Event / request type*" required value={form.request_type}
              onChange={(e) => setForm((p) => ({ ...p, request_type: e.target.value }))} className="input-field" />
            <input placeholder="Current approver name" value={form.current_approver_name}
              onChange={(e) => setForm((p) => ({ ...p, current_approver_name: e.target.value }))} className="input-field" />
            <input placeholder="Current approver email" value={form.current_approver_email}
              onChange={(e) => setForm((p) => ({ ...p, current_approver_email: e.target.value }))} className="input-field" />
          </div>
          <div className="form-row-3">
            <div>
              <label className="form-label">SLA Deadline*</label>
              <input type="datetime-local" required value={form.sla_deadline}
                onChange={(e) => setForm((p) => ({ ...p, sla_deadline: e.target.value }))} className="input-field" />
            </div>
            <div>
              <label className="form-label">Duration (hours)</label>
              <input type="number" value={form.sla_duration_hours}
                onChange={(e) => setForm((p) => ({ ...p, sla_duration_hours: Number(e.target.value) }))} className="input-field" />
            </div>
            <div>
              <label className="form-label">Priority</label>
              <select value={form.priority} onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))} className="input-field">
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </div>
          </div>
          <div>
            <label className="form-label">Event summary</label>
            <input placeholder="Short context summary..." value={form.event_summary}
              onChange={(e) => setForm((p) => ({ ...p, event_summary: e.target.value }))} className="input-field" />
          </div>
          <div>
            <label className="form-label">If Breached — Custom Instructions for AI Agent (optional)</label>
            <textarea
              placeholder={"Describe what the agent should do if this SLA is breached...\nExample: 'Notify the engineering lead and schedule an emergency review.'"}
              value={form.breach_instructions}
              onChange={(e) => setForm((p) => ({ ...p, breach_instructions: e.target.value }))}
              className="input-field"
              style={{ height: 96, resize: "vertical", fontFamily: "inherit" }}
            />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <label style={{ color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 8, fontSize: "0.85rem" }}>
              <input type="checkbox" checked={form.auto_monitor_overdue}
                onChange={(e) => setForm((p) => ({ ...p, auto_monitor_overdue: e.target.checked }))} />
              Auto-trigger monitor if already overdue
            </label>
            <button className="btn-primary" type="submit" disabled={creating}>
              {creating ? "Creating..." : "Create SLA Event"}
            </button>
          </div>
        </form>
        {message ? <div className="status-msg">{message}</div> : null}
      </div>

      {/* Approvals Table */}
      <div className="panel" style={{ overflow: "hidden", marginBottom: 16 }}>
        {loading ? (
          <div className="loading-state"><div className="spinner" /></div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Approval</th>
                <th>Current Approver</th>
                <th>SLA Deadline</th>
                <th>Status</th>
                <th>Reminder</th>
                <th>Delegate</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {approvals.slice((page - 1) * pageSize, page * pageSize).map((a) => (
                <tr key={a.approval_id} onClick={() => openRow(a.approval_id)}>
                  <td className="cell-bright">{a.request_type}</td>
                  <td>{a.current_approver || "—"}</td>
                  <td>
                    <span style={{ color: isOverdue(a.sla_deadline) ? "#ef4444" : "var(--text-secondary)" }}>
                      {new Date(a.sla_deadline).toLocaleString()}
                      {isOverdue(a.sla_deadline) && " ⚠️"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge badge-${a.status}`}>{a.status}</span>
                  </td>
                  <td>{a.email_sent_status || "pending"}</td>
                  <td>{a.delegate_approver || "—"}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn-secondary btn-sm" onClick={() => openRow(a.approval_id)}>View</button>
                      <button className="btn-secondary btn-sm" onClick={() => monitor(a.approval_id)} disabled={monitoring === a.approval_id}>
                        {monitoring === a.approval_id ? "Running..." : "Monitor"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && <Pagination currentPage={page} pageSize={pageSize} totalItems={approvals.length} onPageChange={setPage} />}
      </div>

      {/* Detail Modal */}
      <Modal isOpen={!!detail} onClose={() => setDetail(null)} title={`Approval: ${detail?.approval?.request_type || ''}`}>
        {detail && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div>
              <section className="detail-section">
                <h4>Approval Info</h4>
                <p><b>Type:</b> {detail.approval.request_type}</p>
                <p><b>Current Approver:</b> {detail.approval.current_approver || "—"}</p>
                <p><b>Delegate:</b> {detail.approval.delegate_approver || "—"}</p>
                <p><b>Status:</b> <span className={`badge badge-${detail.approval.status}`}>{detail.approval.status}</span></p>
                <p><b>SLA Deadline:</b> <span style={{ color: isOverdue(detail.approval.sla_deadline) ? "#ef4444" : "inherit" }}>
                  {new Date(detail.approval.sla_deadline).toLocaleString()}</span></p>
                <p><b>Reroute Reason:</b> {detail.approval.reroute_reason || "—"}</p>
                <p><b>Reminder:</b> {detail.approval.last_reminder_sent_at ? new Date(detail.approval.last_reminder_sent_at).toLocaleString() : "Not sent yet"}</p>
              </section>

              <section className="detail-section">
                <h4>Audit Trail</h4>
                <div style={{ maxHeight: 280, overflowY: "auto" }}>
                  {!detail.audits?.length ? (
                    <p style={{ color: "var(--text-muted)" }}>No audit entries yet.</p>
                  ) : detail.audits.map((a: any) => (
                    <div key={a.log_id} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: "1px dashed var(--border)" }}>
                      <div className="cell-mono" style={{ marginBottom: 2 }}>{new Date(a.timestamp).toLocaleString()}</div>
                      <div className="cell-bright" style={{ fontSize: "0.85rem" }}>{a.event_type}</div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>{a.message}</div>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <div>
              <section className="detail-section">
                <h4>Workflow Execution</h4>
                {!detail.workflow_run ? (
                  <p style={{ color: "var(--text-muted)" }}>No workflow run linked yet. Run Monitor to trigger.</p>
                ) : (
                  <>
                    <p><b>Run ID:</b> <code style={{ color: "var(--accent)", fontSize: "0.8rem" }}>{detail.workflow_run.run.workflow_run_id.slice(0, 16)}...</code></p>
                    <p><b>Current Step:</b> {detail.workflow_run.run.current_step || "—"}</p>
                    <p><b>Step Status:</b> <span className={`badge badge-${detail.workflow_run.run.step_status}`}>{detail.workflow_run.run.step_status || "—"}</span></p>

                    <div style={{ marginTop: 12 }}>
                      {(detail.workflow_run.steps || []).map((s: any) => (
                        <div key={s.id} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: "1px dashed var(--border)", display: "flex", gap: 10 }}>
                          <div style={{ width: 10, height: 10, borderRadius: "50%", marginTop: 5, flexShrink: 0,
                            background: s.step_status === "completed" ? "#10b981" : s.step_status === "failed" ? "#ef4444" : "#f59e0b" }} />
                          <div>
                            <div className="cell-bright" style={{ fontSize: "0.85rem" }}>{s.step_name}</div>
                            <div className="cell-mono">{new Date(s.created_at).toLocaleString()} — {s.step_status}</div>
                            {s.error_message && <div style={{ color: "#ef4444", fontSize: "0.8rem", marginTop: 2 }}>{s.error_message}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </section>

              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn-primary" onClick={() => monitor(detail.approval.approval_id)} disabled={monitoring === detail.approval.approval_id}>
                  {monitoring === detail.approval.approval_id ? "Running..." : "Run Monitor Now"}
                </button>
                {detail.workflow_run?.run?.workflow_run_id && (
                  <Link href={`/workflows/${detail.workflow_run.run.workflow_run_id}`}
                    className="btn-secondary" style={{ textDecoration: "none" }}>
                    View Full Workflow →
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
