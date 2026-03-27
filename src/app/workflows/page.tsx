"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Workflow {
  id: string;
  type: string;
  trigger_event: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/workflows`)
      .then((r) => r.json())
      .then(setWorkflows)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: 32, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, marginBottom: 8, color: "var(--text-bright)", letterSpacing: "-0.02em" }}>
            Workflows
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Monitor and trace all execution plans and autonomous behaviors.
          </p>
        </div>
        <Link href="/" style={{ padding: "10px 20px", background: "var(--accent)", color: "white", borderRadius: "100px", textDecoration: "none", fontSize: "0.85rem", fontWeight: 600 }}>
          + New Workflow
        </Link>
      </div>

      <div className="panel" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: "center" }}>
            <div className="spinner" style={{ margin: "0 auto" }} />
          </div>
        ) : workflows.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center", color: "var(--text-muted)" }}>
            No workflows have been started yet.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "rgba(0,0,0,0.2)" }}>
                <th style={thStyle}>ID</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Started</th>
                <th style={thStyle}>Action</th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((wf) => (
                <tr key={wf.id} style={{ borderBottom: "1px solid var(--border)", transition: "background 0.2s" }} className="hover-row">
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {wf.id.split("-")[0]}
                  </td>
                  <td style={{ ...tdStyle, fontWeight: 500, color: "var(--text-bright)" }}>
                    {wf.type}
                  </td>
                  <td style={tdStyle}>
                    <span className={`badge badge-${wf.status.toLowerCase()}`}>
                      {wf.status === "RUNNING" && <span className="pulse-dot" style={{ background: "currentColor", marginRight: 4 }} />}
                      {wf.status}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, color: "var(--text-secondary)", fontSize: "0.8rem" }}>
                    {new Date(wf.created_at).toLocaleString()}
                  </td>
                  <td style={tdStyle}>
                    <Link href={`/workflows/${wf.id}`} style={{ color: "var(--accent)", textDecoration: "none", fontSize: "0.85rem", fontWeight: 600 }}>
                      View Workflow →
                    </Link>
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
  fontSize: "0.9rem",
};
