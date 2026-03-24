import { AgentResult, StepContext, logAgentActivity } from './agentBase';
import { toolRegistry } from '../tools/toolRegistry';
import { eventBus } from '../workflow/eventBus';

/**
 * Execution Agent — calls tools to perform actual workflow actions.
 * This agent is responsible for executing individual workflow steps
 * by invoking the appropriate tool from the tool registry.
 */
export async function executeStep(context: StepContext): Promise<AgentResult> {
  const startTime = Date.now();
  const agentName = 'ExecutionAgent';

  eventBus.emitWorkflowEvent('agent:active', context.workflowId, `Execution Agent starting: ${context.stepName}`, {
    stepId: context.stepId,
    agentName,
  });

  try {
    if (!context.toolName) {
      // No tool needed — this is a non-tool step
      const result: AgentResult = {
        success: true,
        message: `Step "${context.stepName}" completed (no tool required)`,
        status: 'completed',
        data: { note: 'No tool invocation was needed for this step' },
      };

      await logAgentActivity(
        context.workflowId,
        context.stepId,
        agentName,
        'execute_no_tool',
        undefined,
        context.inputData,
        result.data,
        Date.now() - startTime
      );

      return result;
    }

    // Emit tool call event
    eventBus.emitWorkflowEvent('tool:call', context.workflowId, `Calling tool: ${context.toolName}`, {
      stepId: context.stepId,
      agentName,
      toolName: context.toolName,
      data: { input: context.inputData },
    });

    // Execute the tool
    const toolResponse = await toolRegistry.executeTool(context.toolName, context.inputData || {});

    // Emit tool result event
    eventBus.emitWorkflowEvent('tool:result', context.workflowId, `Tool ${context.toolName}: ${toolResponse.message}`, {
      stepId: context.stepId,
      agentName,
      toolName: context.toolName,
      data: { result: toolResponse },
    });

    const durationMs = Date.now() - startTime;

    await logAgentActivity(
      context.workflowId,
      context.stepId,
      agentName,
      toolResponse.success ? 'execute_success' : 'execute_failure',
      context.toolName,
      context.inputData,
      toolResponse as unknown as Record<string, unknown>,
      durationMs
    );

    if (toolResponse.success) {
      return {
        success: true,
        message: toolResponse.message,
        status: 'completed',
        data: toolResponse.data,
        toolOutput: toolResponse,
      };
    } else {
      return {
        success: false,
        message: toolResponse.message,
        status: 'failed',
        data: { errorCode: toolResponse.errorCode, retryable: toolResponse.retryable },
        toolOutput: toolResponse,
      };
    }
  } catch (error) {
    const durationMs = Date.now() - startTime;
    const errorMsg = (error as Error).message;

    await logAgentActivity(
      context.workflowId,
      context.stepId,
      agentName,
      'execute_error',
      context.toolName,
      context.inputData,
      { error: errorMsg },
      durationMs
    );

    return {
      success: false,
      message: `Execution error: ${errorMsg}`,
      status: 'failed',
      data: { error: errorMsg, retryable: true },
    };
  }
}
