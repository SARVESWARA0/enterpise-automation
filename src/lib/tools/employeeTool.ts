import { BaseTool, ToolInput, ToolResponse, simulateDelay, successResponse, failureResponse } from './baseTool';
import prisma from '../db';

export class EmployeeTool implements BaseTool {
  name = 'employeeTool';
  description = 'Create and manage employee records in the database';

  async execute(input: ToolInput): Promise<ToolResponse> {
    const action = input.action as string;

    switch (action) {
      case 'create_record':
        return this.createRecord(input);
      case 'update_status':
        return this.updateStatus(input);
      case 'get_employee':
        return this.getEmployee(input);
      default:
        return failureResponse(`Unknown employee action: ${action}`, 'UNKNOWN_ACTION', false);
    }
  }

  private async createRecord(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(200, 400);
    try {
      const employee = await prisma.employee.create({
        data: {
          name: input.name as string,
          email: input.email as string,
          role: input.role as string,
          department: input.department as string,
          status: 'ONBOARDING',
        },
      });
      return successResponse(`Employee record created for ${employee.name}`, {
        employeeId: employee.id,
        name: employee.name,
        email: employee.email,
        status: employee.status,
      });
    } catch (error) {
      return failureResponse(
        `Failed to create employee: ${(error as Error).message}`,
        'DB_ERROR',
        true
      );
    }
  }

  private async updateStatus(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(100, 300);
    try {
      const employee = await prisma.employee.update({
        where: { id: input.employeeId as string },
        data: { status: input.status as 'PENDING' | 'ONBOARDING' | 'ACTIVE' | 'FAILED' },
      });
      return successResponse(`Employee ${employee.name} status updated to ${employee.status}`, {
        employeeId: employee.id,
        status: employee.status,
      });
    } catch (error) {
      return failureResponse(
        `Failed to update employee status: ${(error as Error).message}`,
        'DB_ERROR',
        true
      );
    }
  }

  private async getEmployee(input: ToolInput): Promise<ToolResponse> {
    await simulateDelay(100, 200);
    try {
      const employee = await prisma.employee.findUnique({
        where: { id: input.employeeId as string },
      });
      if (!employee) {
        return failureResponse(`Employee not found: ${input.employeeId}`, 'NOT_FOUND', false);
      }
      return successResponse(`Employee found: ${employee.name}`, {
        employeeId: employee.id,
        name: employee.name,
        email: employee.email,
        role: employee.role,
        department: employee.department,
        status: employee.status,
      });
    } catch (error) {
      return failureResponse(
        `Failed to get employee: ${(error as Error).message}`,
        'DB_ERROR',
        true
      );
    }
  }
}
