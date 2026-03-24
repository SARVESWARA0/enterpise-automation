import prisma from '../db';

// Step plan item structure
export interface StepPlan {
  step: string;
  type: 'execution' | 'decision' | 'verification' | 'notification';
  agent: 'ExecutionAgent' | 'DecisionAgent' | 'VerificationAgent';
  tool?: string;
  toolInput?: Record<string, unknown>;
  fallbackBehavior?: string;
  dependencyOrder: number;
}

// Known workflow templates
const WORKFLOW_TEMPLATES: Record<string, (input: Record<string, unknown>) => StepPlan[]> = {
  employee_onboarding: (input) => [
    {
      step: 'Create email account',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'emailTool',
      toolInput: { action: 'create_account', email: input.email, name: input.name },
      fallbackBehavior: 'escalate_to_IT',
      dependencyOrder: 1,
    },
    {
      step: 'Create JIRA access',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'taskTool',
      toolInput: { action: 'create_task', title: `Setup JIRA access for ${input.name}`, description: `Create JIRA account and assign to ${input.department} project`, assignee: 'IT Admin', project: input.department },
      fallbackBehavior: 'escalate_to_IT',
      dependencyOrder: 2,
    },
    {
      step: 'Assign onboarding buddy',
      type: 'decision',
      agent: 'DecisionAgent',
      toolInput: { candidates: [], taskDescription: `Assign a buddy for ${input.name} in ${input.department}`, department: input.department },
      dependencyOrder: 3,
    },
    {
      step: 'Schedule orientation meeting',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'calendarTool',
      toolInput: { action: 'create_event', title: `Orientation: ${input.name}`, attendees: [input.email, 'hr@company.com'], duration: '90min', location: 'Conference Room A' },
      dependencyOrder: 4,
    },
    {
      step: 'Create onboarding task list',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'taskTool',
      toolInput: { action: 'create_task', title: `Onboarding checklist for ${input.name}`, description: 'Complete all onboarding tasks within first week', assignee: input.name, project: 'ONBOARDING' },
      dependencyOrder: 5,
    },
    {
      step: 'Send welcome email',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'emailTool',
      toolInput: { action: 'send_email', to: input.email, subject: `Welcome to the team, ${input.name}!`, body: `We're excited to have you join the ${input.department} team.` },
      dependencyOrder: 6,
    },
    {
      step: 'Update employee status to active',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'employeeTool',
      toolInput: { action: 'update_status', employeeId: input.employeeId, status: 'ACTIVE' },
      dependencyOrder: 7,
    },
  ],

  meeting_action_items: (input) => [
    {
      step: 'Extract action items from transcript',
      type: 'decision',
      agent: 'DecisionAgent',
      toolInput: { 
        action: 'extract_actions', 
        transcript: input.transcript,
        items: parseActionItems(input.transcript as string),
      },
      dependencyOrder: 1,
    },
    {
      step: 'Detect ambiguity in action owners',
      type: 'decision',
      agent: 'DecisionAgent',
      toolInput: { 
        action: 'detect_ambiguity',
        items: parseActionItems(input.transcript as string),
      },
      dependencyOrder: 2,
    },
    {
      step: 'Create tasks for clear action items',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'taskTool',
      toolInput: { action: 'create_task', title: 'Meeting action items', description: 'Tasks from meeting transcript', project: 'MEETINGS' },
      dependencyOrder: 3,
    },
    {
      step: 'Send meeting summary email',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'emailTool',
      toolInput: { action: 'send_email', to: input.participants || 'team@company.com', subject: 'Meeting Summary & Action Items', body: `Action items from meeting: ${input.transcript}` },
      dependencyOrder: 4,
    },
    {
      step: 'Schedule follow-up if needed',
      type: 'decision',
      agent: 'DecisionAgent',
      toolInput: { action: 'decide_followup', context: input.transcript },
      dependencyOrder: 5,
    },
  ],

  sla_breach_prevention: (input) => [
    {
      step: 'Check current SLA status',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'slaTool',
      toolInput: { action: 'check_status', workflowId: input.workflowId, deadline: input.deadline },
      dependencyOrder: 1,
    },
    {
      step: 'Detect bottleneck',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'slaTool',
      toolInput: { action: 'detect_bottleneck', workflowId: input.workflowId },
      dependencyOrder: 2,
    },
    {
      step: 'Find available delegate',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'delegateTool',
      toolInput: { action: 'find_delegate', department: input.department, taskType: 'approval' },
      dependencyOrder: 3,
    },
    {
      step: 'Assign delegate for stalled task',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'delegateTool',
      toolInput: { action: 'assign_delegate', delegateName: 'Auto-selected delegate', taskDescription: `Handle stalled ${input.taskType || 'approval'}` },
      dependencyOrder: 4,
    },
    {
      step: 'Update SLA status',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'slaTool',
      toolInput: { action: 'update_status', workflowId: input.workflowId, currentStatus: 'at_risk', newStatus: 'delegated' },
      dependencyOrder: 5,
    },
    {
      step: 'Send escalation notification',
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'emailTool',
      toolInput: { action: 'send_email', to: 'management@company.com', subject: `SLA Escalation: ${input.taskType || 'Task'}`, body: `SLA breach prevented by delegation. Original approver was unavailable.` },
      dependencyOrder: 6,
    },
  ],
};

// Parse action items from transcript text (simple extraction)
function parseActionItems(transcript: string): Array<{ text: string; owner?: string }> {
  if (!transcript) return [];
  
  const lines = transcript.split(/[.\n]/).filter((l) => l.trim().length > 10);
  return lines.slice(0, 5).map((line) => {
    const trimmed = line.trim();
    // Try to detect owner mentions
    const ownerMatch = trimmed.match(/(\w+)\s+(will|should|needs to|to)\s+/i);
    return {
      text: trimmed,
      owner: ownerMatch ? ownerMatch[1] : undefined,
    };
  });
}

/**
 * Interpret a workflow request into a structured step plan.
 * Supports known templates AND dynamic/surprise workflows.
 */
export async function interpretWorkflow(
  type: string,
  inputData: Record<string, unknown>
): Promise<{ workflowId: string; steps: StepPlan[] }> {
  // 1. Check if we have a known template
  const templateFn = WORKFLOW_TEMPLATES[type];
  let steps: StepPlan[];

  if (templateFn) {
    steps = templateFn(inputData);
  } else {
    // 2. Dynamic/surprise workflow — generate a generic plan
    steps = generateDynamicPlan(type, inputData);
  }

  // 3. Create workflow in DB
  const workflow = await prisma.workflow.create({
    data: {
      type,
      entityId: inputData.employeeId as string | undefined,
      triggerEvent: inputData.triggerEvent as string || `${type}_initiated`,
      inputData: inputData as object,
      status: 'PLANNING',
      plan: steps as unknown as object,
    },
  });

  // 4. Create steps in DB
  for (const step of steps) {
    await prisma.step.create({
      data: {
        workflowId: workflow.id,
        stepName: step.step,
        stepType: step.type,
        status: 'PENDING',
        assignedAgent: step.agent,
        toolName: step.tool || null,
        inputData: step.toolInput as object || null,
        fallbackBehavior: step.fallbackBehavior || null,
        dependencyOrder: step.dependencyOrder,
        maxRetries: 2,
      },
    });
  }

  // Update workflow status to PENDING (ready for execution)
  await prisma.workflow.update({
    where: { id: workflow.id },
    data: { status: 'PENDING' },
  });

  return { workflowId: workflow.id, steps };
}

/**
 * Generate a dynamic plan for unknown/surprise workflows.
 */
function generateDynamicPlan(type: string, input: Record<string, unknown>): StepPlan[] {
  const typeName = type.replace(/_/g, ' ');
  const steps: StepPlan[] = [
    {
      step: `Analyze ${typeName} request`,
      type: 'decision',
      agent: 'DecisionAgent',
      toolInput: { action: 'analyze', context: input, workflowType: type },
      dependencyOrder: 1,
    },
    {
      step: `Validate ${typeName} requirements`,
      type: 'decision',
      agent: 'DecisionAgent',
      toolInput: { action: 'validate', context: input },
      dependencyOrder: 2,
    },
    {
      step: `Create tracking task for ${typeName}`,
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'taskTool',
      toolInput: { action: 'create_task', title: `${typeName} workflow`, description: `Auto-generated workflow for: ${typeName}`, priority: 'high', project: 'DYNAMIC' },
      dependencyOrder: 3,
    },
    {
      step: `Execute primary action for ${typeName}`,
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: determineBestTool(type, input),
      toolInput: buildDynamicToolInput(type, input),
      fallbackBehavior: 'delegate',
      dependencyOrder: 4,
    },
    {
      step: `Send notification for ${typeName}`,
      type: 'execution',
      agent: 'ExecutionAgent',
      tool: 'emailTool',
      toolInput: { action: 'send_email', to: input.notifyEmail || 'operations@company.com', subject: `Workflow completed: ${typeName}`, body: `The ${typeName} workflow has been processed.` },
      dependencyOrder: 5,
    },
  ];

  return steps;
}

function determineBestTool(type: string, input: Record<string, unknown>): string {
  const typeLower = type.toLowerCase();
  if (typeLower.includes('email') || typeLower.includes('notification')) return 'emailTool';
  if (typeLower.includes('meeting') || typeLower.includes('schedule') || typeLower.includes('calendar')) return 'calendarTool';
  if (typeLower.includes('task') || typeLower.includes('ticket') || typeLower.includes('jira')) return 'taskTool';
  if (typeLower.includes('employee') || typeLower.includes('hr') || typeLower.includes('onboard')) return 'employeeTool';
  if (typeLower.includes('sla') || typeLower.includes('deadline') || typeLower.includes('overdue')) return 'slaTool';
  if (typeLower.includes('delegate') || typeLower.includes('assign') || typeLower.includes('approve')) return 'delegateTool';
  return 'taskTool'; // Default to task creation
}

function buildDynamicToolInput(type: string, input: Record<string, unknown>): Record<string, unknown> {
  const tool = determineBestTool(type, input);
  const typeName = type.replace(/_/g, ' ');

  switch (tool) {
    case 'emailTool':
      return { action: 'send_email', to: input.email || 'team@company.com', subject: typeName, body: `Processing: ${typeName}` };
    case 'calendarTool':
      return { action: 'create_event', title: typeName, duration: '30min' };
    case 'taskTool':
      return { action: 'create_task', title: typeName, description: `Dynamic workflow: ${typeName}`, priority: 'medium' };
    case 'employeeTool':
      return { action: 'update_status', employeeId: input.employeeId, status: input.status || 'ACTIVE' };
    case 'slaTool':
      return { action: 'check_status', workflowId: input.workflowId };
    case 'delegateTool':
      return { action: 'find_delegate', department: input.department || 'Operations', taskType: typeName };
    default:
      return { action: 'create_task', title: typeName };
  }
}
