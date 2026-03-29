"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuditLog {
  id: string;
  workflow_id: string;
  step_id: string | null;
  agent_name: string;
  decision: string;
  reason: string;
  action_taken: string;
  tool_name: string | null;
  status: string | null;
  timestamp: string;
}

const AGENT_COLORS: Record<string, string> = {
  interpreter: "var(--interpreter)",
  execution: "var(--execution)",
  verification: "var(--verification)",
  recovery: "var(--recovery)",
  orchestrator: "var(--orchestrator)",
  system: "var(--text-muted)",
};

export default function AuditsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [enterpriseLogs, setEnterpriseLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [activeTab, setActiveTab] = useState<"agent" | "enterprise">("agent");
  const [page, setPage] = useState(1);
  const itemsPerPage = 15;

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/audits`).then((r) => r.json()).catch(() => []),
      fetch(`${API}/api/enterprise-audits?limit=400`).then((r) => r.json()).catch(() => []),
    ]).then(([core, enterprise]) => {
      setLogs(core || []);
      setEnterpriseLogs(enterprise || []);
    }).finally(() => setLoading(false));
  }, []);

  const activeItems = activeTab === "agent" ? logs : enterpriseLogs;
  const totalPages = Math.ceil(activeItems.length / itemsPerPage) || 1;
  const currentItems = activeItems.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Global Audit Trail</h1>
          <p>Immutable log of all agent decisions, escalations, and system actions.</p>
        </div>
        <div className="page-header-right" style={{ display: "flex", gap: "8px" }}>
          <button 
            className={`btn-secondary${activeTab === "agent" ? " active" : ""}`}
            style={activeTab === "agent" ? { background: "var(--accent)", color: "white", borderColor: "var(--accent)" } : {}}
            onClick={() => { setActiveTab("agent"); setPage(1); }}
          >
            Agent Workflows
          </button>
          <button 
            className={`btn-secondary${activeTab === "enterprise" ? " active" : ""}`}
            style={activeTab === "enterprise" ? { background: "var(--accent)", color: "white", borderColor: "var(--accent)" } : {}}
            onClick={() => { setActiveTab("enterprise"); setPage(1); }}
          >
            Enterprise Events
          </button>
        </div>
      </div>

      <div className="panel" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {loading ? (
          <div className="loading-state"><div className="spinner" /></div>
        ) : activeItems.length === 0 ? (
          <div className="empty-state">No audit logs found for this category.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", minHeight: "500px", justifyContent: "space-between" }}>
            <table className="data-table">
              {activeTab === "agent" ? (
                <>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Agent</th>
                      <th>Decision</th>
                      <th>Action Taken</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentItems.map((log: any) => (
                      <tr key={log.id} style={{ cursor: "default" }}>
                        <td className="cell-mono" style={{ whiteSpace: "nowrap" }}>
                          {new Date(log.timestamp).toLocaleString(undefined, {
                            month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit"
                          })}
                        </td>
                        <td style={{ fontWeight: 700, color: AGENT_COLORS[log.agent_name] || "var(--text-secondary)" }}>
                          {log.agent_name}
                        </td>
                        <td>
                          <span className={`badge badge-${log.decision === "ESCALATED" ? "escalated" : log.decision === "FAILED" ? "failed" : "completed"}`}>
                            {log.decision}
                          </span>
                        </td>
                        <td style={{ color: "var(--text-primary)" }}>{log.action_taken}</td>
                        <td style={{ color: "var(--text-secondary)", fontSize: "0.8rem", maxWidth: 300 }}>{log.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </>
              ) : (
                <>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Entity</th>
                      <th>Event</th>
                      <th>Actor</th>
                      <th>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentItems.map((log: any) => (
                      <tr key={log.log_id} style={{ cursor: "default" }}>
                        <td className="cell-mono">{new Date(log.timestamp).toLocaleString()}</td>
                        <td>{log.entity_type}:{String(log.entity_id).slice(0, 8)}</td>
                        <td><span className="badge">{log.event_type}</span></td>
                        <td>{log.actor}</td>
                        <td style={{ color: "var(--text-secondary)" }}>{log.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
            </table>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 20px", borderTop: "1px solid var(--border)", marginTop: "auto" }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Showing {(page - 1) * itemsPerPage + 1} to {Math.min(page * itemsPerPage, activeItems.length)} of {activeItems.length} entries
              </span>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  className="btn-secondary"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Prev
                </button>
                <button
                  className="btn-secondary"
                  disabled={page === totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
