import { BaseTool, ToolInput, ToolResponse, successResponse, failureResponse } from './baseTool';
import prisma from '../db';

// Audit tool is DETERMINISTIC - it writes directly to DB, no AI agent involved
export class AuditTool implements BaseTool {
  name = 'auditTool';
  description = 'Log audit entries to the database (deterministic, not AI-driven)';

  async execute(input: ToolInput): Promise<ToolResponse> {
    try {
      const auditLog = await prisma.auditLog.create({
        data: {
          workflowId: input.workflowId as string,
          stepId: input.stepId as string | undefined,
          decision: input.decision as string | undefined,
          reason: input.reason as string | undefined,
          actionTaken: input.actionTaken as string | undefined,
          agentName: input.agentName as string | undefined,
          toolName: input.toolName as string | undefined,
          retryCount: input.retryCount as number | undefined,
          status: input.status as string | undefined,
        },
      });

      return successResponse('Audit log entry created', {
        auditId: auditLog.id,
        timestamp: auditLog.timestamp.toISOString(),
      });
    } catch (error) {
      return failureResponse(
        `Failed to create audit log: ${(error as Error).message}`,
        'AUDIT_DB_ERROR',
        true
      );
    }
  }
}
