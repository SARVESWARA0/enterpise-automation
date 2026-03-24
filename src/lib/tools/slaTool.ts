import { BaseTool, ToolInput, ToolResponse, simulateDelay, successResponse, failureResponse } from './baseTool';

export class SlaTool implements BaseTool {
  name = 'slaTool';
  description = 'Monitor and manage SLA compliance';

  async execute(input: ToolInput): Promise<ToolResponse> {
    const action = input.action as string;

    switch (action) {
      case 'check_status':
        return this.checkStatus(input);
      case 'update_status':
        return this.updateStatus(input);
      case 'detect_bottleneck':
        return this.detectBottleneck(input);
      default:
        return failureResponse(`Unknown SLA action: ${action}`, 'UNKNOWN_ACTION', false);
    }
  }

  private async checkStatus(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(200, 500);

    const deadline = input.deadline ? new Date(input.deadline as string) : new Date(Date.now() + 86400000);
    const isOverdue = deadline < new Date();
    const hoursRemaining = Math.round((deadline.getTime() - Date.now()) / 3600000);

    return successResponse(`SLA status checked for ${input.workflowId || 'workflow'}`, {
      workflowId: input.workflowId as string,
      isOverdue,
      hoursRemaining,
      riskLevel: isOverdue ? 'critical' : hoursRemaining < 4 ? 'high' : hoursRemaining < 12 ? 'medium' : 'low',
      deadline: deadline.toISOString(),
    });
  }

  private async updateStatus(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(200, 400);

    return successResponse(`SLA status updated to ${input.newStatus}`, {
      workflowId: input.workflowId as string,
      previousStatus: input.currentStatus || 'unknown',
      newStatus: input.newStatus as string,
      updatedAt: new Date().toISOString(),
    });
  }

  private async detectBottleneck(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(300, 600);

    const bottlenecks = [
      { stage: 'approval', assignee: 'Manager A', stalledHours: 8 },
      { stage: 'review', assignee: 'Reviewer B', stalledHours: 4 },
    ];

    const randomBottleneck = bottlenecks[Math.floor(Math.random() * bottlenecks.length)];

    return successResponse(`Bottleneck detected at ${randomBottleneck.stage} stage`, {
      workflowId: input.workflowId as string,
      bottleneck: randomBottleneck,
      suggestion: `Reroute to delegate or escalate to management`,
    });
  }
}
