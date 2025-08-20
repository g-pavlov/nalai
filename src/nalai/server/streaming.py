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

# Constants
SENSITIVE_FIELDS = {"api_specs", "api_summaries"}
INTERRUPT_CLASS_NAME = "Interrupt"
LANGCHAIN_MESSAGE_FIELDS = {
    "content",
    "id",
    "tool_calls",
    "tool_call_chunks",
    "invalid_tool_calls",
}


def format_sse_event_default(event_type: str, data: str) -> str:
    """Default SSE event formatter."""
    return f"event: {event_type}\ndata: {data}\n\n"


def _is_langchain_message(event: object) -> bool:
    """Check if object is a LangChain message."""
    return hasattr(event, "content") and hasattr(event, "__class__")


def _is_interrupt_object(event: object) -> bool:
    """Check if object is a LangGraph Interrupt."""
    return (
        hasattr(event, "__class__") and event.__class__.__name__ == INTERRUPT_CLASS_NAME
    )


def _is_pydantic_model(event: object) -> bool:
    """Check if object is a Pydantic model."""
    return hasattr(event, "model_dump")


def _is_dict_like(event: object) -> bool:
    """Check if object has to_dict method."""
    return hasattr(event, "to_dict")


def _serialize_dict(event: dict) -> dict:
    """Serialize dictionary with sensitive data filtering."""
    filtered_event = {}
    for k, v in event.items():
        if k in SENSITIVE_FIELDS:
            continue  # Skip sensitive data entirely
        elif k == "__interrupt__" and isinstance(v, list):
            # Handle interrupt list - serialize each interrupt object completely
            filtered_event[k] = [serialize_event(item) for item in v]
        elif k == "data" and isinstance(v, dict):
            # Recursively filter nested data objects
            filtered_event[k] = _serialize_nested_data(v)
        elif k == "config" and isinstance(v, dict):
            # Ensure config dictionaries preserve JSON boolean values
            filtered_event[k] = _serialize_config_dict(v)
        else:
            filtered_event[k] = serialize_event(v)
    return filtered_event


def _serialize_nested_data(data: dict) -> dict:
    """Serialize nested data objects with filtering."""
    filtered_data = {}
    for data_k, data_v in data.items():
        if data_k in SENSITIVE_FIELDS:
            continue  # Skip sensitive data entirely
        else:
            filtered_data[data_k] = serialize_event(data_v)
    return filtered_data


def _serialize_config_dict(config: dict) -> dict:
    """Serialize config dictionary preserving JSON boolean values."""
    config_dict = {}
    for config_k, config_v in config.items():
        if isinstance(config_v, bool):
            config_dict[config_k] = bool(config_v)  # Ensure JSON boolean
        else:
            config_dict[config_k] = serialize_event(config_v)
    return config_dict


def _serialize_langchain_message(event: object) -> dict:
    """Serialize LangChain message objects."""
    return {
        "type": event.__class__.__name__,
        "content": str(event.content),
        "id": getattr(event, "id", None),
        "tool_calls": getattr(event, "tool_calls", None),
        "tool_call_chunks": getattr(event, "tool_call_chunks", None),
        "invalid_tool_calls": getattr(event, "invalid_tool_calls", None),
    }


def _serialize_generic_object(event: object) -> dict:
    """Serialize generic objects with __dict__."""
    return {k: serialize_event(v) for k, v in event.__dict__.items()}


def _serialize_interrupt_object(event: object) -> dict:
    """Serialize LangGraph Interrupt objects."""
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
                        interrupt_dict[attr_name] = serialize_event(attr_value)
            except Exception:
                continue  # Skip attributes that can't be accessed
    return interrupt_dict


def _serialize_primitive_types(event: object) -> object:
    """Serialize primitive types and handle edge cases."""
    if isinstance(event, bool):
        return bool(event)  # Ensure JSON boolean
    elif event is None:
        return None
    else:
        # Try to convert to string for other types
        return str(event)


def serialize_event(event: object) -> object:
    """Default event serializer that handles various object types."""
    try:
        if isinstance(event, dict):
            return _serialize_dict(event)
        elif _is_pydantic_model(event):
            # Pydantic model - convert to dict and filter
            event_dict = event.model_dump()
            return serialize_event(event_dict)
        elif _is_dict_like(event):
            return serialize_event(event.to_dict())
        elif hasattr(event, "__dict__"):
            if _is_langchain_message(event):
                return _serialize_langchain_message(event)
            else:
                return _serialize_generic_object(event)
        elif isinstance(event, list | tuple):
            return [serialize_event(item) for item in event]
        elif _is_interrupt_object(event):
            return _serialize_interrupt_object(event)
        else:
            return _serialize_primitive_types(event)
    except Exception as e:
        logger.warning(f"Error serializing event: {e}")
        return str(event)


async def stream_events(
    agent: CompiledStateGraph,
    config: dict,
    agent_input: dict,
    resume_input: dict | None = None,
    *,
    serialize_func: Callable[[object], object] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream events with API interruption handling using astream.

    Args:
        agent: Compiled LangGraph agent
        config: Runtime configuration with user context
        agent_input: Input for the agent
        resume_input: Optional resume input if resuming from interrupt
        serialize_func: Function to serialize event data (uses default if None)

    Yields:
        Formatted SSE event strings
    """
    # Use default serializer if none provided
    if serialize_func is None:
        serialize_func = serialize_event

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

                serialized_chunk = serialize_func(chunk)
                if serialized_chunk:
                    # Check if already SSE formatted
                    if isinstance(
                        serialized_chunk, str
                    ) and serialized_chunk.startswith("data: "):
                        yield serialized_chunk
                    else:
                        yield f"data: {json.dumps(serialized_chunk)}\n\n"
        else:
            # Start fresh workflow
            logger.info("Streaming events from workflow start")
            async for chunk in agent.astream(
                agent_input, config, stream_mode=["updates", "messages"]
            ):
                serialized_chunk = serialize_func(chunk)
                if serialized_chunk:
                    # Check if already SSE formatted
                    if isinstance(
                        serialized_chunk, str
                    ) and serialized_chunk.startswith("data: "):
                        yield serialized_chunk
                    else:
                        yield f"data: {json.dumps(serialized_chunk)}\n\n"

    except Exception as e:
        logger.error(f"Error in API event streaming: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def serialize_to_sse(event: object, serialize_func: Callable[[object], object]) -> str:
    """Serialize event to Server-Sent Events format."""
    serialized_event = serialize_func(event)
    return f"data: {json.dumps(serialized_event)}\n\n"
