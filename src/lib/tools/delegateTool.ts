import { BaseTool, ToolInput, ToolResponse, simulateDelay, successResponse, failureResponse } from './baseTool';

export class DelegateTool implements BaseTool {
  name = 'delegateTool';
  description = 'Find and assign delegates for workflow tasks';

  async execute(input: ToolInput): Promise<ToolResponse> {
    const action = input.action as string;

    switch (action) {
      case 'find_delegate':
        return this.findDelegate(input);
      case 'assign_delegate':
        return this.assignDelegate(input);
      default:
        return failureResponse(`Unknown delegate action: ${action}`, 'UNKNOWN_ACTION', false);
    }
  }

  private async findDelegate(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(300, 600);

    const delegates = [
      { name: 'Sarah Kim', role: 'Senior Manager', department: 'Operations', available: true },
      { name: 'Mike Torres', role: 'Team Lead', department: input.department || 'Engineering', available: true },
      { name: 'Lisa Wang', role: 'VP', department: 'Management', available: false },
    ];

    const available = delegates.filter((d) => d.available);
    const selected = available[Math.floor(Math.random() * available.length)];

    return successResponse(`Found delegate: ${selected.name}`, {
      delegate: selected,
      reason: `${selected.name} is available and has authority for ${input.taskType || 'this task'}`,
    });
  }

  private async assignDelegate(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(200, 400);

    return successResponse(`Delegate ${input.delegateName} assigned to handle ${input.taskDescription}`, {
      delegateId: `del-${Date.now()}`,
      delegateName: input.delegateName as string,
      taskDescription: input.taskDescription as string,
      assignedAt: new Date().toISOString(),
      expectedResolution: new Date(Date.now() + 7200000).toISOString(),
    });
  }
}
