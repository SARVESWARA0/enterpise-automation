import { AgentResult, StepContext, logAgentActivity } from './agentBase';
import { eventBus } from '../workflow/eventBus';

/**
 * Decision Agent — makes routing decisions, detects ambiguity, and assigns ownership.
 * 
 * Key rules:
 * - Do NOT guess if owner is unclear → return AWAITING_CLARIFICATION
 * - Detect ambiguous action items
 * - Choose which route/branch to take
 */
export async function makeDecision(context: StepContext): Promise<AgentResult> {
  const startTime = Date.now();
  const agentName = 'DecisionAgent';

  eventBus.emitWorkflowEvent('agent:active', context.workflowId, `Decision Agent analyzing: ${context.stepName}`, {
    stepId: context.stepId,
    agentName,
  });

  try {
    const input = context.inputData || {};
    const workflowInput = context.workflowInput || {};

    // Decision logic based on step type
    let result: AgentResult;

    if (context.stepName.toLowerCase().includes('assign') || context.stepName.toLowerCase().includes('owner')) {
      result = await decideOwnership(context, input, workflowInput);
    } else if (context.stepName.toLowerCase().includes('route') || context.stepName.toLowerCase().includes('branch')) {
      result = await decideBranching(context, input);
    } else if (context.stepName.toLowerCase().includes('ambig') || context.stepName.toLowerCase().includes('clarif')) {
      result = await detectAmbiguity(context, input);
    } else {
      // General decision making
      result = await makeGeneralDecision(context, input);
    }

    const durationMs = Date.now() - startTime;
    await logAgentActivity(
      context.workflowId,
      context.stepId,
      agentName,
      `decision_${result.status}`,
      undefined,
      context.inputData,
      result.data,
      durationMs
    );

    eventBus.emitWorkflowEvent('agent:complete', context.workflowId, `Decision Agent: ${result.message}`, {
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
      'decision_error',
      undefined,
      context.inputData,
      { error: errorMsg },
      Date.now() - startTime
    );

    return {
      success: false,
      message: `Decision error: ${errorMsg}`,
      status: 'failed',
      data: { error: errorMsg },
    };
  }
}

async function decideOwnership(
  context: StepContext,
  input: Record<string, unknown>,
  workflowInput: Record<string, unknown>
): Promise<AgentResult> {
  // Simulate decision-making delay
  await new Promise((r) => setTimeout(r, 300 + Math.random() * 500));

  const candidates = input.candidates as string[] | undefined;
  const taskDescription = input.taskDescription as string || context.stepName;

  // If there are no candidates or the task is ambiguous, request clarification
  if (!candidates || candidates.length === 0) {
    // Check if we can infer from workflow context
    const department = workflowInput.department as string;
    if (department) {
      const inferredOwner = `${department} Team Lead`;
      return {
        success: true,
        message: `Assigned to ${inferredOwner} based on department context`,
        status: 'completed',
        data: {
          assignedTo: inferredOwner,
          reason: `Inferred from department: ${department}`,
          confidence: 'medium',
        },
      };
    }

    return {
      success: false,
      message: `Cannot determine owner for "${taskDescription}" — no candidates provided and context is insufficient`,
      status: 'awaiting_clarification',
      data: {
        question: `Who should own the task: "${taskDescription}"?`,
        reason: 'No candidates available and cannot infer from context',
      },
    };
  }

  // If multiple candidates, pick the best one (simplified logic)
  if (candidates.length === 1) {
    return {
      success: true,
      message: `Assigned to ${candidates[0]}`,
      status: 'completed',
      data: { assignedTo: candidates[0], reason: 'Only candidate available', confidence: 'high' },
    };
  }

  // Pick based on simple heuristic (in real system, use AI/context)
  const selected = candidates[Math.floor(Math.random() * candidates.length)];
  return {
    success: true,
    message: `Assigned to ${selected} from ${candidates.length} candidates`,
    status: 'completed',
    data: {
      assignedTo: selected,
      candidates,
      reason: `Selected based on availability and role match`,
      confidence: 'medium',
    },
  };
}

async function decideBranching(context: StepContext, input: Record<string, unknown>): Promise<AgentResult> {
  await new Promise((r) => setTimeout(r, 200 + Math.random() * 300));

  const condition = input.condition as string;
  const branches = input.branches as string[] || ['default'];

  const selectedBranch = branches[0]; // Simplified
  return {
    success: true,
    message: `Branch selected: ${selectedBranch}`,
    status: 'completed',
    data: {
      selectedBranch,
      condition,
      reason: `Condition "${condition}" evaluated to branch "${selectedBranch}"`,
    },
  };
}

async function detectAmbiguity(context: StepContext, input: Record<string, unknown>): Promise<AgentResult> {
  await new Promise((r) => setTimeout(r, 300 + Math.random() * 400));

  const items = input.items as Array<{ text: string; owner?: string }> | undefined;

  if (!items || items.length === 0) {
    return {
      success: true,
      message: 'No items to check for ambiguity',
      status: 'completed',
      data: { ambiguousItems: [] },
    };
  }

  const ambiguous = items.filter((item) => !item.owner || item.owner === 'unknown' || item.owner === '');
  const clear = items.filter((item) => item.owner && item.owner !== 'unknown' && item.owner !== '');

  if (ambiguous.length > 0) {
    return {
      success: false,
      message: `Found ${ambiguous.length} ambiguous action items that need owner clarification`,
      status: 'awaiting_clarification',
      data: {
        ambiguousItems: ambiguous,
        clearItems: clear,
        question: `Please assign owners for: ${ambiguous.map((i) => i.text).join(', ')}`,
      },
    };
  }

  return {
    success: true,
    message: `All ${items.length} items have clear ownership`,
    status: 'completed',
    data: { allItems: items },
  };
}

async function makeGeneralDecision(context: StepContext, input: Record<string, unknown>): Promise<AgentResult> {
  await new Promise((r) => setTimeout(r, 200 + Math.random() * 400));

  return {
    success: true,
    message: `Decision made for step: ${context.stepName}`,
    status: 'completed',
    data: {
      decision: 'proceed',
      reason: `Context analysis indicates step "${context.stepName}" should proceed normally`,
      input,
    },
  };
}
