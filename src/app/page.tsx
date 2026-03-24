'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface DashboardData {
  employees: { total: number; active: number };
  workflows: { total: number; running: number; completed: number; failed: number; escalated: number };
  recentActivity: Array<{ id: string; decision: string; reason: string; agentName: string; timestamp: string; status: string }>;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/dashboard').then(r => r.json()).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
    const interval = setInterval(() => { fetch('/api/dashboard').then(r => r.json()).then(setData); }, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '100px' }}><div className="spinner" /></div>;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Enterprise Autopilot</h1>
        <p className="page-subtitle">Multi-Agent Autonomous Workflow Orchestration</p>
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="glass-card stat-card">
          <span className="stat-value">{data?.employees.total || 0}</span>
          <span className="stat-label">Total Employees</span>
        </div>
        <div className="glass-card stat-card">
          <span className="stat-value">{data?.workflows.total || 0}</span>
          <span className="stat-label">Total Workflows</span>
        </div>
        <div className="glass-card stat-card">
          <span className="stat-value" style={{ background: 'linear-gradient(135deg, #10b981, #34d399)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{data?.workflows.completed || 0}</span>
          <span className="stat-label">Completed</span>
        </div>
        <div className="glass-card stat-card">
          <span className="stat-value" style={{ background: 'linear-gradient(135deg, #3b82f6, #60a5fa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{data?.workflows.running || 0}</span>
          <span className="stat-label">Running</span>
        </div>
        <div className="glass-card stat-card">
          <span className="stat-value" style={{ background: 'linear-gradient(135deg, #f59e0b, #fbbf24)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{data?.workflows.escalated || 0}</span>
          <span className="stat-label">Escalated</span>
        </div>
        <div className="glass-card stat-card">
          <span className="stat-value" style={{ background: 'linear-gradient(135deg, #ef4444, #f87171)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{data?.workflows.failed || 0}</span>
          <span className="stat-label">Failed</span>
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <Link href="/employees" style={{ textDecoration: 'none' }}>
          <div className="glass-card" style={{ padding: '20px', cursor: 'pointer' }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>◈</div>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>Employee Onboarding</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Create employees and watch the autonomous onboarding workflow execute</div>
          </div>
        </Link>
        <Link href="/workflows/new" style={{ textDecoration: 'none' }}>
          <div className="glass-card" style={{ padding: '20px', cursor: 'pointer' }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>✦</div>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>Custom Workflow</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Enter any workflow description and watch dynamic multi-agent execution</div>
          </div>
        </Link>
        <Link href="/audit" style={{ textDecoration: 'none' }}>
          <div className="glass-card" style={{ padding: '20px', cursor: 'pointer' }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>◉</div>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>Audit Trail</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Full audit logs with every decision, tool call, and recovery action</div>
          </div>
        </Link>
      </div>

      {/* Recent Activity */}
      <div className="glass-card" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '16px', margin: '0 0 16px 0' }}>Recent Activity</h3>
        {(!data?.recentActivity || data.recentActivity.length === 0) ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>No recent activity. Create an employee to trigger a workflow!</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {data.recentActivity.map((log) => (
              <div key={log.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px', borderRadius: '8px', background: 'rgba(99, 102, 241, 0.03)' }}>
                <span className={`badge badge-${log.status || 'pending'}`}>{log.status || 'info'}</span>
                <span style={{ flex: 1, fontSize: '0.8rem' }}>{log.decision}: {log.reason?.substring(0, 80)}</span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{new Date(log.timestamp).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
