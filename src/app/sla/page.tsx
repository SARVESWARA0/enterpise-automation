'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface SlaWorkflow {
  id: string;
  type: string;
  status: string;
  createdAt: string;
  employee?: { name: string };
  steps: Array<{ id: string; stepName: string; status: string; assignedAgent: string; updatedAt: string }>;
  sla: { completedSteps: number; failedSteps: number; totalSteps: number; progress: number; hoursElapsed: number; riskLevel: string };
}

export default function SlaPage() {
  const [workflows, setWorkflows] = useState<SlaWorkflow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSla = () => fetch('/api/sla').then(r => r.json()).then(d => { setWorkflows(d); setLoading(false); });
    fetchSla();
    const i = setInterval(fetchSla, 5000);
    return () => clearInterval(i);
  }, []);

  const riskColors: Record<string, string> = { low: 'var(--success)', medium: 'var(--warning)', high: '#f97316', critical: 'var(--danger)' };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">SLA Monitoring</h1>
        <p className="page-subtitle">Track at-risk and overdue workflows with automated escalation</p>
      </div>

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto' }} /></div>
      ) : workflows.length === 0 ? (
        <div className="glass-card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '12px' }}>✓</div>
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>All Clear</div>
          <div style={{ fontSize: '0.8rem' }}>No at-risk workflows at the moment. Start a workflow to see SLA monitoring.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {workflows.map((wf) => (
            <div key={wf.id} className="glass-card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>{wf.type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {wf.employee?.name || `ID: ${wf.id.slice(0, 8)}`} · Started {new Date(wf.createdAt).toLocaleString()}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span style={{
                    padding: '6px 14px', borderRadius: '20px', fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase',
                    background: `${riskColors[wf.sla.riskLevel]}20`, color: riskColors[wf.sla.riskLevel],
                  }}>{wf.sla.riskLevel} risk</span>
                  <span className={`badge badge-${wf.status.toLowerCase()}`}>{wf.status}</span>
                </div>
              </div>
              
              {/* Progress bar */}
              <div style={{ background: 'rgba(30, 41, 59, 0.5)', borderRadius: '4px', height: '6px', marginBottom: '12px' }}>
                <div style={{ background: `linear-gradient(90deg, var(--gradient-start), var(--gradient-end))`, borderRadius: '4px', height: '100%', width: `${wf.sla.progress}%`, transition: 'width 0.5s' }} />
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  {wf.sla.completedSteps}/{wf.sla.totalSteps} steps · {wf.sla.failedSteps} failed · {wf.sla.hoursElapsed}h elapsed
                </div>
                <Link href={`/workflows/${wf.id}`} style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: '0.8rem', fontWeight: 600 }}>View Execution →</Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
