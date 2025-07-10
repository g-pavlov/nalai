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
        elif hasattr(event, "to_dict"):
            return event.to_dict()
        elif hasattr(event, "__dict__"):
            return serialize_event_default(event.__dict__)
        else:
            return event
    except Exception:
        return str(event)


def format_sse_event_default(event_type: str, data: str) -> str:
    """Default SSE event formatter."""
    return f"event: {event_type}\ndata: {data}\n\n"


def process_and_format_event(
    event: dict,
    allowed_events: list,
    serialize_event: Callable[[object], object],
    format_sse_event: Callable[[str, str], str],
) -> str | None:
    """Process a single event and return formatted SSE data if applicable."""
    event_type = event.get("event")

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
) -> AsyncGenerator[str, None]:
    """
    Special event stream handler used by the /human-review endpoint.

    Events are instances of StreamEvent (Union[StandardStreamEvent, CustomStreamEvent]),
    which are TypedDict types that behave like dictionaries.
    """
    try:
        async for event in agent.astream_events(
            Command(resume=resume_input), config, stream_mode="values"
        ):
            # Handle both StandardStreamEvent and CustomStreamEvent
            if isinstance(event, dict):
                event_type = event.get("event")
                if event_type in ("on_chat_model_stream", "on_tool_end"):
                    yield format_sse_event("data", json.dumps(serialize_event(event)))

        snapshot = agent.get_state(config)
        if len(snapshot) and len(snapshot[-1]) > 0:
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
    except Exception as e:
        logger.error(f"Error in event stream: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
