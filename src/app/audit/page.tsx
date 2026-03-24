'use client';

import { useEffect, useState } from 'react';

interface AuditLog {
  id: string;
  workflowId: string;
  stepId: string;
  decision: string;
  reason: string;
  actionTaken: string;
  agentName: string;
  toolName: string;
  retryCount: number;
  status: string;
  timestamp: string;
  workflow?: { type: string; status: string };
  step?: { stepName: string; stepType: string };
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ agentName: '', status: '' });

  const fetchLogs = () => {
    const params = new URLSearchParams();
    if (filters.agentName) params.set('agentName', filters.agentName);
    if (filters.status) params.set('status', filters.status);
    fetch(`/api/audit?${params}`).then(r => r.json()).then(d => { setLogs(d); setLoading(false); });
  };

  useEffect(() => { fetchLogs(); const i = setInterval(fetchLogs, 5000); return () => clearInterval(i); }, [filters.agentName, filters.status]);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Audit Trail</h1>
        <p className="page-subtitle">Complete decision log — every action, tool call, retry, and escalation recorded</p>
      </div>

      {/* Filters */}
      <div className="glass-card" style={{ padding: '16px', marginBottom: '16px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <select className="input" style={{ width: 'auto', minWidth: '180px' }} value={filters.agentName}
          onChange={(e) => setFilters({ ...filters, agentName: e.target.value })}>
          <option value="">All Agents</option>
          <option value="ExecutionAgent">Execution Agent</option>
          <option value="DecisionAgent">Decision Agent</option>
          <option value="VerificationAgent">Verification Agent</option>
          <option value="RecoveryAgent">Recovery Agent</option>
        </select>
        <select className="input" style={{ width: 'auto', minWidth: '180px' }} value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          <option value="">All Status</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="escalated">Escalated</option>
          <option value="retrying">Retrying</option>
          <option value="awaiting_clarification">Awaiting Clarification</option>
          <option value="warning">Warning</option>
        </select>
        <div style={{ flex: 1, textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-muted)', alignSelf: 'center' }}>
          {logs.length} entries
        </div>
      </div>

      <div className="glass-card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto' }} /></div>
        ) : logs.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>No audit logs yet. Run a workflow to generate audit entries.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Workflow</th>
                <th>Step</th>
                <th>Agent</th>
                <th>Decision</th>
                <th>Status</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>{new Date(log.timestamp).toLocaleString()}</td>
                  <td style={{ fontSize: '0.75rem' }}>{log.workflow?.type?.replace(/_/g, ' ') || log.workflowId.slice(0, 8)}</td>
                  <td style={{ fontSize: '0.75rem' }}>{log.step?.stepName || '—'}</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--accent)' }}>{log.agentName || '—'}</td>
                  <td style={{ fontWeight: 600, fontSize: '0.8rem' }}>{log.decision}</td>
                  <td><span className={`badge badge-${(log.status || 'pending').toLowerCase()}`}>{log.status || '—'}</span></td>
                  <td style={{ fontSize: '0.75rem', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{log.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
