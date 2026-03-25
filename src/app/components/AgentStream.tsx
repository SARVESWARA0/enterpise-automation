'use client';

import { useRef, useEffect, useMemo } from 'react';

interface StreamEvent {
  event_type: string;
  agent: string;
  step_id?: number | null;
  data: any;
  timestamp: string;
}

const AGENT_META: Record<string, { emoji: string; color: string; label: string }> = {
  interpreter:   { emoji: '🧠', color: 'var(--interpreter)', label: 'Interpreter' },
  execution:     { emoji: '⚡', color: 'var(--execution)',    label: 'Execution' },
  verification:  { emoji: '🔍', color: 'var(--verification)', label: 'Verification' },
  recovery:      { emoji: '🚑', color: 'var(--recovery)',     label: 'Recovery' },
  orchestrator:  { emoji: '⚙️', color: 'var(--orchestrator)', label: 'Orchestrator' },
};

function getAgent(name: string) {
  return AGENT_META[name] || { emoji: '🤖', color: 'var(--text-muted)', label: name || 'System' };
}

function formatTime(ts: string) {
  if (!ts) return '';
  try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return ''; }
}

function snakeToTitle(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function renderParams(params: Record<string, any>) {
  return Object.entries(params).map(([k, v]) => (
    <div key={k} className="param-row">
      <span className="param-key">{snakeToTitle(k)}</span>
      <span className="param-arrow">→</span>
      <span className="param-value">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
    </div>
  ));
}

/**
 * Collapse consecutive token_stream events from the same agent into a
 * single "thinking bubble" with the concatenated text.
 */
function collapseTokens(events: StreamEvent[]): StreamEvent[] {
  const result: StreamEvent[] = [];
  let i = 0;

  while (i < events.length) {
    const evt = events[i];

    if (evt.event_type === 'token_stream') {
      // Accumulate consecutive token_stream events from the same agent
      let accumulated = evt.data?.chunk || '';
      const agentName = evt.agent;
      const stepId = evt.step_id;
      const timestamp = evt.timestamp;
      let j = i + 1;

      while (j < events.length &&
             events[j].event_type === 'token_stream' &&
             events[j].agent === agentName) {
        accumulated += events[j].data?.chunk || '';
        j++;
      }

      result.push({
        event_type: '__token_group__',
        agent: agentName,
        step_id: stepId,
        timestamp,
        data: {
          text: accumulated,
          is_reasoning: evt.data?.is_reasoning,
          // is the last event still a token (meaning agent is still thinking)?
          live: j < events.length ? false : events[j - 1]?.event_type === 'token_stream',
        },
      });
      i = j;
    } else {
      result.push(evt);
      i++;
    }
  }

  return result;
}

export default function AgentStream({ events }: { events: StreamEvent[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const collapsed = useMemo(() => collapseTokens(events), [events]);

  return (
    <div className="panel stream-panel">
      <div className="panel-header">
        <span>Agent Stream</span>
        <span className="count">{events.length} events</span>
      </div>
      <div className="panel-body" ref={scrollRef} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {collapsed.length === 0 && (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '20px', textAlign: 'center' }}>
            Waiting for agent activity...
          </div>
        )}

        {collapsed.map((evt, i) => {
          const agent = getAgent(evt.agent);
          const data = evt.data || {};
          const time = formatTime(evt.timestamp);

          // ── Live token group — agent thinking bubble ──
          if (evt.event_type === '__token_group__') {
            const isReasoning = data.is_reasoning;
            return (
              <div key={i} className="agent-bubble">
                <div className="agent-avatar" style={{ borderColor: agent.color }}>{agent.emoji}</div>
                <div className="agent-bubble-content">
                  <div className="agent-bubble-name" style={{ color: agent.color }}>
                    {agent.label}
                    {isReasoning && (
                      <span style={{ fontSize: '0.65rem', opacity: 0.6, marginLeft: 6, fontStyle: 'italic' }}>
                        reasoning
                      </span>
                    )}
                    <span className="time">{time}</span>
                  </div>
                  <div
                    className="agent-bubble-text"
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.72rem',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      background: isReasoning ? 'rgba(139,92,246,0.05)' : 'rgba(96,165,250,0.04)',
                      borderColor: isReasoning ? 'rgba(139,92,246,0.2)' : agent.color + '30',
                      lineHeight: 1.6,
                    }}
                  >
                    {data.text}
                    {data.live && (
                      <span
                        style={{
                          display: 'inline-block',
                          width: '7px',
                          height: '12px',
                          background: agent.color,
                          marginLeft: '2px',
                          verticalAlign: 'text-bottom',
                          borderRadius: '1px',
                          animation: 'blink 1s step-end infinite',
                          opacity: 0.8,
                        }}
                      />
                    )}
                  </div>
                </div>
              </div>
            );
          }

          // ── Tool start from within agent stream ──
          if (evt.event_type === 'agent_tool_start') {
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 8px' }}>
                <span style={{ color: agent.color, fontSize: '0.7rem' }}>{agent.emoji}</span>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  background: 'rgba(96,165,250,0.08)', border: '1px solid rgba(96,165,250,0.2)',
                  borderRadius: '12px', padding: '3px 10px',
                  fontSize: '0.7rem', color: 'var(--execution)',
                }}>
                  <span style={{ opacity: 0.6 }}>calling</span>
                  <code style={{ fontWeight: 700 }}>{data.tool}</code>
                  <span style={{
                    display: 'inline-block', width: '6px', height: '6px',
                    borderRadius: '50%', background: 'var(--execution)',
                    animation: 'pulse 1.2s ease-in-out infinite',
                  }} />
                </span>
              </div>
            );
          }

          // ── Agent Message → Chat Bubble ──
          if (evt.event_type === 'agent_message') {
            const message = data.message || data.verdict
              ? `${data.verdict ? `Verdict: ${data.verdict}` : ''}${data.reason ? ` — ${data.reason}` : ''}${data.confidence != null ? ` (${Math.round(data.confidence * 100)}% confidence)` : ''}${data.message || ''}`
              : JSON.stringify(data);

            return (
              <div key={i} className="agent-bubble">
                <div className="agent-avatar" style={{ borderColor: agent.color }}>{agent.emoji}</div>
                <div className="agent-bubble-content">
                  <div className="agent-bubble-name" style={{ color: agent.color }}>
                    {agent.label}
                    <span className="time">{time}</span>
                  </div>
                  <div className="agent-bubble-text">{message}</div>
                </div>
              </div>
            );
          }

          // ── Plan Event → Plan Summary Bubble ──
          if (evt.event_type === 'plan') {
            const steps = data.steps || [];
            return (
              <div key={i} className="agent-bubble">
                <div className="agent-avatar" style={{ borderColor: agent.color }}>{agent.emoji}</div>
                <div className="agent-bubble-content">
                  <div className="agent-bubble-name" style={{ color: agent.color }}>
                    {agent.label} — Execution Plan
                    <span className="time">{time}</span>
                  </div>
                  <div className="agent-bubble-text">
                    {steps.map((s: any, j: number) => (
                      <div key={j} style={{ padding: '4px 0', borderBottom: j < steps.length - 1 ? '1px solid var(--border)' : 'none' }}>
                        <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.7rem', marginRight: '8px' }}>{s.step_id}.</span>
                        <span style={{ fontWeight: 600, fontSize: '0.78rem' }}>{s.name}</span>
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem', marginLeft: '8px', fontFamily: 'var(--font-mono)' }}>{s.tool_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          }

          // ── Tool Call → Cursor-style Block ──
          if (evt.event_type === 'tool_call') {
            return (
              <div key={i} className="stream-card tool-call">
                <div className="stream-card-header">
                  <span>⚡ TOOL CALL</span>
                  <span>{data.tool || 'unknown'}</span>
                  {data.attempt && <span style={{ opacity: 0.5 }}>attempt {data.attempt}</span>}
                </div>
                <div className="stream-card-body">
                  {data.parameters && renderParams(data.parameters)}
                  {data.reason && (
                    <div style={{ marginTop: '6px', color: 'var(--recovery)', fontSize: '0.7rem' }}>
                      {data.reason}
                    </div>
                  )}
                </div>
              </div>
            );
          }

          // ── Tool Result ──
          if (evt.event_type === 'tool_result') {
            const isSuccess = data.status === 'SUCCESS' || data.status === 'success';
            const cardClass = isSuccess ? 'tool-result-success' : 'tool-result-failure';
            return (
              <div key={i} className={`stream-card ${cardClass}`}>
                <div className="stream-card-header">
                  <span>{isSuccess ? '✓ RESULT' : '✕ RESULT'}</span>
                  <span>{isSuccess ? 'SUCCESS' : 'FAILED'}</span>
                </div>
                <div className="stream-card-body">
                  {data.output && typeof data.output === 'object'
                    ? renderParams(data.output)
                    : data.output
                      ? <div className="param-row"><span className="param-value">{String(data.output).substring(0, 300)}</span></div>
                      : null
                  }
                  {data.error && (
                    <div style={{ color: 'var(--danger)', marginTop: '4px' }}>Error: {data.error}</div>
                  )}
                </div>
              </div>
            );
          }

          // ── Recovery Event ──
          if (evt.event_type === 'recovery') {
            const action = data.action;
            return (
              <div key={i} className="stream-card recovery-card">
                <div className="stream-card-header">
                  <span>🚑 Recovery Agent</span>
                  {action && <span className="badge badge-escalated">{action}</span>}
                </div>
                <div className="stream-card-body">
                  {data.message && <div>{data.message}</div>}
                  {data.reason && <div style={{ marginTop: '4px' }}>Reason: {data.reason}</div>}
                  {data.audit_message && (
                    <div style={{ marginTop: '4px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      Audit: {data.audit_message}
                    </div>
                  )}
                </div>
              </div>
            );
          }

          // ── Step Start / Complete / Failed ──
          if (evt.event_type === 'step_start') {
            return (
              <div key={i} className="agent-bubble">
                <div className="agent-avatar" style={{ borderColor: 'var(--execution)' }}>⚡</div>
                <div className="agent-bubble-content">
                  <div className="agent-bubble-name" style={{ color: 'var(--execution)' }}>
                    Step {data.step_id}: {data.name}
                    <span className="time">{time}</span>
                  </div>
                  <div className="agent-bubble-text" style={{ background: 'rgba(96,165,250,0.05)', borderColor: 'rgba(96,165,250,0.15)' }}>
                    Executing <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--execution)' }}>{data.tool}</span>
                  </div>
                </div>
              </div>
            );
          }

          if (evt.event_type === 'step_complete') {
            return (
              <div key={i} className="agent-bubble">
                <div className="agent-avatar" style={{ borderColor: 'var(--verification)' }}>✓</div>
                <div className="agent-bubble-content">
                  <div className="agent-bubble-name" style={{ color: 'var(--verification)' }}>
                    Step {data.step_id} Complete
                    <span className="time">{time}</span>
                  </div>
                  <div className="agent-bubble-text" style={{ background: 'rgba(52,211,153,0.05)', borderColor: 'rgba(52,211,153,0.15)' }}>
                    ✅ {data.name}
                  </div>
                </div>
              </div>
            );
          }

          if (evt.event_type === 'step_failed') {
            const isEscalated = data.status === 'ESCALATED';
            return (
              <div key={i} className="agent-bubble">
                <div className="agent-avatar" style={{ borderColor: isEscalated ? 'var(--recovery)' : 'var(--danger)' }}>
                  {isEscalated ? '⚡' : '✕'}
                </div>
                <div className="agent-bubble-content">
                  <div className="agent-bubble-name" style={{ color: isEscalated ? 'var(--recovery)' : 'var(--danger)' }}>
                    Step {data.step_id} {isEscalated ? 'Escalated' : 'Failed'}
                    <span className="time">{time}</span>
                  </div>
                  <div className="agent-bubble-text" style={{
                    background: isEscalated ? 'rgba(251,146,60,0.05)' : 'rgba(239,68,68,0.05)',
                    borderColor: isEscalated ? 'rgba(251,146,60,0.15)' : 'rgba(239,68,68,0.15)',
                  }}>
                    {data.reason || data.message || `Step ${data.step_id} ${data.status}`}
                  </div>
                </div>
              </div>
            );
          }

          // ── Workflow Complete ──
          if (evt.event_type === 'workflow_complete') {
            return (
              <div key={i} className="agent-bubble">
                <div className="agent-avatar" style={{ borderColor: 'var(--success)' }}>🏁</div>
                <div className="agent-bubble-content">
                  <div className="agent-bubble-name" style={{ color: 'var(--success)' }}>
                    Workflow Complete
                    <span className="time">{time}</span>
                  </div>
                  <div className="agent-bubble-text" style={{ background: 'rgba(16,185,129,0.05)', borderColor: 'rgba(16,185,129,0.15)' }}>
                    {data.summary || `${data.completed}/${data.total_steps} steps completed`}
                    {data.escalated > 0 && ` · ${data.escalated} escalated`}
                  </div>
                </div>
              </div>
            );
          }

          // ── Heartbeat — skip silently ──
          if (evt.event_type === 'heartbeat') return null;

          // ── Default: generic bubble ──
          return (
            <div key={i} className="agent-bubble">
              <div className="agent-avatar" style={{ borderColor: agent.color }}>{agent.emoji}</div>
              <div className="agent-bubble-content">
                <div className="agent-bubble-name" style={{ color: agent.color }}>
                  {agent.label}
                  <span className="time">{time}</span>
                </div>
                <div className="agent-bubble-text">{JSON.stringify(data).substring(0, 200)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
