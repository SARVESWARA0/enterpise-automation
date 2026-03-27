"use client";

interface AgentState {
  active: boolean;
  action: string;
}

const AGENTS: { id: string; emoji: string; name: string; color: string; role: string }[] = [
  { id: "interpreter",  emoji: "🧠", name: "Interpreter",  color: "var(--interpreter)",  role: "Planner" },
  { id: "execution",    emoji: "⚡", name: "Execution",    color: "var(--execution)",    role: "Operator" },
  { id: "verification", emoji: "✅", name: "Verification", color: "var(--verification)", role: "Auditor" },
  { id: "recovery",     emoji: "🔧", name: "Recovery",     color: "var(--recovery)",     role: "Resilience" },
];

export default function AgentRoster({ agents }: { agents: Record<string, AgentState> }) {
  return (
    <>
      <div className="panel-header">
        <span>🤖</span> Agent Roster
      </div>
      <div className="panel-body">
        {AGENTS.map((a) => {
          const state = agents[a.id] || { active: false, action: "Idle" };
          return (
            <div key={a.id} className={`agent-card ${state.active ? "active" : "inactive"}`}>
              <div className="agent-card-header">
                <span className="agent-card-emoji">{a.emoji}</span>
                <span className="agent-card-name" style={{ color: state.active ? a.color : "var(--text-muted)" }}>
                  {a.name}
                </span>
                <span style={{ marginLeft: "auto" }}>
                  {state.active ? (
                    <span className="pulse-dot" style={{ background: a.color }} />
                  ) : (
                    <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>IDLE</span>
                  )}
                </span>
              </div>
              <div className="agent-card-ticker">
                {state.active ? state.action : a.role}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
