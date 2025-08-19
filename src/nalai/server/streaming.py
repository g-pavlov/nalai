"""
Event handling utilities for API Assistant server.

This module contains functions for processing, serializing, and formatting
events from the agent, including specialized handlers for different event types.
"""

import json
import logging
from collections.abc import AsyncGenerator, Callable

from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger("nalai")


def format_sse_event_default(event_type: str, data: str) -> str:
    """Default SSE event formatter."""
    return f"event: {event_type}\ndata: {data}\n\n"


def serialize_event_default(event: object) -> object:
    """Default event serializer that handles various object types."""
    try:
        if isinstance(event, dict):
            # Only filter the irrelavant or sensitive data, keep workflow state
            filtered_event = {}
            for k, v in event.items():
                # Only filter the sensitive data, keep workflow state
                if k in ["api_specs", "api_summaries"]:
                    continue  # Skip these entirely
                elif k == "__interrupt__" and isinstance(v, list):
                    # Handle interrupt list - serialize each interrupt object completely
                    filtered_event[k] = [serialize_event_default(item) for item in v]
                elif k == "data" and isinstance(v, dict):
                    # Recursively filter nested data objects
                    filtered_data = {}
                    for data_k, data_v in v.items():
                        if data_k in ["api_specs", "api_summaries"]:
                            continue  # Skip these entirely
                        else:
                            filtered_data[data_k] = serialize_event_default(data_v)
                    filtered_event[k] = filtered_data
                elif k == "config" and isinstance(v, dict):
                    # Ensure config dictionaries preserve JSON boolean values
                    config_dict = {}
                    for config_k, config_v in v.items():
                        if isinstance(config_v, bool):
                            config_dict[config_k] = bool(
                                config_v
                            )  # Ensure JSON boolean
                        else:
                            config_dict[config_k] = serialize_event_default(config_v)
                    filtered_event[k] = config_dict
                else:
                    filtered_event[k] = serialize_event_default(v)
            return filtered_event
        elif hasattr(event, "model_dump"):
            # Pydantic model - convert to dict and filter
            event_dict = event.model_dump()
            return serialize_event_default(event_dict)
        elif hasattr(event, "to_dict"):
            return serialize_event_default(event.to_dict())
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
        elif hasattr(event, "__class__") and event.__class__.__name__ == "Interrupt":
            # Handle LangGraph Interrupt objects by type name - serialize all attributes
            interrupt_dict = {}
            # Get all attributes, including those that might not be in __dict__
            for attr_name in dir(event):
                if not attr_name.startswith("_"):  # Skip private attributes
                    try:
                        attr_value = getattr(event, attr_name)
                        if not callable(attr_value):  # Skip methods
                            # Ensure boolean values are properly serialized
                            if isinstance(attr_value, bool):
                                interrupt_dict[attr_name] = attr_value
                            else:
                                interrupt_dict[attr_name] = serialize_event_default(
                                    attr_value
                                )
                    except Exception:
                        continue  # Skip attributes that can't be accessed
            return interrupt_dict
        else:
            # Handle specific types that might be converted to strings incorrectly
            if isinstance(event, bool):
                return bool(event)  # Ensure JSON boolean
            elif event is None:
                return None
            else:
                # Try to convert to string for other types
                return str(event)
    except Exception as e:
        logger.warning(f"Error serializing event: {e}")
        return str(event)


async def stream_events(
    agent: CompiledStateGraph,
    config: dict,
    agent_input: dict,
    resume_input: dict | None = None,
    *,
    serialize_event: Callable[[object], object] = serialize_event_default,
) -> AsyncGenerator[str, None]:
    """
    Stream events with API interruption handling using astream.

    Args:
        agent: Compiled LangGraph agent
        config: Runtime configuration with user context
        agent_input: Input for the agent
        resume_input: Optional resume input if resuming from interrupt
        serialize_event: Function to serialize event data

    Yields:
        Formatted SSE event strings
    """
    try:
        # If we have resume input, this means we're resuming from an interrupt
        if resume_input:
            logger.info(f"Resuming workflow with input: {resume_input}")
            # Resume the workflow with the human's decision
            from langgraph.types import Command

            # Structure resume_input like CLI: wrap in list (resume_input is already a dict)
            resume_command = [resume_input]
            async for chunk in agent.astream(
                Command(resume=resume_command),
                config,
                stream_mode=["updates", "messages"],
            ):
                # Add response_type to metadata for logging
                if hasattr(chunk, "metadata"):
                    chunk.metadata = getattr(chunk, "metadata", {})
                    chunk.metadata["response_type"] = resume_input.get(
                        "action", "unknown"
                    )

                serialized_chunk = serialize_event(chunk)
                if serialized_chunk:
                    yield f"data: {json.dumps(serialized_chunk)}\n\n"
        else:
            # Start fresh workflow
            logger.info("Streaming events from workflow start")
            async for chunk in agent.astream(
                agent_input, config, stream_mode=["updates", "messages"]
            ):
                serialized_chunk = serialize_event(chunk)
                if serialized_chunk:
                    yield f"data: {json.dumps(serialized_chunk)}\n\n"

    except Exception as e:
        logger.error(f"Error in API event streaming: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
