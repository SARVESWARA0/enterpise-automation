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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/audits`)
      .then((r) => r.json())
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: 32, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, marginBottom: 8, color: "var(--text-bright)", letterSpacing: "-0.02em" }}>
          📜 Global Audit Trail
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Immutable log of all agent decisions, escalations, and system actions.
        </p>
      </div>

      <div className="panel" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: "center" }}>
            <div className="spinner" style={{ margin: "0 auto" }} />
          </div>
        ) : logs.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center", color: "var(--text-muted)" }}>
            No audit logs found.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "rgba(0,0,0,0.2)" }}>
                <th style={thStyle}>Timestamp</th>
                <th style={thStyle}>Agent</th>
                <th style={thStyle}>Decision</th>
                <th style={thStyle}>Action Taken</th>
                <th style={thStyle}>Reason</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} style={{ borderBottom: "1px solid var(--border)", transition: "background 0.2s" }} className="hover-row">
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                    {new Date(log.timestamp).toLocaleString(undefined, {
                      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit"
                    })}
                  </td>
                  <td style={{ ...tdStyle, fontWeight: 700, color: AGENT_COLORS[log.agent_name] || "var(--text-secondary)" }}>
                    {log.agent_name}
                  </td>
                  <td style={tdStyle}>
                    <span className="badge" style={{ 
                      background: "rgba(255,255,255,0.05)", 
                      color: log.decision === "ESCALATED" ? "var(--warning)" : log.decision === "FAILED" ? "var(--danger)" : "var(--text-bright)" 
                    }}>
                      {log.decision}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, color: "var(--text-primary)" }}>
                    {log.action_taken}
                  </td>
                  <td style={{ ...tdStyle, color: "var(--text-secondary)", fontSize: "0.8rem", maxWidth: 300 }}>
                    {log.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        .hover-row:hover { background: var(--bg-hover) !important; }
      `}} />
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "16px 20px",
  fontSize: "0.7rem",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--text-muted)",
  fontFamily: "var(--font-mono)"
};

const tdStyle: React.CSSProperties = {
  padding: "16px 20px",
  fontSize: "0.85rem",
};
