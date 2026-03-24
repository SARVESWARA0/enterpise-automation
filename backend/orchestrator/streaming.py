"""
SSE Streaming helper — emits real-time events to the stream file.
"""
from state_manager import append_stream_event


def emit_event(workflow_id: str, event_type: str, agent_name: str, message: str, data: dict = None):
    """Write an SSE event to the stream file for frontend consumption.

    Args:
        workflow_id: The workflow this event belongs to.
        event_type: Event type string (e.g., 'chat:message', 'workflow:start').
        agent_name: Name of the agent emitting this event.
        message: Human-readable message.
        data: Optional structured data payload.
    """
    event = {
        "type": event_type,
        "workflowId": workflow_id,
        "agentName": agent_name,
        "message": message,
    }
    if data:
        event["data"] = data
    append_stream_event(workflow_id, event)
