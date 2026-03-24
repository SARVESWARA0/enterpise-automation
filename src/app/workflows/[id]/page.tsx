'use client';

import { useEffect, useState, useRef, use } from 'react';

interface Step { id?: string; stepName: string; stepDescription?: string; toolName?: string; status: string; assignedAgent: string; retryCount: number; dependencyOrder: number; }
interface StreamEvent { type: string; workflowId: string; stepId?: string; agentName?: string; message: string; data?: any; timestamp?: string; }
interface Workflow { id: string; type: string; status: string; plan?: Step[]; steps: Step[]; }

export default function WorkflowChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const chatRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Fetch workflow data
  useEffect(() => {
    const fetchWorkflow = () => fetch(`/api/workflows/${id}`).then(r => r.json()).then(d => { setWorkflow(d); setLoading(false); });
    fetchWorkflow();
    const i = setInterval(fetchWorkflow, 3000);
    return () => clearInterval(i);
  }, [id]);

  // SSE stream
  useEffect(() => {
    const es = new EventSource(`/api/workflows/${id}/stream`);
    eventSourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const event: StreamEvent = JSON.parse(e.data);
        setEvents(prev => [...prev, event]);
      } catch {}
    };

    es.onerror = () => { es.close(); };
    return () => { es.close(); };
  }, [id]);

  // Auto-scroll stream
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [events]);

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '100px' }}><div className="spinner" /></div>;
  if (!workflow) return <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Workflow not found</div>;

  const getAgentColor = (agent?: string) => {
    if (agent === 'PlannerAgent') return 'var(--purple)';
    if (agent === 'ExecutionAgent') return 'var(--info)';
    if (agent === 'VerificationAgent') return 'var(--success)';
    if (agent === 'RecoveryAgent') return 'var(--warning)';
    if (agent === 'Orchestrator') return 'var(--accent)';
    if (agent === 'Graph') return 'var(--text-muted)';
    return 'var(--text-muted)';
  };

  const getAgentAvatar = (agent?: string) => {
    if (agent === 'PlannerAgent') return '🧠';
    if (agent === 'ExecutionAgent') return '⚡';
    if (agent === 'VerificationAgent') return '✅';
    if (agent === 'RecoveryAgent') return '🚑';
    if (agent === 'Orchestrator') return '🎯';
    if (agent === 'Graph') return '📊';
    return '🤖';
  };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header" style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">Autopilot Chat</h1>
          <p className="page-subtitle">Monitoring dynamic execution</p>
        </div>
        <span className={`badge badge-${(workflow.status || 'pending').toLowerCase()}`} style={{ fontSize: '1rem', padding: '8px 16px' }}>
          {workflow.status === 'RUNNING' && <span className="pulse-dot" style={{ background: 'var(--info)', width: '10px', height: '10px' }} />}
          {workflow.status || 'LOADING'}
        </span>
      </div>

      <div className="glass-card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0 }}>
        {/* Chat Feed */}
        <div ref={chatRef} style={{ flex: 1, overflowY: 'auto', padding: '30px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* User Prompt Message */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '20px' }}>
            <div style={{
              background: 'var(--accent)',
              color: 'white',
              padding: '16px 24px',
              borderRadius: '24px 24px 4px 24px',
              maxWidth: '80%',
              fontSize: '1.1rem',
              boxShadow: '0 4px 15px rgba(99, 102, 241, 0.3)'
            }}>
              {workflow.type}
            </div>
          </div>

          {events.length === 0 && workflow.status === 'RUNNING' && (
             <div style={{ display: 'flex', gap: '15px' }}>
             <div style={{ fontSize: '1.5rem' }}>🤖</div>
             <div style={{ background: 'var(--surface-50)', padding: '16px 20px', borderRadius: '4px 24px 24px 24px', color: 'var(--text-muted)' }}>
               Thinking...
             </div>
           </div>
          )}

          {events.filter(e => 
            e.type.startsWith('chat:') || 
            e.type.startsWith('agent:') || 
            e.type === 'workflow:start' || 
            e.type === 'workflow:complete' || 
            e.type === 'workflow:failed'
          ).map((evt, i) => {
            const isPlanner = evt.type === 'chat:planning_started' || evt.type === 'chat:plan_generated';
            const isError = evt.type === 'chat:error' || evt.type === 'workflow:failed';
            const isSuccess = evt.type === 'chat:step_complete' || evt.type === 'workflow:complete';
            const isSystem = evt.type === 'workflow:start' || evt.type === 'workflow:complete' || evt.type === 'workflow:failed';
            const agent = isSystem ? 'Orchestrator' : (isPlanner ? 'PlannerAgent' : evt.agentName || 'System');
            
            return (
              <div key={i} style={{ display: 'flex', gap: '15px', maxWidth: '85%' }}>
                <div style={{ 
                  width: '40px', height: '40px', borderRadius: '50%', 
                  background: 'var(--surface-100)', display: 'flex', 
                  alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem',
                  border: `2px solid ${getAgentColor(agent)}`,
                  flexShrink: 0
                }}>
                  {getAgentAvatar(agent)}
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: getAgentColor(agent) }}>
                    {agent} <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.7rem', marginLeft: '8px' }}>{evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}</span>
                  </div>
                  
                  <div style={{ 
                    background: isError ? 'rgba(239, 68, 68, 0.1)' : 'var(--surface-50)', 
                    border: isError ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid var(--border)',
                    padding: '16px 20px', 
                    borderRadius: '4px 24px 24px 24px',
                    color: isError ? 'var(--danger)' : 'var(--text-primary)',
                    fontSize: '0.95rem',
                    lineHeight: '1.5'
                  }}>
                    {evt.message}

                    {/* Render Plan JSON nicely */}
                    {evt.type === 'chat:plan_generated' && evt.data?.steps && (
                      <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {evt.data.steps.map((s: Step, j: number) => (
                          <div key={j} style={{ background: 'var(--surface-100)', padding: '12px', borderRadius: '8px', borderLeft: '3px solid var(--info)' }}>
                            <div style={{ fontWeight: 600, marginBottom: '4px' }}>{j+1}. {s.stepName}</div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{s.stepDescription || s.toolName}</div>
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
    </div>
  );
}
