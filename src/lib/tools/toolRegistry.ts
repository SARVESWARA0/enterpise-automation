import { BaseTool, ToolInput, ToolResponse } from './baseTool';
import { EmailTool } from './emailTool';
import { CalendarTool } from './calendarTool';
import { TaskTool } from './taskTool';
import { EmployeeTool } from './employeeTool';
import { SlaTool } from './slaTool';
import { DelegateTool } from './delegateTool';
import { AuditTool } from './auditTool';

class ToolRegistry {
  private tools: Map<string, BaseTool> = new Map();

  constructor() {
    this.register(new EmailTool());
    this.register(new CalendarTool());
    this.register(new TaskTool());
    this.register(new EmployeeTool());
    this.register(new SlaTool());
    this.register(new DelegateTool());
    this.register(new AuditTool());
  }

  register(tool: BaseTool): void {
    this.tools.set(tool.name, tool);
  }

  getTool(name: string): BaseTool | undefined {
    return this.tools.get(name);
  }

  async executeTool(toolName: string, input: ToolInput): Promise<ToolResponse> {
    const tool = this.getTool(toolName);
    if (!tool) {
      return {
        success: false,
        message: `Tool "${toolName}" not found in registry`,
        errorCode: 'TOOL_NOT_FOUND',
        retryable: false,
      };
    }
    return tool.execute(input);
  }

  listTools(): { name: string; description: string }[] {
    return Array.from(this.tools.values()).map((t) => ({
      name: t.name,
      description: t.description,
    }));
  }
}

// Singleton
export const toolRegistry = new ToolRegistry();
