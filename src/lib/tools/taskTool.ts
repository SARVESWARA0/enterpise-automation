import { BaseTool, ToolInput, ToolResponse, simulateDelay, shouldSimulateFailure, successResponse, failureResponse } from './baseTool';

export class TaskTool implements BaseTool {
  name = 'taskTool';
  description = 'Create and manage tasks in project tracker (JIRA-like)';

  async execute(input: ToolInput): Promise<ToolResponse> {
    const action = input.action as string;

    switch (action) {
      case 'create_task':
        return this.createTask(input);
      case 'assign_task':
        return this.assignTask(input);
      case 'update_task':
        return this.updateTask(input);
      default:
        return failureResponse(`Unknown task action: ${action}`, 'UNKNOWN_ACTION', false);
    }
  }

  private async createTask(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(400, 800);

    if (shouldSimulateFailure(0.20)) {
      return failureResponse(
        'JIRA API connection failed: service unavailable',
        'JIRA_UNAVAILABLE',
        true
      );
    }

    const taskId = `TASK-${Math.floor(Math.random() * 9000) + 1000}`;
    return successResponse(`Task "${input.title}" created in tracker`, {
      taskId,
      title: input.title as string,
      description: input.description as string,
      assignee: input.assignee || 'unassigned',
      priority: input.priority || 'medium',
      project: input.project || 'DEFAULT',
      status: 'open',
      createdAt: new Date().toISOString(),
    });
  }

  private async assignTask(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(200, 400);

    return successResponse(`Task ${input.taskId} assigned to ${input.assignee}`, {
      taskId: input.taskId as string,
      assignee: input.assignee as string,
      updatedAt: new Date().toISOString(),
    });
  }

  private async updateTask(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(200, 400);

    return successResponse(`Task ${input.taskId} updated`, {
      taskId: input.taskId as string,
      status: input.status as string,
      updatedAt: new Date().toISOString(),
    });
  }
}
