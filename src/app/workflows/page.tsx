'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Workflow {
  id: string;
  type: string;
  status: string;
  triggerEvent: string;
  createdAt: string;
  employee?: { name: string };
  steps: Array<{ id: string; stepName: string; status: string }>;
  _count: { auditLogs: number };
}

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Prompt input state
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const fetchWorkflows = () => fetch('/api/workflows').then(r => r.json()).then(d => { setWorkflows(d); setLoading(false); });
    fetchWorkflows();
    const i = setInterval(fetchWorkflows, 3000);
    return () => clearInterval(i);
  }, []);

  const handlePromptSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: prompt, // The raw prompt intent
          inputData: {} 
        })
      });
      const data = await res.json();
      if (data.workflowId) {
        router.push(`/workflows/${data.workflowId}`);
      }
    } catch (e) {
      console.error(e);
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <div className="page-header" style={{ textAlign: 'center', marginBottom: '40px' }}>
        <h1 className="page-title" style={{ fontSize: '2.5rem', marginBottom: '10px' }}>Enterprise Autopilot</h1>
        <p className="page-subtitle" style={{ fontSize: '1.2rem' }}>What would you like me to do?</p>
      </div>

      {/* Hero Chat Prompt Area */}
      <div style={{ maxWidth: '800px', margin: '0 auto 60px auto' }}>
        <form onSubmit={handlePromptSubmit} style={{ position: 'relative' }}>
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isSubmitting}
            placeholder="e.g. Check SLA for yesterday's outage, or Send a welcome email to Sarah..."
            style={{
              width: '100%',
              padding: '24px 80px 24px 30px',
              fontSize: '1.2rem',
              borderRadius: '30px',
              border: '1px solid var(--border)',
              background: 'var(--surface-50)',
              color: 'var(--text-primary)',
              boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
              outline: 'none',
              transition: 'all 0.3s'
            }}
          />
          <button 
            type="submit" 
            disabled={!prompt.trim() || isSubmitting}
            style={{
              position: 'absolute',
              right: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              background: prompt.trim() ? 'var(--accent)' : 'var(--surface-100)',
              color: 'white',
              border: 'none',
              borderRadius: '50%',
              width: '50px',
              height: '50px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: prompt.trim() ? 'pointer' : 'not-allowed',
              transition: 'all 0.3s'
            }}
          >
            {isSubmitting ? (
              <div className="spinner" style={{ width: '20px', height: '20px', borderWidth: '2px' }} />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            )}
          </button>
        </form>
        <div style={{ display: 'flex', gap: '10px', marginTop: '15px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <span className="badge badge-pending" style={{ cursor: 'pointer' }} onClick={() => setPrompt("Audit recent employee changes")}>Audit recent employee changes</span>
          <span className="badge badge-pending" style={{ cursor: 'pointer' }} onClick={() => setPrompt("Schedule a team sync for next week")}>Schedule a team sync for next week</span>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ color: 'var(--text-primary)' }}>Execution History</h2>
      </div>

      <div className="glass-card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto' }} /></div>
        ) : workflows.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>No workflow history yet. Create a prompt above.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Intent</th>
                <th>Status</th>
                <th>Steps</th>
                <th>Audit</th>
                <th>Started</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((wf) => {
                const completed = wf.steps.filter(s => s.status === 'COMPLETED').length;
                return (
                  <tr key={wf.id}>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {wf.type}
                    </td>
                    <td>
                      <span className={`badge badge-${wf.status.toLowerCase()}`}>
                        {wf.status === 'RUNNING' && <span className="pulse-dot" style={{ background: 'var(--info)' }} />}
                        {wf.status}
                      </span>
                    </td>
                    <td>{completed}/{wf.steps.length}</td>
                    <td>{wf._count.auditLogs}</td>
                    <td style={{ fontSize: '0.8rem' }}>{new Date(wf.createdAt).toLocaleString()}</td>
                    <td>
                      <Link href={`/workflows/${wf.id}`} style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: '0.8rem', fontWeight: 600 }}>
                        View Chat →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
