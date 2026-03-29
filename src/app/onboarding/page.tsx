"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modal from "../components/Modal";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function OnboardingPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [detail, setDetail] = useState<any>(null);
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    email: "",
    role: "",
    department: "",
    onboardingDate: "",
    onboardingTime: "",
    triggerMode: "scheduled" as "immediate" | "scheduled",
  });

  async function loadWorkflows() {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/workflows`);
      const all = await res.json();
      setRows((all || []).filter((w: any) => String(w.type).includes("onboarding")));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadWorkflows(); }, []);

  async function openDetail(wfId: string) {
    try {
      const [wfRes, eventsRes, auditsRes] = await Promise.all([
        fetch(`${API}/api/workflows/${wfId}`),
        fetch(`${API}/api/workflows/${wfId}/events`),
        fetch(`${API}/api/enterprise-audits?entity_type=workflow&entity_id=${wfId}`),
      ]);
      const wf = await wfRes.json();
      const eventsPayload = eventsRes.ok ? await eventsRes.json() : { events: [] };
      const audits = auditsRes.ok ? await auditsRes.json() : [];
      setDetail({ wf, events: eventsPayload.events || [], audits: Array.isArray(audits) ? audits : [] });
    } catch {
      setDetail(null);
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const request = `Onboard ${form.name} as a new ${form.role} in the ${form.department} department. Email: ${form.email}. Onboarding scheduled for ${form.onboardingDate} at ${form.onboardingTime}.`;

      let scheduled_at: string | null = null;
      if (form.triggerMode === "scheduled" && form.onboardingDate && form.onboardingTime) {
        scheduled_at = new Date(`${form.onboardingDate}T${form.onboardingTime}`).toISOString();
      }

      const res = await fetch(`${API}/api/workflows/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request,
          trigger: "employee_onboarding",
          name: form.name,
          email: form.email,
          role: form.role,
          department: form.department,
          scheduled_at,
        }),
      });
      const data = await res.json();
      setShowModal(false);
      setForm({ name: "", email: "", role: "", department: "", onboardingDate: "", onboardingTime: "", triggerMode: "scheduled" });
      await loadWorkflows();

      if (data.status === "SCHEDULED") {
        if (data.workflowId) openDetail(data.workflowId);
      } else {
        router.push(`/workflows/${data.workflowId}`);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const isScheduledPast = (w: any) => {
    if (!w.scheduled_at) return false;
    return new Date() > new Date(w.scheduled_at);
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Onboarding Progress</h1>
          <p>Schedule onboarding workflows or trigger them immediately. The system auto-triggers at the scheduled time.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          + New Onboarding
        </button>
      </div>

      {/* Table */}
      <div className="panel" style={{ overflow: "hidden", marginBottom: 16 }}>
        {loading ? (
          <div className="loading-state"><div className="spinner" /></div>
        ) : rows.length === 0 ? (
          <div className="empty-state">No onboarding workflows yet. Create one to get started.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Workflow</th>
                <th>Employee</th>
                <th>Scheduled</th>
                <th>Status</th>
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((w) => {
                const inputData = typeof w.input_data === "string" ? JSON.parse(w.input_data) : (w.input_data || {});
                return (
                  <tr key={w.id} onClick={() => openDetail(w.id)}>
                    <td className="cell-mono">{String(w.id).slice(0, 8)}</td>
                    <td className="cell-bright">{inputData.name || "—"}</td>
                    <td>
                      {w.scheduled_at ? (
                        <span style={{ color: isScheduledPast(w) && w.status === "SCHEDULED" ? "#ef4444" : "inherit" }}>
                          {new Date(w.scheduled_at).toLocaleString()}
                          {isScheduledPast(w) && w.status === "SCHEDULED" && " ⏰"}
                        </span>
                      ) : "Immediate"}
                    </td>
                    <td>
                      <span className={`badge badge-${w.status.toLowerCase()}`}>{w.status}</span>
                    </td>
                    <td>{new Date(w.updated_at).toLocaleString()}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <Link href={`/workflows/${w.id}`} className="cell-link">
                        View Workflow →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail Panel */}
      {detail && (
        <div className="panel" style={{ padding: "var(--card-padding)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
            <h3 style={{ margin: 0, color: "var(--text-bright)", fontWeight: 700 }}>Workflow Detail</h3>
            <button onClick={() => setDetail(null)} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.2rem" }}>&times;</button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div>
              <section className="detail-section">
                <h4>Workflow Info</h4>
                <p><b>ID:</b> <code style={{ color: "var(--accent)", fontSize: "0.8rem" }}>{detail.wf.id}</code></p>
                <p><b>Type:</b> {detail.wf.type}</p>
                <p><b>Status:</b> <span className={`badge badge-${detail.wf.status.toLowerCase()}`}>{detail.wf.status}</span></p>
                {detail.wf.scheduled_at && <p><b>Scheduled At:</b> {new Date(detail.wf.scheduled_at).toLocaleString()}</p>}
                <p><b>Created:</b> {new Date(detail.wf.created_at).toLocaleString()}</p>
              </section>

              <section className="detail-section">
                <h4>Execution Steps</h4>
                <div style={{ maxHeight: 300, overflowY: "auto" }}>
                  {detail.events.length === 0 ? (
                    <p style={{ color: "var(--text-muted)" }}>
                      {detail.wf.status === "SCHEDULED" ? "Workflow will execute at the scheduled time." : "No execution events yet."}
                    </p>
                  ) : detail.events.filter((e: any) => e.event_type !== "heartbeat").map((e: any, i: number) => (
                    <div key={i} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: "1px dashed var(--border)", display: "flex", gap: 10 }}>
                      <div style={{
                        width: 10, height: 10, borderRadius: "50%", marginTop: 5, flexShrink: 0,
                        background: e.event_type === "step_complete" ? "#10b981" : e.event_type === "step_failed" ? "#ef4444" : "#f59e0b"
                      }} />
                      <div>
                        <div className="cell-bright" style={{ fontSize: "0.85rem" }}>{e.event_type}</div>
                        <div className="cell-mono">{e.agent} — {new Date(e.timestamp).toLocaleString()}</div>
                        {e.data?.name && <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>Step: {e.data.name}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <Link href={`/workflows/${detail.wf.id}`} className="btn-primary"
                style={{ display: "inline-block", textDecoration: "none" }}>
                Open Live Dashboard →
              </Link>
            </div>

            <div>
              <section className="detail-section" style={{ height: "100%" }}>
                <h4>Audit Trail</h4>
                <div style={{ maxHeight: 420, overflowY: "auto" }}>
                  {detail.audits.length === 0 ? (
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
          </div>
        </div>
      )}

      {/* Modal */}
      <Modal isOpen={showModal} onClose={() => setShowModal(false)} title="New Onboarding">
        <form onSubmit={handleCreate} className="form-grid">
          <input required placeholder="Employee Name" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-field" />
          <input required type="email" placeholder="Email Address" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} className="input-field" />
          <div className="form-row-2">
            <input required placeholder="Role (e.g. Software Engineer)" value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })} className="input-field" />
            <input required placeholder="Department (e.g. Engineering)" value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })} className="input-field" />
          </div>
          <div className="form-row-2">
            <div>
              <label className="form-label">Onboarding Date</label>
              <input required type="date" value={form.onboardingDate}
                onChange={(e) => setForm({ ...form, onboardingDate: e.target.value })} className="input-field" />
            </div>
            <div>
              <label className="form-label">Onboarding Time</label>
              <input required type="time" value={form.onboardingTime}
                onChange={(e) => setForm({ ...form, onboardingTime: e.target.value })} className="input-field" />
            </div>
          </div>

          {/* Trigger Mode */}
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <label style={{ color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: "0.85rem" }}>
              <input type="radio" name="triggerMode" value="scheduled" checked={form.triggerMode === "scheduled"}
                onChange={() => setForm({ ...form, triggerMode: "scheduled" })} />
              Schedule for date/time
            </label>
            <label style={{ color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: "0.85rem" }}>
              <input type="radio" name="triggerMode" value="immediate" checked={form.triggerMode === "immediate"}
                onChange={() => setForm({ ...form, triggerMode: "immediate" })} />
              Trigger immediately
            </label>
          </div>

          <div className="form-actions">
            <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={creating}>
              {creating ? "Starting..." : form.triggerMode === "scheduled" ? "Schedule Onboarding" : "Trigger Onboarding Now"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
