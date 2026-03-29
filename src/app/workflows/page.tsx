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
    <div className="page-container">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Workflows</h1>
          <p>Monitor and trace all execution plans and autonomous behaviors.</p>
        </div>
        <Link href="/" className="btn-primary" style={{ textDecoration: "none" }}>
          + New Workflow
        </Link>
      </div>

      <div className="panel" style={{ overflow: "hidden" }}>
        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
          </div>
        ) : workflows.length === 0 ? (
          <div className="empty-state">No workflows have been started yet.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Status</th>
                <th>Started</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((wf) => (
                <tr key={wf.id}>
                  <td className="cell-mono">{wf.id.split("-")[0]}</td>
                  <td className="cell-bright">{wf.type}</td>
                  <td>
                    <span className={`badge badge-${wf.status.toLowerCase()}`}>
                      {wf.status === "RUNNING" && <span className="pulse-dot" style={{ background: "currentColor", marginRight: 4 }} />}
                      {wf.status}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>
                    {new Date(wf.created_at).toLocaleString()}
                  </td>
                  <td>
                    <Link href={`/workflows/${wf.id}`} className="cell-link">
                      View Details →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
