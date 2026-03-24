import { AgentResult, StepContext, logAgentActivity } from './agentBase';
import { eventBus } from '../workflow/eventBus';

/**
 * Recovery Agent — handles failures through retry, reroute, or escalation.
 * 
 * Recovery strategy:
 * 1. If retryable and under max retries → RETRY
 * 2. If retryable but max retries exceeded → ESCALATE
 * 3. If not retryable → ESCALATE immediately
 * 4. If fallback behavior is defined → attempt fallback
 */
export async function recoverStep(
  context: StepContext, 
  failureResult: AgentResult
): Promise<AgentResult> {
  const startTime = Date.now();
  const agentName = 'RecoveryAgent';

  eventBus.emitWorkflowEvent('recovery:start', context.workflowId, `Recovery Agent handling failure: ${context.stepName}`, {
    stepId: context.stepId,
    agentName,
    data: { failure: failureResult.message, retryCount: context.retryCount },
  });

  try {
    await new Promise((r) => setTimeout(r, 200 + Math.random() * 300));

    const isRetryable = failureResult.toolOutput?.retryable !== false && 
                        failureResult.data?.retryable !== false;
    const canRetry = context.retryCount < context.maxRetries;

    let result: AgentResult;

    if (isRetryable && canRetry) {
      // Strategy: RETRY
      result = {
        success: true,
        message: `Recovery: will retry step "${context.stepName}" (attempt ${context.retryCount + 1}/${context.maxRetries})`,
        status: 'retried',
        data: {
          strategy: 'retry',
          retryCount: context.retryCount + 1,
          reason: `Error is retryable, attempt ${context.retryCount + 1} of ${context.maxRetries}`,
          originalError: failureResult.message,
        },
      };
    } else if (context.fallbackBehavior) {
      // Strategy: FALLBACK
      result = await attemptFallback(context, failureResult);
    } else {
      // Strategy: ESCALATE
      const escalationTarget = determineEscalationTarget(context);
      result = {
        success: false,
        message: `Recovery: escalating step "${context.stepName}" to ${escalationTarget}`,
        status: 'escalated',
        data: {
          strategy: 'escalate',
          escalatedTo: escalationTarget,
          reason: isRetryable 
            ? `Max retries (${context.maxRetries}) exceeded` 
            : `Error is not retryable: ${failureResult.toolOutput?.errorCode || 'unknown'}`,
          originalError: failureResult.message,
          retryCount: context.retryCount,
        },
      };
    }

    const durationMs = Date.now() - startTime;
    await logAgentActivity(
      context.workflowId,
      context.stepId,
      agentName,
      `recovery_${result.data?.strategy || 'unknown'}`,
      context.toolName,
      { failure: failureResult.message },
      result.data,
      durationMs
    );

    eventBus.emitWorkflowEvent('recovery:complete', context.workflowId, result.message, {
      stepId: context.stepId,
      agentName,
      data: result.data,
    });

    return result;
  } catch (error) {
    const errorMsg = (error as Error).message;
    await logAgentActivity(
      context.workflowId,
      context.stepId,
      agentName,
      'recovery_error',
      context.toolName,
      undefined,
      { error: errorMsg },
      Date.now() - startTime
    );

    return {
      success: false,
      message: `Recovery failed: ${errorMsg}`,
      status: 'escalated',
      data: { strategy: 'escalate', reason: `Recovery agent error: ${errorMsg}` },
    };
  }
}

async function attemptFallback(context: StepContext, failureResult: AgentResult): Promise<AgentResult> {
  await new Promise((r) => setTimeout(r, 300));

  // Parse fallback behavior
  const fallback = context.fallbackBehavior || '';
  
  if (fallback.includes('skip')) {
    return {
      success: true,
      message: `Recovery: skipping step "${context.stepName}" per fallback policy`,
      status: 'completed',
      data: {
        strategy: 'fallback_skip',
        reason: `Fallback policy: skip on failure`,
        originalError: failureResult.message,
      },
    };
  }

  if (fallback.includes('delegate')) {
    return {
      success: true,
      message: `Recovery: delegating step "${context.stepName}" to alternate handler`,
      status: 'completed',
      data: {
        strategy: 'fallback_delegate',
        reason: `Fallback policy: delegate to alternate handler`,
        delegatedTo: 'Alternate Handler',
        originalError: failureResult.message,
      },
    };
  }

  // Default fallback: escalate
  return {
    success: false,
    message: `Recovery: no viable fallback for "${context.stepName}", escalating`,
    status: 'escalated',
    data: {
      strategy: 'escalate',
      reason: `Fallback "${fallback}" could not resolve the issue`,
      originalError: failureResult.message,
    },
  };
}

function determineEscalationTarget(context: StepContext): string {
  const toolName = context.toolName || '';
  
  if (toolName.includes('email')) return 'IT Support Team';
  if (toolName.includes('task') || toolName.includes('jira')) return 'IT Support Team';
  if (toolName.includes('calendar')) return 'Admin Team';
  if (toolName.includes('sla')) return 'Management';
  if (toolName.includes('employee')) return 'HR Team';
  
  return 'Operations Team';
}
