import { AgentResult, StepContext, logAgentActivity } from './agentBase';
import { eventBus } from '../workflow/eventBus';

/**
 * Verification Agent — confirms that execution succeeded and expected side effects occurred.
 */
export async function verifyStep(context: StepContext, executionResult: AgentResult): Promise<AgentResult> {
  const startTime = Date.now();
  const agentName = 'VerificationAgent';

  eventBus.emitWorkflowEvent('verification:start', context.workflowId, `Verifying step: ${context.stepName}`, {
    stepId: context.stepId,
    agentName,
  });

  try {
    // Simulate verification delay
    await new Promise((r) => setTimeout(r, 200 + Math.random() * 300));

    const checks: { check: string; passed: boolean; detail: string }[] = [];

    // 1. Check that the execution result was successful
    checks.push({
      check: 'execution_success',
      passed: executionResult.success,
      detail: executionResult.success ? 'Execution reported success' : `Execution failed: ${executionResult.message}`,
    });

    // 2. Check that we got meaningful output
    const hasOutput = executionResult.data && Object.keys(executionResult.data).length > 0;
    checks.push({
      check: 'output_present',
      passed: !!hasOutput,
      detail: hasOutput ? 'Output data received' : 'No output data from execution',
    });

    // 3. Check tool-specific expectations
    if (context.toolName) {
      const toolCheck = verifyToolOutput(context.toolName, executionResult);
      checks.push(toolCheck);
    }

    const allPassed = checks.every((c) => c.passed);
    const failedChecks = checks.filter((c) => !c.passed);

    const durationMs = Date.now() - startTime;
    const resultData = { checks, allPassed, failedChecks };

    await logAgentActivity(
      context.workflowId,
      context.stepId,
      agentName,
      allPassed ? 'verification_passed' : 'verification_failed',
      context.toolName,
      { executionResult: executionResult.message },
      resultData,
      durationMs
    );

    const result: AgentResult = {
      success: allPassed,
      message: allPassed
        ? `Verification passed: ${checks.length}/${checks.length} checks OK`
        : `Verification failed: ${failedChecks.length}/${checks.length} checks failed`,
      status: allPassed ? 'completed' : 'failed',
      data: resultData,
    };

    eventBus.emitWorkflowEvent('verification:result', context.workflowId, result.message, {
      stepId: context.stepId,
      agentName,
      data: resultData,
    });

    return result;
  } catch (error) {
    const errorMsg = (error as Error).message;
    await logAgentActivity(
      context.workflowId,
      context.stepId,
      agentName,
      'verification_error',
      context.toolName,
      undefined,
      { error: errorMsg },
      Date.now() - startTime
    );

    return {
      success: false,
      message: `Verification error: ${errorMsg}`,
      status: 'failed',
    };
  }
}

function verifyToolOutput(toolName: string, result: AgentResult): { check: string; passed: boolean; detail: string } {
  const data = result.data || {};

  switch (toolName) {
    case 'emailTool':
      const hasEmailId = !!data.email || !!data.messageId || !!data.accountId;
      return {
        check: 'email_tool_output',
        passed: hasEmailId,
        detail: hasEmailId ? 'Email tool returned expected identifiers' : 'Missing email identifiers in output',
      };

    case 'calendarTool':
      const hasEventId = !!data.eventId;
      return {
        check: 'calendar_tool_output',
        passed: hasEventId,
        detail: hasEventId ? 'Calendar event ID confirmed' : 'Missing event ID',
      };

    case 'taskTool':
      const hasTaskId = !!data.taskId;
      return {
        check: 'task_tool_output',
        passed: hasTaskId,
        detail: hasTaskId ? 'Task ID confirmed in tracker' : 'Missing task ID from tracker',
      };

    case 'employeeTool':
      const hasEmpId = !!data.employeeId;
      return {
        check: 'employee_tool_output',
        passed: hasEmpId,
        detail: hasEmpId ? 'Employee record ID confirmed' : 'Missing employee record ID',
      };

    default:
      return {
        check: `${toolName}_output`,
        passed: result.success,
        detail: `Tool ${toolName} output verified by success flag`,
      };
  }
}
