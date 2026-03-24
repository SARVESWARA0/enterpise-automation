import prisma from '../db';
import { ToolResponse } from '../tools/baseTool';

// Agent execution result
export interface AgentResult {
  success: boolean;
  message: string;
  data?: Record<string, unknown>;
  status: 'completed' | 'failed' | 'awaiting_clarification' | 'escalated' | 'retried';
  toolOutput?: ToolResponse;
}

// Step context passed to agents
export interface StepContext {
  workflowId: string;
  stepId: string;
  stepName: string;
  stepType: string;
  toolName?: string;
  inputData?: Record<string, unknown>;
  workflowInput?: Record<string, unknown>;
  retryCount: number;
  maxRetries: number;
  previousStepOutputs?: Record<string, unknown>[];
}

// Log agent activity to the database
export async function logAgentActivity(
  workflowId: string,
  stepId: string | null,
  agentName: string,
  action: string,
  toolName?: string,
  input?: Record<string, unknown>,
  output?: Record<string, unknown>,
  durationMs?: number
): Promise<void> {
  try {
    await prisma.agentLog.create({
      data: {
        workflowId,
        stepId,
        agentName,
        action,
        toolName,
        input: input || undefined,
        output: output || undefined,
        durationMs,
      },
    });
  } catch (err) {
    console.error('[AgentBase] Failed to log agent activity:', err);
  }
}
