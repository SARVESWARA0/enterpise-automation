import prisma from '../db';
import { eventBus } from './eventBus';
import { executeStep } from '../agents/executionAgent';
import { makeDecision } from '../agents/decisionAgent';
import { verifyStep } from '../agents/verificationAgent';
import { recoverStep } from '../agents/recoveryAgent';
import { StepContext } from '../agents/agentBase';
import { AuditTool } from '../tools/auditTool';

const auditTool = new AuditTool();

/**
 * The Orchestrator is the brain of the system.
 * It reads the workflow plan, executes steps in order,
 * manages state, handles retries/escalation, and streams live updates.
 */
export async function executeWorkflow(workflowId: string): Promise<void> {
  // 1. Load workflow with steps
  const workflow = await prisma.workflow.findUnique({
    where: { id: workflowId },
    include: { steps: { orderBy: { dependencyOrder: 'asc' } } },
  });

  if (!workflow) {
    throw new Error(`Workflow not found: ${workflowId}`);
  }

  // 2. Mark workflow as RUNNING
  await prisma.workflow.update({
    where: { id: workflowId },
    data: { status: 'RUNNING' },
  });

  eventBus.emitWorkflowEvent('workflow:start', workflowId, `Workflow "${workflow.type}" started with ${workflow.steps.length} steps`);

  const workflowInput = (workflow.inputData as Record<string, unknown>) || {};
  const stepOutputs: Record<string, unknown>[] = [];
  let hasEscalation = false;

  // 3. Execute steps in dependency order
  for (const step of workflow.steps) {
    const context: StepContext = {
      workflowId,
      stepId: step.id,
      stepName: step.stepName,
      stepType: step.stepType,
      toolName: step.toolName || undefined,
      inputData: (step.inputData as Record<string, unknown>) || {},
      workflowInput,
      retryCount: step.retryCount,
      maxRetries: step.maxRetries,
      previousStepOutputs: stepOutputs,
    };

    // If a previous step had a fallback behavior result, check for it
    const fallbackBehavior = step.fallbackBehavior || undefined;
    if (fallbackBehavior) {
      context.inputData = { ...context.inputData };
    }

    // Mark step as RUNNING
    await prisma.step.update({
      where: { id: step.id },
      data: { status: 'RUNNING' },
    });

    eventBus.emitWorkflowEvent('step:start', workflowId, `Starting step: ${step.stepName}`, {
      stepId: step.id,
      agentName: step.assignedAgent || undefined,
      toolName: step.toolName || undefined,
    });

    // Audit: step start
    await auditTool.execute({
      workflowId,
      stepId: step.id,
      decision: 'step_started',
      reason: `Executing step "${step.stepName}" (order: ${step.dependencyOrder})`,
      actionTaken: `Dispatching to ${step.assignedAgent || 'agent'}`,
      agentName: step.assignedAgent,
      toolName: step.toolName,
      status: 'running',
    });

    // 4. Dispatch to the correct agent
    let result = await dispatchToAgent(context);

    // 5. Handle failures with recovery
    if (!result.success && result.status === 'failed') {
      let recovered = false;

      // Retry loop
      while (context.retryCount < context.maxRetries && !recovered) {
        context.retryCount++;

        // Update DB retry count
        await prisma.step.update({
          where: { id: step.id },
          data: { retryCount: context.retryCount, status: 'RETRIED' },
        });

        eventBus.emitWorkflowEvent('step:retry', workflowId, `Retrying step: ${step.stepName} (attempt ${context.retryCount}/${context.maxRetries})`, {
          stepId: step.id,
          data: { retryCount: context.retryCount },
        });

        // Audit: retry
        await auditTool.execute({
          workflowId,
          stepId: step.id,
          decision: 'retry',
          reason: `Previous attempt failed: ${result.message}`,
          actionTaken: `Retry attempt ${context.retryCount}`,
          agentName: step.assignedAgent,
          toolName: step.toolName,
          retryCount: context.retryCount,
          status: 'retrying',
        });

        // Retry execution
        result = await dispatchToAgent(context);

        if (result.success) {
          recovered = true;
        }
      }

      // If still failed after retries, invoke Recovery Agent
      if (!recovered) {
        const recoveryResult = await recoverStep(context, result);

        if (recoveryResult.status === 'retried') {
          // Recovery says retry one more time
          context.retryCount++;
          result = await dispatchToAgent(context);
        } else if (recoveryResult.status === 'escalated') {
          hasEscalation = true;

          await prisma.step.update({
            where: { id: step.id },
            data: {
              status: 'ESCALATED',
              currentOutput: recoveryResult.data as object || null,
            },
          });

          eventBus.emitWorkflowEvent('step:escalated', workflowId, `Step escalated: ${step.stepName}`, {
            stepId: step.id,
            data: recoveryResult.data,
          });

          // Audit: escalation
          await auditTool.execute({
            workflowId,
            stepId: step.id,
            decision: 'escalated',
            reason: recoveryResult.message,
            actionTaken: `Escalated to ${recoveryResult.data?.escalatedTo || 'management'}`,
            agentName: 'RecoveryAgent',
            toolName: step.toolName,
            retryCount: context.retryCount,
            status: 'escalated',
          });

          stepOutputs.push({ step: step.stepName, status: 'escalated', ...recoveryResult.data });
          continue; // Move to next step
        } else if (recoveryResult.success) {
          result = recoveryResult;
        }
      }
    }

    // 6. Handle awaiting clarification
    if (result.status === 'awaiting_clarification') {
      await prisma.step.update({
        where: { id: step.id },
        data: {
          status: 'AWAITING_CLARIFICATION',
          currentOutput: result.data as object || null,
        },
      });

      eventBus.emitWorkflowEvent('step:clarification', workflowId, `Step needs clarification: ${step.stepName}`, {
        stepId: step.id,
        data: result.data,
      });

      // Audit
      await auditTool.execute({
        workflowId,
        stepId: step.id,
        decision: 'awaiting_clarification',
        reason: result.message,
        actionTaken: 'Paused for clarification',
        agentName: step.assignedAgent,
        status: 'awaiting_clarification',
      });

      stepOutputs.push({ step: step.stepName, status: 'awaiting_clarification', ...result.data });
      continue; // Move to next step
    }

    // 7. Verification (for successful execution steps)
    if (result.success && step.stepType === 'execution') {
      const verificationResult = await verifyStep(context, result);

      if (!verificationResult.success) {
        // Verification failed — log but continue (non-blocking)
        await auditTool.execute({
          workflowId,
          stepId: step.id,
          decision: 'verification_warning',
          reason: verificationResult.message,
          actionTaken: 'Proceeding despite verification warning',
          agentName: 'VerificationAgent',
          status: 'warning',
        });
      }
    }

    // 8. Mark step as completed or failed
    const finalStatus = result.success ? 'COMPLETED' : 'FAILED';
    await prisma.step.update({
      where: { id: step.id },
      data: {
        status: finalStatus,
        currentOutput: result.data as object || null,
        retryCount: context.retryCount,
      },
    });

    if (result.success) {
      eventBus.emitWorkflowEvent('step:complete', workflowId, `Step completed: ${step.stepName}`, {
        stepId: step.id,
        data: result.data,
      });
    } else {
      eventBus.emitWorkflowEvent('step:failed', workflowId, `Step failed: ${step.stepName}`, {
        stepId: step.id,
        data: result.data,
      });
    }

    // Audit: step completion
    await auditTool.execute({
      workflowId,
      stepId: step.id,
      decision: finalStatus.toLowerCase(),
      reason: result.message,
      actionTaken: `Step ${finalStatus.toLowerCase()}`,
      agentName: step.assignedAgent,
      toolName: step.toolName,
      retryCount: context.retryCount,
      status: finalStatus.toLowerCase(),
    });

    stepOutputs.push({ step: step.stepName, status: finalStatus, ...result.data });
  }

  // 9. Mark workflow as complete
  const finalWorkflowStatus = hasEscalation ? 'ESCALATED' : 'COMPLETED';
  await prisma.workflow.update({
    where: { id: workflowId },
    data: { status: finalWorkflowStatus },
  });

  eventBus.emitWorkflowEvent('workflow:complete', workflowId, `Workflow "${workflow.type}" ${finalWorkflowStatus.toLowerCase()}`, {
    data: { totalSteps: workflow.steps.length, status: finalWorkflowStatus },
  });
}

/**
 * Dispatch a step to the correct agent based on step type.
 */
async function dispatchToAgent(context: StepContext) {
  switch (context.stepType) {
    case 'decision':
      return makeDecision(context);
    case 'execution':
      return executeStep(context);
    case 'verification':
      return verifyStep(context, { success: true, message: 'Pre-verification', status: 'completed' });
    default:
      return executeStep(context); // Default to execution
  }
}
