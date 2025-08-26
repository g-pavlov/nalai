"""
Event serialization utilities for core package.

This module contains functions for processing and serializing events
from the agent, including specialized handlers for different event types.
"""

import logging

logger = logging.getLogger("nalai")

# Constants
SENSITIVE_FIELDS = {"api_specs", "api_summaries"}
INTERRUPT_CLASS_NAME = "Interrupt"

# LangGraph-specific sensitive fields that should be filtered from streaming chunks
LANGGRAPH_SENSITIVE_FIELDS = {
    "auth_token",
    "user_id",
    "user_email",
    "org_unit_id",
    "langgraph_step",
    "langgraph_node",
    "langgraph_triggers",
    "langgraph_path",
    "langgraph_checkpoint_ns",
    "checkpoint_ns",
    "ls_provider",
    "ls_model_name",
    "ls_model_type",
    "ls_temperature",
    "thread_id",
    "cache_disabled",
    "disable_cache",
}

# Fields that indicate meaningful content in LangGraph chunks
LANGGRAPH_MEANINGFUL_FIELDS = {
    "messages",
    "selected_apis",
    "cache_miss",
    "updates",
    "content",
}


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
        if config_k in SENSITIVE_FIELDS:
            continue  # Skip sensitive data entirely
        elif isinstance(config_v, bool):
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


def filter_langgraph_streaming_chunk(
    chunk: object, conversation_id: str
) -> object | None:
    """
    Filter LangGraph streaming chunks for client consumption.

    This function consolidates the filtering logic previously in LangGraphAgent
    and removes sensitive LangGraph-specific fields while preserving meaningful content.

    Args:
        chunk: The raw LangGraph chunk to filter
        conversation_id: The conversation ID to add to filtered chunks

    Returns:
        Filtered chunk with conversation context, or None if should be skipped
    """
    # For message chunks with content, always preserve them and filter sensitive fields
    if hasattr(chunk, "content") and hasattr(chunk, "type"):
        # Create a clean message object with conversation context
        filtered_message = {
            "content": chunk.content,
            "type": chunk.type,
            "id": getattr(chunk, "id", None),
            "conversation": conversation_id,
        }

        # Add tool calls if present
        if hasattr(chunk, "tool_calls") and chunk.tool_calls:
            filtered_message["tool_calls"] = chunk.tool_calls

        # Add tool call chunks if present
        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
            filtered_message["tool_call_chunks"] = chunk.tool_call_chunks

        # Add invalid tool calls if present
        if hasattr(chunk, "invalid_tool_calls") and chunk.invalid_tool_calls:
            filtered_message["invalid_tool_calls"] = chunk.invalid_tool_calls

        # Add response metadata if present
        if hasattr(chunk, "response_metadata") and chunk.response_metadata:
            filtered_message["response_metadata"] = chunk.response_metadata

        return filtered_message

    # For update chunks with meaningful data, preserve them and filter sensitive fields
    if hasattr(chunk, "__dict__"):
        # Check if this chunk has meaningful content (not just internal state)
        has_meaningful_content = any(
            hasattr(chunk, field) and getattr(chunk, field) is not None
            for field in LANGGRAPH_MEANINGFUL_FIELDS
        )

        if has_meaningful_content:
            filtered_dict = {}
            for key, value in chunk.__dict__.items():
                # Skip sensitive fields but preserve meaningful content
                if key in LANGGRAPH_SENSITIVE_FIELDS:
                    continue

                # Add conversation context
                if key == "conversation":
                    filtered_dict[key] = conversation_id
                else:
                    filtered_dict[key] = value

            if filtered_dict:
                filtered_dict["conversation"] = conversation_id
                return filtered_dict
        else:
            # Skip chunks that are purely internal state
            if any(hasattr(chunk, field) for field in LANGGRAPH_SENSITIVE_FIELDS):
                return None

    # For dictionary chunks, preserve meaningful content and filter sensitive fields
    if isinstance(chunk, dict):
        # Check if this dict has meaningful content
        has_meaningful_content = any(
            key in chunk for key in LANGGRAPH_MEANINGFUL_FIELDS
        )

        if has_meaningful_content:
            filtered_dict = {}
            for key, value in chunk.items():
                # Skip sensitive fields but preserve meaningful content
                if key in LANGGRAPH_SENSITIVE_FIELDS:
                    continue

                filtered_dict[key] = value

            if filtered_dict:
                filtered_dict["conversation"] = conversation_id
                return filtered_dict
        else:
            # Skip dicts that are purely internal state
            if any(key in chunk for key in LANGGRAPH_SENSITIVE_FIELDS):
                return None

    # For other objects, try to add conversation context if they have meaningful content
    if hasattr(chunk, "__dict__"):
        # Check if this object has meaningful content
        has_meaningful_content = any(
            hasattr(chunk, field) and getattr(chunk, field) is not None
            for field in LANGGRAPH_MEANINGFUL_FIELDS
        )

        if has_meaningful_content:
            # Create a copy with conversation context
            filtered_chunk = type(chunk)()
            for key, value in chunk.__dict__.items():
                if key in LANGGRAPH_SENSITIVE_FIELDS:
                    continue
                setattr(filtered_chunk, key, value)

            # Add conversation context
            filtered_chunk.conversation = conversation_id
            return filtered_chunk
        else:
            # Skip objects that are purely internal state
            if any(hasattr(chunk, field) for field in LANGGRAPH_SENSITIVE_FIELDS):
                return None

    return None


def serialize_langgraph_streaming_chunk(
    chunk: object, conversation_id: str
) -> object | None:
    """
    Filter and serialize a LangGraph streaming chunk for client consumption.

    This is a convenience function that combines filtering and serialization
    for LangGraph streaming chunks.

    Args:
        chunk: The raw LangGraph chunk to process
        conversation_id: The conversation ID to add to filtered chunks

    Returns:
        Serialized chunk ready for client consumption, or None if should be skipped
    """
    filtered_chunk = filter_langgraph_streaming_chunk(chunk, conversation_id)
    if filtered_chunk:
        return serialize_event(filtered_chunk)
    return None
