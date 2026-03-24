// Simple in-process event emitter for SSE streaming
type EventHandler = (data: WorkflowEvent) => void;

export interface WorkflowEvent {
  type: 
    | 'workflow:start'
    | 'workflow:planning'
    | 'workflow:complete'
    | 'workflow:failed'
    | 'step:start'
    | 'step:complete'
    | 'step:failed'
    | 'step:retry'
    | 'step:escalated'
    | 'step:clarification'
    | 'agent:active'
    | 'agent:complete'
    | 'tool:call'
    | 'tool:result'
    | 'recovery:start'
    | 'recovery:complete'
    | 'verification:start'
    | 'verification:result';
  workflowId: string;
  stepId?: string;
  agentName?: string;
  toolName?: string;
  message: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

class EventBus {
  private listeners: Map<string, Set<EventHandler>> = new Map();
  private globalListeners: Set<EventHandler> = new Set();

  // Subscribe to events for a specific workflow
  subscribe(workflowId: string, handler: EventHandler): () => void {
    if (!this.listeners.has(workflowId)) {
      this.listeners.set(workflowId, new Set());
    }
    this.listeners.get(workflowId)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.listeners.get(workflowId)?.delete(handler);
      if (this.listeners.get(workflowId)?.size === 0) {
        this.listeners.delete(workflowId);
      }
    };
  }

  // Subscribe to ALL workflow events (for global dashboards)
  subscribeAll(handler: EventHandler): () => void {
    this.globalListeners.add(handler);
    return () => {
      this.globalListeners.delete(handler);
    };
  }

  // Emit an event
  emit(event: WorkflowEvent): void {
    // Notify workflow-specific listeners
    const handlers = this.listeners.get(event.workflowId);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(event);
        } catch (err) {
          console.error('[EventBus] Handler error:', err);
        }
      });
    }

    // Notify global listeners
    this.globalListeners.forEach((handler) => {
      try {
        handler(event);
      } catch (err) {
        console.error('[EventBus] Global handler error:', err);
      }
    });
  }

  // Helper to create and emit a standard event
  emitWorkflowEvent(
    type: WorkflowEvent['type'],
    workflowId: string,
    message: string,
    extra?: Partial<Omit<WorkflowEvent, 'type' | 'workflowId' | 'message' | 'timestamp'>>
  ): void {
    this.emit({
      type,
      workflowId,
      message,
      timestamp: new Date().toISOString(),
      ...extra,
    });
  }
}

// Singleton event bus
export const eventBus = new EventBus();
