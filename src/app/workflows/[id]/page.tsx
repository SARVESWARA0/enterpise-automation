'use client';

import { useEffect, useState, use } from 'react';
import AgentStream from '../../components/AgentStream';
import ExecutionPlan from '../../components/ExecutionPlan';
import AgentRoster from '../../components/AgentRoster';
import AuditTrail from '../../components/AuditTrail';

interface StreamEvent {
  event_type: string;
  agent: string;
  step_id?: number | null;
  data: any;
  timestamp: string;
}

interface PlanStep {
  step_id: number;
  name: string;
  tool_name: string;
  status?: string;
}

export default function WorkflowDashboard({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [steps, setSteps] = useState<PlanStep[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState('STARTING');
  const [showModal, setShowModal] = useState(false);
  const [summary, setSummary] = useState<any>(null);

  // SSE Connection
  useEffect(() => {
    // Connect directly to backend — Next.js rewrites buffer SSE responses
    const backendUrl = typeof window !== 'undefined'
      ? `http://${window.location.hostname}:8000`
      : 'http://localhost:8000';
    const es = new EventSource(`${backendUrl}/api/workflows/${id}/stream`);

    es.onmessage = (e) => {
      try {
        const event: StreamEvent = JSON.parse(e.data);

        // Skip heartbeats
        if (event.event_type === 'heartbeat') return;

        setEvents(prev => [...prev, event]);

        // Update plan steps when we get a plan event
        if (event.event_type === 'plan' && event.data?.steps) {
          setSteps(event.data.steps.map((s: any) => ({
            ...s,
            status: 'PENDING',
          })));
          setWorkflowStatus('RUNNING');
        }

        // Update step statuses
        if (event.event_type === 'step_start' && event.step_id != null) {
          setSteps(prev => prev.map(s =>
            s.step_id === event.step_id ? { ...s, status: 'RUNNING' } : s
          ));
        }
        if (event.event_type === 'step_complete' && event.data?.step_id != null) {
          setSteps(prev => prev.map(s =>
            s.step_id === event.data.step_id ? { ...s, status: 'COMPLETED' } : s
          ));
        }
        if (event.event_type === 'step_failed' && event.data?.step_id != null) {
          const newStatus = event.data.status || 'FAILED';
          setSteps(prev => prev.map(s =>
            s.step_id === event.data.step_id ? { ...s, status: newStatus } : s
          ));
        }

        // Workflow complete
        if (event.event_type === 'workflow_complete') {
          setWorkflowStatus(event.data?.status || 'COMPLETED');
          setSummary(event.data);
          setShowModal(true);
          es.close();
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      // EventSource auto-reconnects
    };

    return () => es.close();
  }, [id]);

  const completedCount = steps.filter(s => s.status === 'COMPLETED').length;
  const activeStep = steps.find(s => s.status === 'RUNNING');

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header Bar */}
      <div className="dash-header">
        <div className="logo">
          <span className="accent">ET</span> AUTOPILOT
          <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', fontWeight: 400 }}>
            · Workflow #{id.substring(0, 8)}
          </span>
        </div>
        <div className="meta">
          <span className={`badge badge-${workflowStatus.toLowerCase()}`}>
            {workflowStatus === 'RUNNING' && <span className="pulse-dot" style={{ background: 'var(--info)' }} />}
            {workflowStatus}
          </span>
          {steps.length > 0 && (
            <span>{completedCount}/{steps.length} steps</span>
          )}
        </div>
      </div>

      {/* 4-Panel Grid */}
      <div className="dashboard-grid">
        <ExecutionPlan
          steps={steps}
          activeStepId={activeStep?.step_id}
        />
        <AgentStream events={events} />
        <AgentRoster events={events} />
        <AuditTrail events={events} />
      </div>

      {/* Workflow Complete Modal */}
      {showModal && summary && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ color: summary.status === 'COMPLETED' ? 'var(--success)' : 'var(--recovery)' }}>
              {summary.status === 'COMPLETED' ? '🎉 Workflow Complete' : '⚠️ Workflow Finished'}
            </h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '20px', fontSize: '0.85rem' }}>
              {summary.summary}
            </p>
            <div className="stat-row">
              <span className="label">Total Steps</span>
              <span className="value">{summary.total_steps}</span>
            </div>
            <div className="stat-row">
              <span className="label">Completed</span>
              <span className="value" style={{ color: 'var(--success)' }}>{summary.completed}</span>
            </div>
            <div className="stat-row">
              <span className="label">Escalated</span>
              <span className="value" style={{ color: 'var(--recovery)' }}>{summary.escalated}</span>
            </div>
            <div className="stat-row">
              <span className="label">Failed</span>
              <span className="value" style={{ color: 'var(--danger)' }}>{summary.failed}</span>
            </div>
            <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
              <button className="btn-primary" onClick={() => window.location.href = '/'}>
                ← New Workflow
              </button>
              <button className="btn-secondary" onClick={() => setShowModal(false)}>
                View Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
