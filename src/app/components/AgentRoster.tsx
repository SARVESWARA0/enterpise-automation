'use client';

const AGENTS = [
  { id: 'interpreter',  emoji: '🧠', label: 'Interpreter',  color: 'var(--interpreter)' },
  { id: 'execution',    emoji: '⚡', label: 'Execution',    color: 'var(--execution)' },
  { id: 'verification', emoji: '🔍', label: 'Verification', color: 'var(--verification)' },
  { id: 'recovery',     emoji: '🚑', label: 'Recovery',     color: 'var(--recovery)' },
];

interface StreamEvent {
  event_type: string;
  agent: string;
  data: any;
  timestamp: string;
}

export default function AgentRoster({ events }: { events: StreamEvent[] }) {
  // Compute last activity per agent
  const agentActivity = new Map<string, { message: string; active: boolean }>();

  // Mark all as standby first
  AGENTS.forEach(a => agentActivity.set(a.id, { message: '', active: false }));

  // Find latest event from each agent
  const recentSlice = events.slice(-40);
  recentSlice.forEach(evt => {
    if (evt.agent && agentActivity.has(evt.agent)) {
      const msg = evt.data?.message || evt.data?.verdict || evt.data?.action || evt.event_type;
      agentActivity.set(evt.agent, { message: String(msg).substring(0, 60), active: true });
    }
  });

  // Determine currently active agent (from last event)
  const lastEvent = events.length > 0 ? events[events.length - 1] : null;
  const currentAgent = lastEvent?.agent || '';
  const isWorkflowDone = lastEvent?.event_type === 'workflow_complete';

  return (
    <div className="panel roster-panel">
      <div className="panel-header">
        <span>Agent Roster</span>
      </div>
      <div className="panel-body">
        {AGENTS.map(agent => {
          const info = agentActivity.get(agent.id);
          const isCurrentlyActive = !isWorkflowDone && currentAgent === agent.id;
          const hasBeenActive = info?.active || false;

          return (
            <div
              key={agent.id}
              className={`agent-card ${isCurrentlyActive ? 'active' : hasBeenActive ? '' : 'inactive'}`}
              style={isCurrentlyActive ? { borderColor: agent.color + '60', background: agent.color + '08' } : undefined}
            >
              <div className="agent-card-header">
                <span className="agent-card-emoji">{agent.emoji}</span>
                <span className="agent-card-name" style={{ color: isCurrentlyActive ? agent.color : hasBeenActive ? 'var(--text-secondary)' : 'var(--text-muted)' }}>
                  {agent.label}
                </span>
                {isCurrentlyActive ? (
                  <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span className="pulse-dot" style={{ background: agent.color }} />
                    <span style={{ fontSize: '0.6rem', fontWeight: 600, color: agent.color, fontFamily: 'var(--font-mono)' }}>ACTIVE</span>
                  </span>
                ) : (
                  <span style={{ marginLeft: 'auto', fontSize: '0.58rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {hasBeenActive ? '● DONE' : '● STANDBY'}
                  </span>
                )}
              </div>
              {hasBeenActive && info?.message && (
                <div className="agent-card-ticker">{info.message}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
