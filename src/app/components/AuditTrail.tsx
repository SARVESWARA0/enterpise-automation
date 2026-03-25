'use client';

import { useRef, useEffect } from 'react';

interface StreamEvent {
  event_type: string;
  agent: string;
  step_id?: number | null;
  data: any;
  timestamp: string;
}

const AGENT_COLORS: Record<string, string> = {
  interpreter:  'var(--interpreter)',
  execution:    'var(--execution)',
  verification: 'var(--verification)',
  recovery:     'var(--recovery)',
  orchestrator: 'var(--orchestrator)',
};

function formatTime(ts: string) {
  if (!ts) return '';
  try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return ''; }
}

function getOutcomeColor(eventType: string): string {
  if (eventType.includes('complete') || eventType.includes('success')) return 'var(--success)';
  if (eventType.includes('failed') || eventType.includes('failure')) return 'var(--danger)';
  if (eventType.includes('recovery') || eventType.includes('escalat')) return 'var(--recovery)';
  return 'var(--text-secondary)';
}

function getOutcomeLabel(evt: StreamEvent): string {
  const data = evt.data || {};
  if (evt.event_type === 'step_complete') return '✓ OK';
  if (evt.event_type === 'step_failed') return data.status === 'ESCALATED' ? '⚡ ESC' : '✕ FAIL';
  if (evt.event_type === 'recovery') return data.action || 'RECOVER';
  if (evt.event_type === 'tool_result') return data.status === 'SUCCESS' ? '✓ OK' : '✕ FAIL';
  if (evt.event_type === 'workflow_complete') return data.status || 'DONE';
  return evt.event_type.split('_').pop() || '';
}

function getActionLabel(evt: StreamEvent): string {
  const data = evt.data || {};
  if (evt.event_type === 'tool_call') return `Call: ${data.tool || 'unknown'}`;
  if (evt.event_type === 'tool_result') return `Result: ${data.tool_called || data.tool || ''}`;
  if (evt.event_type === 'step_start') return `Start: ${data.name || ''}`;
  if (evt.event_type === 'step_complete') return `Done: ${data.name || ''}`;
  if (evt.event_type === 'step_failed') return `${data.status || 'Failed'}: ${data.reason || ''}`;
  if (evt.event_type === 'recovery') return data.message || data.reason || 'Recovery';
  if (evt.event_type === 'agent_message') return data.message?.substring(0, 60) || '';
  if (evt.event_type === 'workflow_complete') return data.summary?.substring(0, 60) || 'Workflow done';
  return evt.event_type;
}

export default function AuditTrail({ events }: { events: StreamEvent[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Filter to only show meaningful audit events
  const auditEvents = events.filter(e =>
    ['tool_call', 'tool_result', 'step_start', 'step_complete', 'step_failed',
     'recovery', 'workflow_complete'].includes(e.event_type)
  );

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [auditEvents.length]);

  return (
    <div className="panel audit-panel">
      <div className="panel-header">
        <span>Audit Trail</span>
        <span className="count">{auditEvents.length} entries</span>
      </div>
      <div className="panel-body" ref={scrollRef} style={{ padding: '4px 8px' }}>
        {auditEvents.length === 0 ? (
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', padding: '8px' }}>
            No audit entries yet...
          </div>
        ) : (
          auditEvents.map((evt, i) => (
            <div key={i} className="audit-row">
              <span className="audit-time">{formatTime(evt.timestamp)}</span>
              <span className="audit-agent" style={{ color: AGENT_COLORS[evt.agent] || 'var(--text-muted)' }}>
                {evt.agent || 'system'}
              </span>
              <span className="audit-action">{getActionLabel(evt)}</span>
              <span className="audit-outcome" style={{ color: getOutcomeColor(evt.event_type) }}>
                {getOutcomeLabel(evt)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
