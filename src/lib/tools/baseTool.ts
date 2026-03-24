// Tool response contract
export interface ToolResponse {
  success: boolean;
  message: string;
  data?: Record<string, unknown>;
  errorCode?: string;
  retryable?: boolean;
}

// Tool input
export interface ToolInput {
  [key: string]: unknown;
}

// Base tool interface
export interface BaseTool {
  name: string;
  description: string;
  execute(input: ToolInput): Promise<ToolResponse>;
}

// Helper to simulate async delays (mock tools)
export function simulateDelay(minMs: number = 200, maxMs: number = 800): Promise<void> {
  const delay = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
  return new Promise((resolve) => setTimeout(resolve, delay));
}

// Helper to simulate random failures for demo purposes
export function shouldSimulateFailure(failureRate: number = 0.15): boolean {
  return Math.random() < failureRate;
}

// Create a success response
export function successResponse(message: string, data?: Record<string, unknown>): ToolResponse {
  return { success: true, message, data };
}

// Create a failure response
export function failureResponse(
  message: string,
  errorCode: string,
  retryable: boolean = true
): ToolResponse {
  return { success: false, message, errorCode, retryable };
}
