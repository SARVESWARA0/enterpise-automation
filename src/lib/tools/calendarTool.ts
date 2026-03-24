import { BaseTool, ToolInput, ToolResponse, simulateDelay, shouldSimulateFailure, successResponse, failureResponse } from './baseTool';

export class CalendarTool implements BaseTool {
  name = 'calendarTool';
  description = 'Create and manage calendar events';

  async execute(input: ToolInput): Promise<ToolResponse> {
    const action = input.action as string;

    switch (action) {
      case 'create_event':
        return this.createEvent(input);
      case 'check_availability':
        return this.checkAvailability(input);
      default:
        return failureResponse(`Unknown calendar action: ${action}`, 'UNKNOWN_ACTION', false);
    }
  }

  private async createEvent(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(300, 600);

    if (shouldSimulateFailure(0.10)) {
      return failureResponse(
        'Calendar service unavailable: rate limit exceeded',
        'RATE_LIMIT',
        true
      );
    }

    const startTime = input.startTime || new Date(Date.now() + 86400000).toISOString();
    return successResponse(`Calendar event "${input.title}" created`, {
      eventId: `evt-${Date.now()}`,
      title: input.title as string,
      startTime,
      duration: input.duration || '60min',
      attendees: input.attendees || [],
      location: input.location || 'Virtual - Teams',
      createdAt: new Date().toISOString(),
    });
  }

  private async checkAvailability(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(200, 400);

    return successResponse(`Availability checked for ${input.participant}`, {
      participant: input.participant as string,
      available: Math.random() > 0.3,
      nextAvailableSlot: new Date(Date.now() + 3600000).toISOString(),
    });
  }
}
