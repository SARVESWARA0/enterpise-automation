'use client';

import { useEffect, useState, useRef, use } from 'react';

interface Step {
  id?: string;
  stepName: string;
  stepDescription?: string;
  stepType?: string;
  toolName?: string;
  status: string;
  assignedAgent: string;
  retryCount: number;
  dependencyOrder: number;
  fallbackBehavior?: string;
}
interface StreamEvent {
  type: string;
  workflowId: string;
  stepId?: string;
  agentName?: string;
  message: string;
  data?: any;
  timestamp?: string;
}
interface AuditEntry {
  id: string;
  decision: string;
  reason: string;
  agentName: string;
  status: string;
  timestamp: string;
  toolName?: string;
}
interface Workflow {
  id: string;
  type: string;
  status: string;
  plan?: Step[];
  steps: Step[];
  auditLogs?: AuditEntry[];
}

const AGENT_CONFIG: Record<string, { emoji: string; color: string; label: string }> = {
  InterpreterAgent: { emoji: '🧠', color: 'var(--purple, #a78bfa)', label: 'Interpreter' },
  PlannerAgent:     { emoji: '🧠', color: 'var(--purple, #a78bfa)', label: 'Planner' },
  DecisionAgent:    { emoji: '🧭', color: '#22d3ee', label: 'Decision' },
  ExecutionAgent:   { emoji: '⚡', color: 'var(--info)', label: 'Execution' },
  VerificationAgent:{ emoji: '✅', color: 'var(--success)', label: 'Verification' },
  RecoveryAgent:    { emoji: '🚑', color: 'var(--warning)', label: 'Recovery' },
  ClarificationAgent:{ emoji: '🔍', color: '#06b6d4', label: 'Clarification' },
  HealthMonitorAgent:{ emoji: '📊', color: '#f97316', label: 'Health Monitor' },
  Orchestrator:     { emoji: '🎯', color: 'var(--accent)', label: 'Orchestrator' },
  Graph:            { emoji: '📊', color: 'var(--text-muted)', label: 'Graph' },
};

function getAgent(name?: string) {
  return AGENT_CONFIG[name || ''] || { emoji: '🤖', color: 'var(--text-muted)', label: name || 'System' };
}

function getStepStatusBadge(status: string) {
  const map: Record<string, { color: string; bg: string }> = {
    PENDING:   { color: '#fbbf24', bg: 'rgba(245,158,11,0.15)' },
    RUNNING:   { color: '#60a5fa', bg: 'rgba(59,130,246,0.15)' },
    COMPLETED: { color: '#34d399', bg: 'rgba(16,185,129,0.15)' },
    FAILED:    { color: '#f87171', bg: 'rgba(239,68,68,0.15)' },
    ESCALATED: { color: '#fbbf24', bg: 'rgba(245,158,11,0.15)' },
    AWAITING_CLARIFICATION: { color: '#22d3ee', bg: 'rgba(6,182,212,0.15)' },
    SKIPPED:   { color: '#94a3b8', bg: 'rgba(100,116,139,0.15)' },
  };
  return map[status] || map.PENDING;
}

export default function WorkflowExecutionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const chatRef = useRef<HTMLDivElement>(null);

  // Fetch workflow data
  useEffect(() => {
    const fetchWorkflow = () =>
      fetch(`/api/workflows/${id}`)
        .then((r) => r.json())
        .then((d) => { setWorkflow(d); setLoading(false); });
    fetchWorkflow();
    const i = setInterval(fetchWorkflow, 3000);
    return () => clearInterval(i);
  }, [id]);

  // SSE stream
  useEffect(() => {
    const es = new EventSource(`/api/workflows/${id}/stream`);
    es.onmessage = (e) => {
      try {
        const event: StreamEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, event]);
      } catch {}
    };
    // Let browser auto-reconnect on error
    return () => es.close();
  }, [id]);

  // Auto-scroll
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [events]);

  if (loading)
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '100px' }}>
        <div className="spinner" />
      </div>
    );
  if (!workflow)
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Workflow not found
      </div>
    );

  const steps = workflow.steps || [];
  const auditLogs = workflow.auditLogs || [];

  // Derive active agents from recent events
  const activeAgents = new Map<string, string>();
  events.slice(-20).forEach((evt) => {
    if (evt.agentName) activeAgents.set(evt.agentName, evt.message);
  });

  const filteredEvents = events.filter(
    (e) =>
      e.type.startsWith('chat:') ||
      e.type.startsWith('agent:') ||
      e.type === 'workflow:start' ||
      e.type === 'workflow:complete' ||
      e.type === 'workflow:failed',
  );

  return (
    <div style={{ height: 'calc(100vh - 70px)', display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 0 16px 0' }}>
        <div>
          <h1 className="page-title" style={{ fontSize: '1.3rem' }}>Autopilot Console</h1>
          <p className="page-subtitle" style={{ fontSize: '0.8rem' }}>Live multi-agent execution</p>
        </div>
        <span className={`badge badge-${(workflow.status || 'pending').toLowerCase()}`} style={{ fontSize: '0.85rem', padding: '6px 14px' }}>
          {workflow.status === 'RUNNING' && <span className="pulse-dot" style={{ background: 'var(--info)', width: '8px', height: '8px' }} />}
          {workflow.status || 'LOADING'}
        </span>
      </div>

      {/* 4-Panel Grid */}
      <div className="execution-grid" style={{ flex: 1, minHeight: 0 }}>

        {/* LEFT PANEL: Step List */}
        <div className="left-panel glass-card" style={{ padding: '16px', overflow: 'auto' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', margin: '0 0 12px 0' }}>
            Execution Plan
          </h3>
          {steps.length === 0 ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Generating plan...</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {steps.map((step, i) => {
                const badge = getStepStatusBadge(step.status);
                const agent = getAgent(step.assignedAgent);
                return (
                  <div key={step.id || i} style={{
                    padding: '10px 12px', borderRadius: '8px',
                    background: step.status === 'RUNNING' ? 'rgba(59,130,246,0.08)' : 'var(--surface-50, rgba(255,255,255,0.03))',
                    borderLeft: `3px solid ${badge.color}`,
                    transition: 'all 0.3s',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {i + 1}. {step.stepName}
                      </span>
                      <span style={{
                        fontSize: '0.6rem', fontWeight: 600, padding: '2px 6px', borderRadius: '9999px',
                        background: badge.bg, color: badge.color, textTransform: 'uppercase',
                      }}>
                        {step.status === 'RUNNING' && <span className="pulse-dot" style={{ background: badge.color, width: '5px', height: '5px', display: 'inline-block', marginRight: '3px' }} />}
                        {step.status}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span>{agent.emoji} {agent.label}</span>
                      {step.stepType && <span style={{ opacity: 0.7 }}>• {step.stepType}</span>}
                      {step.toolName && <span style={{ opacity: 0.5 }}>🔧 {step.toolName}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* CENTER PANEL: Agent Stream Chat */}
        <div className="center-panel glass-card" style={{ padding: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>
            Agent Activity
          </div>
          <div ref={chatRef} style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* User prompt */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '10px' }}>
              <div style={{
                background: 'var(--accent)', color: 'white', padding: '12px 20px',
                borderRadius: '20px 20px 4px 20px', maxWidth: '80%', fontSize: '0.95rem',
                boxShadow: '0 4px 15px rgba(99,102,241,0.3)',
              }}>
                {workflow.type}
              </div>
            </div>

            {filteredEvents.length === 0 && workflow.status === 'RUNNING' && (
              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ fontSize: '1.3rem' }}>🤖</div>
                <div style={{ background: 'var(--surface-50, rgba(255,255,255,0.03))', padding: '12px 16px', borderRadius: '4px 20px 20px 20px', color: 'var(--text-muted)' }}>
                  Thinking...
                </div>
              </div>
            )}

            {filteredEvents.map((evt, i) => {
              const isError = evt.type === 'chat:error' || evt.type === 'workflow:failed';
              const isSystem = evt.type === 'workflow:start' || evt.type === 'workflow:complete' || evt.type === 'workflow:failed';
              const agentName = isSystem ? 'Orchestrator' : (evt.agentName || 'System');
              const agent = getAgent(agentName);

              return (
                <div key={i} style={{ display: 'flex', gap: '10px', maxWidth: '90%' }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '50%',
                    background: 'var(--surface-100, rgba(255,255,255,0.05))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.95rem', border: `2px solid ${agent.color}`, flexShrink: 0,
                  }}>
                    {agent.emoji}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: agent.color }}>
                      {agent.label}
                      <span style={{
                        color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.6rem', marginLeft: '6px',
                      }}>
                        {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}
                      </span>
                    </div>
                    <div style={{
                      background: isError ? 'rgba(239,68,68,0.1)' : 'var(--surface-50, rgba(255,255,255,0.03))',
                      border: isError ? '1px solid rgba(239,68,68,0.3)' : '1px solid var(--border)',
                      padding: '10px 14px', borderRadius: '4px 16px 16px 16px',
                      color: isError ? 'var(--danger)' : 'var(--text-primary)',
                      fontSize: '0.85rem', lineHeight: '1.5', wordBreak: 'break-word',
                    }}>
                      {evt.message}

                      {/* Render plan steps */}
                      {evt.type === 'chat:plan_generated' && evt.data?.steps && (
                        <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {evt.data.steps.map((s: any, j: number) => (
                            <div key={j} style={{
                              background: 'var(--surface-100, rgba(255,255,255,0.05))', padding: '8px 10px',
                              borderRadius: '6px', borderLeft: '3px solid var(--info)',
                            }}>
                              <div style={{ fontWeight: 600, fontSize: '0.8rem', marginBottom: '2px' }}>
                                {j + 1}. {s.stepName}
                                {s.assignedAgent && (
                                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: '6px' }}>
                                    → {s.assignedAgent}
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                {s.stepDescription || s.toolName}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT PANEL: Active Agents */}
        <div className="right-panel glass-card" style={{ padding: '16px', overflow: 'auto' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', margin: '0 0 12px 0' }}>
            Agent Roster
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {Object.entries(AGENT_CONFIG).map(([name, cfg]) => {
              const isActive = activeAgents.has(name);
              const lastMsg = activeAgents.get(name);
              return (
                <div key={name} style={{
                  padding: '10px', borderRadius: '8px',
                  background: isActive ? `${cfg.color}10` : 'transparent',
                  border: `1px solid ${isActive ? cfg.color + '40' : 'var(--border)'}`,
                  opacity: isActive ? 1 : 0.5,
                  transition: 'all 0.3s',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: isActive ? '4px' : '0' }}>
                    <span style={{ fontSize: '1rem' }}>{cfg.emoji}</span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isActive ? cfg.color : 'var(--text-muted)' }}>
                      {cfg.label}
                    </span>
                    {isActive && <span className="pulse-dot" style={{ background: cfg.color, width: '6px', height: '6px' }} />}
                  </div>
                  {isActive && lastMsg && (
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: '28px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {lastMsg.substring(0, 60)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* BOTTOM PANEL: Audit Log */}
        <div className="bottom-panel glass-card" style={{ padding: '12px 16px', overflow: 'auto' }}>
          <h3 style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', margin: '0 0 8px 0' }}>
            Audit Trail
          </h3>
          {auditLogs.length === 0 ? (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No audit entries yet...</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {auditLogs.slice(-15).map((log) => (
                <div key={log.id} style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 8px',
                  borderRadius: '6px', background: 'rgba(99,102,241,0.03)', fontSize: '0.7rem',
                }}>
                  <span className={`badge badge-${log.status || 'pending'}`} style={{ fontSize: '0.55rem', padding: '1px 5px' }}>
                    {log.status || 'info'}
                  </span>
                  <span style={{ color: getAgent(log.agentName).color, fontWeight: 600, fontSize: '0.65rem', minWidth: '70px' }}>
                    {getAgent(log.agentName).label}
                  </span>
                  <span style={{ flex: 1, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {log.decision}: {log.reason?.substring(0, 80)}
                  </span>
                  <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', flexShrink: 0 }}>
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
