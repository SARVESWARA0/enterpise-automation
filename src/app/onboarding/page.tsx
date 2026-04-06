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

  const [docs, setDocs] = useState<File[]>([]);

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
      const formData = new FormData();
      formData.append("name", form.name);
      formData.append("email", form.email);
      formData.append("role", form.role);
      formData.append("department", form.department);
      if (form.onboardingDate) formData.append("onboarding_date", form.onboardingDate);
      if (form.onboardingTime) formData.append("onboarding_time", form.onboardingTime);
      formData.append("trigger_mode", form.triggerMode);

      docs.forEach(doc => {
        formData.append("files", doc);
      });

      const res = await fetch(`${API}/api/onboarding/start-with-docs`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setShowModal(false);
      setForm({ name: "", email: "", role: "", department: "", onboardingDate: "", onboardingTime: "", triggerMode: "scheduled" });
      setDocs([]);
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
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 16 }}>
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

          <div style={{ marginBottom: "16px" }}>
             <label className="form-label">Identity Documents (Optional)</label>
             <div 
               className="doc-upload-zone"
               onClick={() => document.getElementById('onboarding-doc-upload')?.click()}
               onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-active'); }}
               onDragLeave={(e) => { e.currentTarget.classList.remove('drag-active'); }}
               onDrop={(e) => {
                 e.preventDefault();
                 e.currentTarget.classList.remove('drag-active');
                 if (e.dataTransfer.files) {
                   setDocs([...docs, ...Array.from(e.dataTransfer.files)]);
                 }
               }}
               style={{ minHeight: "80px", padding: "16px" }}
             >
               <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
                 <svg className="upload-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                   <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                   <polyline points="17 8 12 3 7 8"></polyline>
                   <line x1="12" y1="3" x2="12" y2="15"></line>
                 </svg>
                 <span style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-primary)" }}>Drop documents here or click to browse</span>
                 <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Supports Aadhaar, PAN, Passport (PDF, PNG, JPG)</span>
               </div>
             </div>
             
             <input 
               id="onboarding-doc-upload"
               type="file" 
               multiple 
               style={{ display: 'none' }}
               onChange={(e) => {
                 if (e.target.files) {
                   setDocs([...docs, ...Array.from(e.target.files)]);
                 }
               }}
             />
             
             {docs.length > 0 && (
               <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "6px" }}>
                 {docs.map((d, i) => (
                   <div key={i} style={{ 
                     fontSize: "0.80rem", background: "var(--bg-surface)", padding: "8px 12px", 
                     borderRadius: "var(--radius-sm)", border: "1px solid var(--border)",
                     display: "flex", justifyContent: "space-between", alignItems: "center"
                   }}>
                     <span style={{ color: "var(--text-bright)", display: "flex", alignItems: "center", gap: "8px" }}>
                       <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                         <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                         <polyline points="14 2 14 8 20 8"></polyline>
                       </svg>
                       {d.name}
                     </span>
                     <button type="button" style={{ 
                       background: "transparent", border: "none", color: "var(--text-muted)", 
                       cursor: "pointer", display: "flex", alignItems: "center"
                     }} onClick={() => setDocs(docs.filter((_, index) => index !== i))}>
                       &times;
                     </button>
                   </div>
                 ))}
               </div>
             )}
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
