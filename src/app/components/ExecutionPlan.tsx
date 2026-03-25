'use client';

interface PlanStep {
  step_id: number;
  name: string;
  tool_name: string;
  status?: string;
}

const STATUS_ICONS: Record<string, string> = {
  PENDING: '○',
  RUNNING: '◉',
  COMPLETED: '✓',
  FAILED: '✕',
  ESCALATED: '⚡',
  SKIPPED: '–',
};

export default function ExecutionPlan({
  steps,
  activeStepId,
  onStepClick,
}: {
  steps: PlanStep[];
  activeStepId?: number | null;
  onStepClick?: (stepId: number) => void;
}) {
  const completedCount = steps.filter(s => s.status === 'COMPLETED').length;
  const progress = steps.length > 0 ? (completedCount / steps.length) * 100 : 0;

  return (
    <div className="panel plan-panel">
      <div className="panel-header">
        <span>Execution Plan</span>
        <span className="count">{completedCount} / {steps.length}</span>
      </div>

      {/* Progress Bar */}
      <div style={{ padding: '0 12px', marginTop: '8px' }}>
        <div className="progress-bar-bg">
          <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div className="panel-body" style={{ paddingTop: '8px' }}>
        {steps.length === 0 ? (
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', padding: '12px 0' }}>
            Generating plan...
          </div>
        ) : (
          steps.map((step) => {
            const status = step.status || 'PENDING';
            const icon = STATUS_ICONS[status] || '○';
            const isActive = step.step_id === activeStepId;
            const statusClass = status.toLowerCase();

            return (
              <div
                key={step.step_id}
                className={`step-row ${statusClass} ${isActive ? 'active' : ''}`}
                onClick={() => onStepClick?.(step.step_id)}
              >
                <span className="step-icon" style={{
                  color: status === 'RUNNING' ? 'var(--info)' :
                         status === 'COMPLETED' ? 'var(--success)' :
                         status === 'FAILED' ? 'var(--danger)' :
                         status === 'ESCALATED' ? 'var(--recovery)' : 'var(--text-muted)',
                }}>
                  {status === 'RUNNING' ? (
                    <span className="pulse-dot" style={{ background: 'var(--info)' }} />
                  ) : icon}
                </span>
                <span className="step-name">{step.step_id}. {step.name}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
