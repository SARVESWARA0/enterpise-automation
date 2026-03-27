"use client";

import { useEffect, useRef } from "react";

interface StreamEvent {
  event_type: string;
  agent: string;
  step_id?: string;
  data: any;
  timestamp: string;
}

const AGENT_META: Record<string, { color: string; label: string }> = {
  interpreter:  { color: "var(--interpreter)", label: "Interpreter" },
  execution:    { color: "var(--execution)", label: "Execution" },
  verification: { color: "var(--verification)", label: "Verification" },
  recovery:     { color: "var(--recovery)", label: "Recovery" },
  orchestrator: { color: "var(--orchestrator)", label: "Orchestrator" },
  system:       { color: "var(--text-muted)", label: "System" },
};

function timeStr(ts: string) {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch { return ""; }
}

export default function AgentStream({ events }: { events: StreamEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  const visible = events.filter((e) =>
    ["agent_message", "tool_call", "tool_result", "recovery", "step_start",
     "step_complete", "step_failed", "token_stream", "agent_tool_start"].includes(e.event_type)
  );

  return (
    <>
      <div className="panel-header">
        <span></span> Agent Stream
        <span className="count">{visible.length}</span>
      </div>
      <div className="panel-body">
        {visible.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)", fontSize: "0.8rem" }}>
            <div className="spinner" style={{ margin: "0 auto 12px" }} />
            Waiting for agent activity...
          </div>
        )}
        {visible.map((e, i) => renderEvent(e, i))}
        <div ref={bottomRef} />
      </div>
    </>
  );
}

function renderEvent(event: StreamEvent, idx: number) {
  const meta = AGENT_META[event.agent] || AGENT_META.system;
  const { event_type, data, timestamp } = event;

  // ── Tool Call Card ──
  if (event_type === "tool_call") {
    return (
      <div key={idx} className="stream-card tool-call">
        <div className="stream-card-header">
          <span>{meta.label} → <strong>{data?.tool}</strong></span>
          <span style={{ fontSize: "0.6rem", color: "var(--text-muted)" }}>{timeStr(timestamp)}</span>
        </div>
        <div className="stream-card-body">
          {data?.parameters && Object.entries(data.parameters).map(([k, v]) => (
            <div key={k} className="param-row">
              <span className="param-key">{k}</span>
              <span className="param-arrow">→</span>
              <span className="param-value">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
            </div>
          ))}
          {data?.attempt && data.attempt > 1 && (
            <div style={{ marginTop: 6, fontSize: "0.65rem", color: "var(--warning)" }}>
              Retry attempt #{data.attempt}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Tool Result Card ──
  if (event_type === "tool_result") {
    const isSuccess = data?.status === "SUCCESS";
    return (
      <div key={idx} className={`stream-card ${isSuccess ? "tool-result-success" : "tool-result-failure"}`}>
        <div className="stream-card-header">
          <span>{isSuccess ? "[SUCCESS]" : "[FAILURE]"} {data?.tool_called || "Result"}</span>
          <span className={`badge badge-${isSuccess ? "completed" : "failed"}`}>{data?.status}</span>
        </div>
        <div className="stream-card-body">
          {data?.output && (
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.7rem", color: "var(--text-secondary)", margin: 0 }}>
              {typeof data.output === "object" ? JSON.stringify(data.output, null, 2) : String(data.output).slice(0, 500)}
            </pre>
          )}
          {data?.error && (
            <div style={{ color: "var(--danger)", marginTop: 4, fontSize: "0.7rem" }}>
              Error: {data.error}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Recovery Card ──
  if (event_type === "recovery") {
    return (
      <div key={idx} className="stream-card recovery-card">
        <div className="stream-card-header">
          <span>🔧 Recovery Agent</span>
          {data?.action && <span className="badge badge-escalated">{data.action}</span>}
        </div>
        <div className="stream-card-body">
          {data?.message && <div>{data.message}</div>}
          {data?.reason && <div style={{ marginTop: 4, color: "var(--text-muted)" }}>Reason: {data.reason}</div>}
          {data?.audit_message && (
            <div style={{ marginTop: 4, fontSize: "0.65rem", color: "var(--warning)" }}>
              📝 {data.audit_message}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Step Start/Complete/Failed ──
  if (event_type === "step_start" || event_type === "step_complete" || event_type === "step_failed") {
    const icon = event_type === "step_start" ? "▶" : event_type === "step_complete" ? "✓" : "✕";
    const color = event_type === "step_start" ? "var(--info)" : event_type === "step_complete" ? "var(--success)" : "var(--danger)";
    return (
      <div key={idx} className="agent-bubble slide-in">
        <div className="agent-avatar" style={{ borderColor: color, color }}>
          {icon}
        </div>
        <div className="agent-bubble-content">
          <div className="agent-bubble-name" style={{ color }}>
            Step {data?.step_id}: {data?.name || data?.status || event_type}
            <span className="time">{timeStr(timestamp)}</span>
          </div>
          {data?.reason && (
            <div className="agent-bubble-text" style={{ fontSize: "0.75rem" }}>
              {data.reason}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Agent Message (chat bubble) ──
  if (event_type === "agent_message") {
    return (
      <div key={idx} className="agent-bubble slide-in">
        <div className="agent-avatar" style={{ borderColor: meta.color, color: meta.color }}>
          {meta.label.charAt(0)}
        </div>
        <div className="agent-bubble-content">
          <div className="agent-bubble-name" style={{ color: meta.color }}>
            {meta.label}
            <span className="time">{timeStr(timestamp)}</span>
          </div>
          <div className="agent-bubble-text">
            {data?.message || data?.verdict || JSON.stringify(data)}
            {data?.confidence !== undefined && (
              <span style={{ marginLeft: 8, fontSize: "0.7rem", color: "var(--text-muted)" }}>
                ({Math.round(data.confidence * 100)}% confidence)
              </span>
            )}
          </div>
        </div>
      </div>
    );
  }

  return null;
}
