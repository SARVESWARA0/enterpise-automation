"use client";

interface Step {
  step_id: number;
  name: string;
  tool_name: string;
  status: string;
}

const STATUS_ICON: Record<string, string> = {
  PENDING: "P",
  RUNNING: "R",
  COMPLETED: "C",
  FAILED: "F",
  ESCALATED: "E",
  SKIPPED: "-",
  RETRIED: "Re",
};

export default function ExecutionPlan({ steps }: { steps: Step[] }) {
  return (
    <>
      <div className="panel-header">
        <span></span> Execution Plan
        <span className="count">{steps.length} steps</span>
      </div>
      <div className="panel-body">
        {steps.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)", fontSize: "0.75rem" }}>
            <div className="spinner" style={{ margin: "0 auto 12px" }} />
            Generating plan...
          </div>
        )}
        {steps.map((s) => (
          <div
            key={s.step_id}
            className={`step-row ${s.status.toLowerCase()}`}
          >
            <span className="step-icon">
              {s.status === "RUNNING" ? (
                <span className="pulse-dot" style={{ background: "var(--info)" }} />
              ) : (
                STATUS_ICON[s.status] || "P"
              )}
            </span>
            <span className="step-name" title={`${s.tool_name}: ${s.name}`}>
              {s.name}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}
