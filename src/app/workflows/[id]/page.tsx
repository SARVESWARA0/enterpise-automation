"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { useParams } from "next/navigation";
import ExecutionPlan from "../../components/ExecutionPlan";
import AgentStream from "../../components/AgentStream";
import AgentRoster from "../../components/AgentRoster";
import AuditTrail from "../../components/AuditTrail";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface StreamEvent {
  event_type: string;
  agent: string;
  step_id?: string;
  data: any;
  timestamp: string;
}

interface Step {
  step_id: number;
  name: string;
  tool_name: string;
  status: string;
}

interface AgentState {
  active: boolean;
  action: string;
}

interface DashState {
  status: string;
  steps: Step[];
  events: StreamEvent[];
  agents: Record<string, AgentState>;
  summary: any;
}

type DashAction =
  | StreamEvent
  | {
      type: "hydrate";
      payload: DashState;
    };

const INITIAL: DashState = {
  status: "CONNECTING",
  steps: [],
  events: [],
  agents: {
    interpreter: { active: false, action: "Idle" },
    execution: { active: false, action: "Idle" },
    verification: { active: false, action: "Idle" },
    recovery: { active: false, action: "Idle" },
  },
  summary: null,
};

function reducer(state: DashState, action: DashAction): DashState {
  if ("type" in action && action.type === "hydrate") {
    return action.payload;
  }

  const event = action as StreamEvent;
  const next = { ...state, events: [...state.events, event] };

  switch (event.event_type) {
    case "plan":
      next.status = "RUNNING";
      next.steps = (event.data?.steps || []).map((s: any) => ({
        step_id: s.step_id,
        name: s.name,
        tool_name: s.tool_name,
        status: "PENDING",
      }));
      break;

    case "step_start":
      next.status = "RUNNING";
      next.steps = next.steps.map((s) =>
        s.step_id === event.data?.step_id ? { ...s, status: "RUNNING" } : s
      );
      break;

    case "step_complete":
      next.steps = next.steps.map((s) =>
        s.step_id === event.data?.step_id
          ? { ...s, status: event.data?.status || "COMPLETED" }
          : s
      );
      break;

    case "step_failed":
      next.steps = next.steps.map((s) =>
        s.step_id === event.data?.step_id
          ? { ...s, status: event.data?.status || "FAILED" }
          : s
      );
      break;

    case "agent_active":
      next.agents = {
        ...next.agents,
        [event.agent]: {
          active: event.data?.active ?? false,
          action: event.data?.action || "Idle",
        },
      };
      break;

    case "workflow_complete":
      next.status = event.data?.status || "COMPLETED";
      next.summary = event.data;
      break;
  }

  return next;
}

export default function WorkflowDashboard() {
  const params = useParams();
  const workflowId = params.id as string;
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!workflowId) return;

    let isActive = true;
    eventSourceRef.current?.close();

    const init = async () => {
      try {
        const wfRes = await fetch(`${API}/api/workflows/${workflowId}`);
        if (!wfRes.ok) throw new Error("Workflow fetch failed");
        const wf = await wfRes.json();

        // Always try to hydrate from saved events first
        const eventsRes = await fetch(`${API}/api/workflows/${workflowId}/events`);
        const eventsPayload = eventsRes.ok ? await eventsRes.json() : { events: [] };
        const historicalEvents: StreamEvent[] = Array.isArray(eventsPayload?.events)
          ? eventsPayload.events
          : [];

        let hydrated = INITIAL;
        for (const event of historicalEvents) {
          if (!event?.event_type || event.event_type === "heartbeat") continue;
          hydrated = reducer(hydrated, event);
        }

        const terminalStatuses = ["COMPLETED", "FAILED", "ESCALATED"];

        if (terminalStatuses.includes(wf.status)) {
          // Workflow is finished — just show the hydrated state
          if (!terminalStatuses.includes(hydrated.status)) {
            hydrated = {
              ...hydrated,
              status: wf.status,
              summary: hydrated.summary ?? {
                status: wf.status,
                summary: "Loaded saved workflow execution.",
              },
            };
          }
          if (isActive) dispatch({ type: "hydrate", payload: hydrated });
          return;
        }

        // Workflow is still running (or pending/scheduled) — hydrate existing events,
        // then connect SSE to receive new events on top
        if (hydrated.events.length > 0) {
          hydrated.status = "RUNNING";
        } else {
          hydrated.status = wf.status === "SCHEDULED" ? "SCHEDULED" : "CONNECTING";
        }
        if (isActive) dispatch({ type: "hydrate", payload: hydrated });

        const es = new EventSource(`${API}/api/workflows/${workflowId}/stream`);
        eventSourceRef.current = es;

        es.onmessage = (e) => {
          try {
            const event: StreamEvent = JSON.parse(e.data);
            if (event.event_type === "heartbeat") return;
            dispatch(event);
            if (event.event_type === "workflow_complete") {
              es.close();
            }
          } catch (err) {
            console.error("SSE parse error:", err);
          }
        };

        es.onerror = () => {
          console.warn("SSE connection lost");
        };
      } catch (err) {
        console.error("Failed to initialize workflow view:", err);
      }
    };

    init();

    return () => {
      isActive = false;
      eventSourceRef.current?.close();
    };
  }, [workflowId]);

  const completedSteps = state.steps.filter((s) => s.status === "COMPLETED").length;
  const totalSteps = state.steps.length;
  const pct = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div className="dash-header">
        <div className="logo">
          <span className="accent">⚡</span> ET Autopilot
          <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: "0.7rem", marginLeft: 8 }}>
            v2 • Graph Orchestration
          </span>
        </div>
        <div className="meta">
          <span className={`badge badge-${state.status.toLowerCase()}`}>
            {state.status === "RUNNING" && <span className="pulse-dot" style={{ background: "var(--info)" }} />}
            {state.status}
          </span>
          {totalSteps > 0 && (
            <span>{completedSteps}/{totalSteps} steps</span>
          )}
          <a href="/" style={{ color: "var(--text-muted)", textDecoration: "none", fontSize: "0.75rem" }}>← Home</a>
        </div>
      </div>

      {/* Progress */}
      {totalSteps > 0 && (
        <div style={{ padding: "0 16px" }}>
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {/* 4-Panel Grid */}
      <div className="dashboard-grid">
        <div className="panel plan-panel">
          <ExecutionPlan steps={state.steps} />
        </div>
        <div className="panel stream-panel">
          <AgentStream events={state.events} />
        </div>
        <div className="panel roster-panel">
          <AgentRoster agents={state.agents} />
        </div>
        <div className="panel audit-panel">
          <AuditTrail events={state.events} />
        </div>
      </div>
    </div>
  );
}
