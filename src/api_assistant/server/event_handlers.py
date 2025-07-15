"""
Event handling utilities for API Assistant server.

This module contains functions for processing, serializing, and formatting
events from the agent, including specialized handlers for different event types.
"""

import json
import logging
from collections.abc import AsyncGenerator, Callable

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

logger = logging.getLogger("api-assistant")


def serialize_event_default(event: object) -> object:
    """Default event serializer that handles various object types."""
    try:
        if isinstance(event, dict):
            return {k: serialize_event_default(v) for k, v in event.items()}
        elif hasattr(event, "model_dump"):
            # Pydantic model - convert to dict
            return event.model_dump()
        elif hasattr(event, "to_dict"):
            return event.to_dict()
        elif hasattr(event, "__dict__"):
            # Handle LangChain message objects specially
            if hasattr(event, "content") and hasattr(event, "__class__"):
                # This is likely a LangChain message object
                return {
                    "type": event.__class__.__name__,
                    "content": str(event.content),
                    "id": getattr(event, "id", None),
                    "tool_calls": getattr(event, "tool_calls", None),
                    "tool_call_chunks": getattr(event, "tool_call_chunks", None),
                    "invalid_tool_calls": getattr(event, "invalid_tool_calls", None),
                }
            else:
                # Generic object with __dict__
                return {
                    k: serialize_event_default(v) for k, v in event.__dict__.items()
                }
        elif isinstance(event, list | tuple):
            return [serialize_event_default(item) for item in event]
        else:
            # Try to convert to string for other types
            return str(event)
    except Exception:
        # Fallback: return string representation
        return f"<{type(event).__name__}: {str(event)}>"


def format_sse_event_default(event_type: str, data: str) -> str:
    """Default SSE event formatter."""
    return f"event: {event_type}\ndata: {data}\n\n"


def process_and_format_event(
    event: dict,
    allowed_events: list[str],
    serialize_event: Callable[[object], object],
    format_sse_event: Callable[[str, str], str],
) -> str | None:
    """
    Process a single event and return formatted SSE data if applicable.

    Args:
        event: Event dictionary from LangGraph
        allowed_events: List of allowed event types to process
        serialize_event: Function to serialize event data
        format_sse_event: Function to format SSE event

    Returns:
        Formatted SSE event string or None if event should be filtered out
    """
    event_type = event.get("event")

    if not event_type:
        return None

    # For on_chain_stream events, only include if they contain __interrupt__ in the data chunk
    if event_type == "on_chain_stream":
        event_data = event.get("data", {})
        chunk = event_data.get("chunk", {})
        if "__interrupt__" in chunk:
            return format_sse_event("data", json.dumps(serialize_event(event)))
    # For other event types, check if they're in the allowed list
    elif event_type in allowed_events:
        return format_sse_event("data", json.dumps(serialize_event(event)))

    return None


async def stream_interruptable_events(
    agent: CompiledStateGraph,
    resume_input: dict,
    config: dict,
    *,
    serialize_event: Callable[[object], object] = serialize_event_default,
    format_sse_event: Callable[[str, str], str] = format_sse_event_default,
    allowed_events: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Special event stream handler used by the /human-review endpoint.

    Events are instances of StreamEvent (Union[StandardStreamEvent, CustomStreamEvent]),
    which are TypedDict types that behave like dictionaries.

    Args:
        agent: Compiled LangGraph agent
        resume_input: Input for resuming the workflow
        config: Runtime configuration with user context
        serialize_event: Function to serialize event data
        format_sse_event: Function to format SSE event
        allowed_events: List of allowed event types (defaults to human review events)

    Yields:
        Formatted SSE event strings
    """
    # Default allowed events for human review
    if allowed_events is None:
        allowed_events = ["on_chat_model_stream", "on_tool_end"]

    try:
        async for event in agent.astream_events(
            Command(resume=resume_input), config, stream_mode="values"
        ):
            # Handle both StandardStreamEvent and CustomStreamEvent
            if isinstance(event, dict):
                formatted_event = process_and_format_event(
                    event, allowed_events, serialize_event, format_sse_event
                )
                if formatted_event:
                    yield formatted_event

        # Check for interrupts in the final state
        snapshot = agent.get_state(config)
        if snapshot and len(snapshot) > 0 and len(snapshot[-1]) > 0:
            try:
                interrupt = snapshot[-1][0].interrupts[0]
                interruption_data = {
                    "event": "on_chain_stream",
                    "data": {
                        "chunk": {
                            "__interrupt__": [
                                {
                                    "value": interrupt.value,
                                    "resumable": interrupt.resumable,
                                    "ns": interrupt.ns,
                                    "when": interrupt.when,
                                }
                            ]
                        }
                    },
                }
                yield format_sse_event("data", json.dumps(interruption_data))
            except (IndexError, AttributeError) as e:
                logger.debug(f"No interrupt found in snapshot: {e}")
                # No interrupt found, which is normal for completed workflows

    except Exception as e:
        logger.error(f"Error in event stream: {str(e)}")
        yield format_sse_event("error", json.dumps({"error": str(e)}))
