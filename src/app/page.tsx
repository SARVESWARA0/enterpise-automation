'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const SCENARIOS = [
  {
    icon: '🧑‍💼',
    title: 'Onboard a New Employee',
    desc: 'Auto-create HR, email, JIRA accounts, assign buddy, schedule orientation, and send welcome email.',
    request: 'Onboard Sarah Chen, joining Engineering team, starting Monday. Email: sarah.chen@company.com',
  },
  {
    icon: '📋',
    title: 'Process Meeting Transcript',
    desc: 'Extract action items from a meeting, assign owners, create tasks, and send summary.',
    request: 'Process this meeting transcript: [John: I\'ll fix the login bug by Friday. Sarah: I\'ll prepare the Q3 report. Action: Team sync needed next week - owner unclear]',
  },
  {
    icon: '⏱️',
    title: 'Resolve SLA Breach',
    desc: 'Detect stuck approvals, reroute to delegates, escalate if needed, and log audit trail.',
    request: 'Procurement approval for vendor contract #VC-2024 has been stuck for 48 hours. Original approver is on leave.',
  },
];

export default function LandingPage() {
  const [customRequest, setCustomRequest] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function startWorkflow(request: string) {
    if (!request.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/workflows/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request }),
      });
      const data = await res.json();
      if (data.workflow_id) {
        router.push(`/workflows/${data.workflow_id}`);
      }
    } catch (err) {
      console.error('Failed to start workflow:', err);
      setLoading(false);
    }
  }

  return (
    <div className="landing">
      {/* Hero */}
      <div className="landing-hero">
        <h1>ET Autopilot</h1>
        <p>
          Multi-agent AI that plans, executes, verifies and recovers —
          with zero hand-holding.
        </p>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Powered by Strands Multi-Agent SDK · PS2 Agentic Enterprise Workflows
        </p>
        <div className="metric-banner">
          ⚡ Saves ~4.5 hours per employee onboarding · 87% autonomous completion rate
        </div>
      </div>

      {/* Scenario Tiles */}
      <div className="scenario-grid">
        {SCENARIOS.map((s, i) => (
          <div
            key={i}
            className="scenario-card"
            onClick={() => {
              setCustomRequest(s.request);
              startWorkflow(s.request);
            }}
          >
            <div className="scenario-icon">{s.icon}</div>
            <div className="scenario-title">{s.title}</div>
            <div className="scenario-desc">{s.desc}</div>
          </div>
        ))}
      </div>

      {/* Custom Input */}
      <div className="custom-input-area">
        <input
          className="input-field"
          placeholder="Or describe your own workflow..."
          value={customRequest}
          onChange={(e) => setCustomRequest(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && startWorkflow(customRequest)}
          disabled={loading}
        />
        <button
          className="btn-primary"
          onClick={() => startWorkflow(customRequest)}
          disabled={loading || !customRequest.trim()}
        >
          {loading ? (
            <><span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Starting...</>
          ) : (
            <>▶ Start</>
          )}
        </button>
      </div>

      {/* Subtle Footer */}
      <div style={{
        color: 'var(--text-muted)',
        fontSize: '0.65rem',
        fontFamily: 'var(--font-mono)',
        textAlign: 'center',
        marginTop: '20px',
      }}>
        ET AI Hackathon 2026 · Problem Statement 2 · Agentic AI for Autonomous Enterprise Workflows
      </div>
    </div>
  );
}
