import { BaseTool, ToolInput, ToolResponse, simulateDelay, shouldSimulateFailure, successResponse, failureResponse } from './baseTool';

export class EmailTool implements BaseTool {
  name = 'emailTool';
  description = 'Send emails and create email accounts';

  async execute(input: ToolInput): Promise<ToolResponse> {
    const action = input.action as string;

    switch (action) {
      case 'create_account':
        return this.createAccount(input);
      case 'send_email':
        return this.sendEmail(input);
      default:
        return failureResponse(`Unknown email action: ${action}`, 'UNKNOWN_ACTION', false);
    }
  }

  private async createAccount(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(400, 1000);

    if (shouldSimulateFailure(0.15)) {
      return failureResponse(
        `Failed to create email account for ${input.email}: SMTP server timeout`,
        'SMTP_TIMEOUT',
        true
      );
    }

    return successResponse(`Email account created for ${input.email}`, {
      email: input.email as string,
      provider: 'enterprise-mail',
      accountId: `mail-${Date.now()}`,
      createdAt: new Date().toISOString(),
    });
  }

  private async sendEmail(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(300, 700);

    if (shouldSimulateFailure(0.10)) {
      return failureResponse(
        `Failed to send email to ${input.to}: delivery timeout`,
        'DELIVERY_TIMEOUT',
        true
      );
    }

    return successResponse(`Email sent to ${input.to}`, {
      messageId: `msg-${Date.now()}`,
      to: input.to as string,
      subject: input.subject as string,
      sentAt: new Date().toISOString(),
    });
  }
}
