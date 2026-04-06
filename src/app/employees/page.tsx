"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Modal from "../components/Modal";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Employee {
  id: string;
  employee_id: string | null;
  name: string;
  email: string;
  company_email: string | null;
  role: string;
  department: string;
  buddy: string | null;
  status: string;
  created_at: string;
}

interface EmployeeDocument {
  id: string;
  employee_id: string;
  filename: string;
  original_name: string;
  file_type: string;
  file_size: number;
  document_category: string | null;
  extracted_data: any;
  validation_status: string;
  validation_details: any;
  created_at: string;
}

/* ── Category label & icon mapping ── */
const DOC_CATEGORY: Record<string, { label: string; icon: string }> = {
  aadhaar: { label: "Aadhaar Card", icon: "🪪" },
  pan: { label: "PAN Card", icon: "💳" },
  passport: { label: "Passport", icon: "🛂" },
  driving_license: { label: "Driving License", icon: "🚗" },
  voter_id: { label: "Voter ID", icon: "🗳️" },
  other: { label: "Document", icon: "📄" },
  unknown: { label: "Unknown", icon: "❓" },
};

const VALIDATION_LABELS: Record<string, { label: string; color: string; bg: string; border: string }> = {
  valid:   { label: "VERIFIED",  color: "#34d399", bg: "rgba(16,185,129,0.1)",  border: "rgba(16,185,129,0.25)" },
  partial: { label: "PARTIAL",   color: "#fbbf24", bg: "rgba(245,158,11,0.1)",  border: "rgba(245,158,11,0.25)" },
  invalid: { label: "MISMATCH", color: "#f87171", bg: "rgba(239,68,68,0.1)",   border: "rgba(239,68,68,0.25)" },
  pending: { label: "PENDING",   color: "#94a3b8", bg: "rgba(100,116,139,0.1)", border: "rgba(100,116,139,0.25)" },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ── Main Page ── */
export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmp, setSelectedEmp] = useState<Employee | null>(null);
  const [documents, setDocuments] = useState<EmployeeDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch(`${API}/api/employees`)
      .then((r) => r.json())
      .then(setEmployees)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  /* ── Load documents when employee selected ── */
  const loadDocuments = useCallback(async (empId: string) => {
    setDocsLoading(true);
    try {
      const res = await fetch(`${API}/api/employees/${empId}/documents`);
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch {
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  }, []);

  const openDetail = (emp: Employee) => {
    setSelectedEmp(emp);
    loadDocuments(emp.id);
  };

  /* ── Upload handler ── */
  const handleUpload = async (files: FileList | File[]) => {
    if (!selectedEmp || !files.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const formData = new FormData();
        formData.append("file", file);
        await fetch(`${API}/api/employees/${selectedEmp.id}/documents`, {
          method: "POST",
          body: formData,
        });
      }
      await loadDocuments(selectedEmp.id);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
    }
  };

  /* ── Drag & drop ── */
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files);
  };

  const filteredEmployees = employees.filter(e =>
    !search || e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.email.toLowerCase().includes(search.toLowerCase()) ||
    e.department.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Employee Directory</h1>
          <p>{employees.length} employees registered · Click a name to view details &amp; documents</p>
        </div>
        <div style={{ position: "relative" }}>
          <input
            className="input-field"
            placeholder="Search employees..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 240, paddingLeft: 36 }}
          />
          <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", opacity: 0.4, fontSize: "0.85rem" }}>🔍</span>
        </div>
      </div>

      <div className="panel" style={{ overflow: "auto" }}>
        {loading ? (
          <div className="loading-state"><div className="spinner" /></div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Employee ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Company Email</th>
                <th>Role</th>
                <th>Department</th>
                <th>Buddy</th>
                <th>Status</th>
                <th>Joined</th>
              </tr>
            </thead>
            <tbody>
              {filteredEmployees.map((emp) => (
                <tr key={emp.id} onClick={() => openDetail(emp)}>
                  <td className="cell-accent">{emp.employee_id || "—"}</td>
                  <td>
                    <span className="emp-name-link">{emp.name}</span>
                  </td>
                  <td>{emp.email}</td>
                  <td>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: emp.company_email ? "var(--success)" : "var(--text-muted)" }}>
                      {emp.company_email || "—"}
                    </span>
                  </td>
                  <td>{emp.role}</td>
                  <td>{emp.department}</td>
                  <td>{emp.buddy || "—"}</td>
                  <td>
                    <span className={`badge badge-${emp.status.toLowerCase()}`}>
                      {emp.status}
                    </span>
                  </td>
                  <td className="cell-mono">{new Date(emp.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ════ Employee Detail Modal ════ */}
      <Modal
        isOpen={!!selectedEmp}
        onClose={() => { setSelectedEmp(null); setDocuments([]); }}
        title={selectedEmp ? `${selectedEmp.name} — Documents & Details` : ""}
      >
        {selectedEmp && (
          <div className="emp-detail-layout">
            {/* ── Left: Employee Info ── */}
            <div className="emp-info-panel">
              <div className="emp-avatar-row">
                <div className="emp-avatar-circle">
                  {selectedEmp.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "1.05rem", color: "var(--text-bright)" }}>
                    {selectedEmp.name}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {selectedEmp.role} · {selectedEmp.department}
                  </div>
                </div>
                <span className={`badge badge-${selectedEmp.status.toLowerCase()}`} style={{ marginLeft: "auto" }}>
                  {selectedEmp.status}
                </span>
              </div>

              <div className="emp-info-grid">
                <InfoRow label="Employee ID" value={selectedEmp.employee_id || "—"} accent />
                <InfoRow label="Email" value={selectedEmp.email} />
                <InfoRow label="Company Email" value={selectedEmp.company_email || "—"} />
                <InfoRow label="Department" value={selectedEmp.department} />
                <InfoRow label="Buddy" value={selectedEmp.buddy || "Not assigned"} />
                <InfoRow label="Joined" value={new Date(selectedEmp.created_at).toLocaleDateString()} />
              </div>

              {/* Document count summary */}
              <div className="doc-summary-bar">
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                  📎 {documents.length} document{documents.length !== 1 ? "s" : ""} uploaded
                </span>
                {documents.length > 0 && (
                  <div style={{ display: "flex", gap: 6 }}>
                    {["valid", "partial", "invalid", "pending"].map(s => {
                      const count = documents.filter(d => d.validation_status === s).length;
                      if (!count) return null;
                      const v = VALIDATION_LABELS[s];
                      return (
                        <span key={s} style={{
                          fontSize: "0.65rem", fontWeight: 700, padding: "2px 8px",
                          borderRadius: 9999, background: v.bg, color: v.color, border: `1px solid ${v.border}`,
                          fontFamily: "var(--font-mono)",
                        }}>
                          {count} {v.label}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* ── Right: Upload + Documents ── */}
            <div className="emp-docs-panel">
              {/* Upload Zone */}
              <div
                className={`doc-upload-zone ${dragActive ? "drag-active" : ""} ${uploading ? "uploading" : ""}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.webp"
                  multiple
                  style={{ display: "none" }}
                  onChange={e => { if (e.target.files) handleUpload(e.target.files); e.target.value = ""; }}
                />
                {uploading ? (
                  <>
                    <div className="spinner" />
                    <span>Uploading & extracting...</span>
                  </>
                ) : (
                  <>
                    <div className="upload-icon">
                      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                    </div>
                    <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                      Drop documents here or <span style={{ color: "var(--accent)" }}>browse</span>
                    </span>
                    <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                      Supports: Aadhaar, PAN, Passport — PDF, PNG, JPG
                    </span>
                  </>
                )}
              </div>

              {/* Document List */}
              <div className="doc-list-section">
                {docsLoading ? (
                  <div className="loading-state" style={{ padding: 30 }}><div className="spinner" /></div>
                ) : documents.length === 0 ? (
                  <div className="empty-state" style={{ padding: 30, fontSize: "0.82rem" }}>
                    No documents uploaded yet. Upload an Aadhaar, PAN, or Passport to begin verification.
                  </div>
                ) : (
                  documents.map(doc => <DocumentCard key={doc.id} doc={doc} />)
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

/* ── Info Row component ── */
function InfoRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="emp-info-row">
      <span className="emp-info-label">{label}</span>
      <span className={`emp-info-value ${accent ? "accent" : ""}`}>{value}</span>
    </div>
  );
}

/* ── Document Card ── */
function DocumentCard({ doc }: { doc: EmployeeDocument }) {
  const [expanded, setExpanded] = useState(false);
  const category = DOC_CATEGORY[doc.document_category || "other"] || DOC_CATEGORY.other;
  const validation = VALIDATION_LABELS[doc.validation_status] || VALIDATION_LABELS.pending;
  const extracted = doc.extracted_data;
  const fields = extracted?.fields || {};
  const valDetails = doc.validation_details || {};
  const valFields = valDetails.fields || {};

  return (
    <div className="doc-card" onClick={() => setExpanded(!expanded)}>
      {/* Card Header */}
      <div className="doc-card-header">
        <div className="doc-card-icon">{category.icon}</div>
        <div className="doc-card-info">
          <div className="doc-card-name">{doc.original_name}</div>
          <div className="doc-card-meta">
            {category.label} · {formatFileSize(doc.file_size)} · {new Date(doc.created_at).toLocaleDateString()}
          </div>
        </div>
        <div style={{
          padding: "3px 10px", borderRadius: 9999,
          background: validation.bg, color: validation.color, border: `1px solid ${validation.border}`,
          fontSize: "0.6rem", fontWeight: 700, fontFamily: "var(--font-mono)",
          textTransform: "uppercase", letterSpacing: "0.06em",
        }}>
          {validation.label}
        </div>
        <div className={`doc-card-chevron ${expanded ? "expanded" : ""}`}>▾</div>
      </div>

      {/* Expanded Detail */}
      {expanded && (
        <div className="doc-card-detail" onClick={e => e.stopPropagation()}>
          {/* Validation score bar */}
          {valDetails.score !== undefined && (
            <div className="doc-validation-score">
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 500 }}>
                Validation Score
              </span>
              <div className="progress-bar-bg" style={{ flex: 1, height: 6 }}>
                <div className="progress-bar-fill" style={{
                  width: `${(valDetails.score || 0) * 100}%`,
                  background: valDetails.score >= 0.8 ? "var(--success)" :
                    valDetails.score >= 0.5 ? "var(--warning)" : "var(--danger)",
                }} />
              </div>
              <span style={{
                fontSize: "0.72rem", fontWeight: 700, fontFamily: "var(--font-mono)",
                color: validation.color,
              }}>
                {Math.round((valDetails.score || 0) * 100)}%
              </span>
            </div>
          )}

          {/* Extracted fields with validation */}
          <div className="doc-fields-grid">
            <div className="doc-fields-title">Extracted Data</div>
            {Object.keys(fields).length === 0 ? (
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", padding: "8px 0" }}>
                No text content could be extracted. Try uploading a text-based PDF.
              </div>
            ) : (
              Object.entries(fields).map(([key, value]) => {
                const val = valFields[key];
                const isMatch = val?.match === true;
                const isMismatch = val?.match === false;
                return (
                  <div key={key} className="doc-field-row">
                    <span className="doc-field-key">{key.replace(/_/g, " ")}</span>
                    <span className="doc-field-value">{String(value)}</span>
                    {val && val.match !== null && val.match !== undefined && (
                      <span className={`doc-field-badge ${isMatch ? "match" : "mismatch"}`}>
                        {isMatch ? "✓ Match" : "✗ Mismatch"}
                      </span>
                    )}
                    {isMismatch && val.expected && (
                      <span className="doc-field-expected">
                        Expected: {val.expected}
                      </span>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Download link */}
          <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 8 }}>
            <a
              href={`${API}/api/documents/${doc.id}/file`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary btn-sm"
              style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              ⬇ Download Original
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
