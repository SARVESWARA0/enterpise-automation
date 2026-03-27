"use client";

interface StreamEvent {
  event_type: string;
  agent: string;
  step_id?: string;
  data: any;
  timestamp: string;
}

function timeStr(ts: string) {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch { return ""; }
}

const AGENT_COLORS: Record<string, string> = {
  interpreter: "var(--interpreter)",
  execution: "var(--execution)",
  verification: "var(--verification)",
  recovery: "var(--recovery)",
  orchestrator: "var(--orchestrator)",
  system: "var(--text-muted)",
};

export default function AuditTrail({ events }: { events: StreamEvent[] }) {
  const auditable = events.filter((e) =>
    ["tool_call", "tool_result", "recovery", "step_complete", "step_failed", "step_start"].includes(e.event_type)
  );

  return (
    <>
      <div className="panel-header">
        <span></span> Audit Trail
        <span className="count">{auditable.length}</span>
      </div>
      <div className="panel-body">
        {auditable.length === 0 && (
          <div style={{ textAlign: "center", padding: 16, color: "var(--text-muted)", fontSize: "0.7rem" }}>
            No audit events yet
          </div>
        )}
        {auditable.map((e, i) => (
          <div key={i} className="audit-row slide-in">
            <span className="audit-time">{timeStr(e.timestamp)}</span>
            <span className="audit-agent" style={{ color: AGENT_COLORS[e.agent] || "var(--text-secondary)" }}>
              {e.agent}
            </span>
            <span className="audit-action">
              {e.event_type === "tool_call" && `→ ${e.data?.tool}`}
              {e.event_type === "tool_result" && `[${e.data?.status === "SUCCESS" ? "PASS" : "FAIL"}] ${e.data?.tool_called}`}
              {e.event_type === "recovery" && `[RECOVERY] ${e.data?.action || "recovering"}`}
              {e.event_type === "step_start" && `[START] ${e.data?.name || e.data?.step_id}`}
              {e.event_type === "step_complete" && `[DONE] ${e.data?.name || e.data?.step_id}`}
              {e.event_type === "step_failed" && `[FAIL] ${e.data?.status || "FAILED"}`}
            </span>
            <span className="audit-outcome">
              {e.step_id && <span style={{ color: "var(--text-muted)" }}>#{e.step_id}</span>}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}
