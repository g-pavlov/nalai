"""
Data transformation utilities for core package.

This module contains functions for transforming LangGraph/LangChain objects
to internal data models.
"""

import logging
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.messages.tool import ToolMessage
from langgraph.prebuilt.interrupt import HumanInterrupt

from .agent import (
    InterruptChunk,
    Message,
    MessageChunk,
    StreamingChunk,
    ToolCall,
    ToolCallChunk,
    ToolChunk,
    UpdateChunk,
)

logger = logging.getLogger("nalai")

# Type aliases for better readability
LangGraphEvent = tuple[str, Any]  # (event_type, event_data)
MessageInput = BaseMessage | dict  # Can be LangChain message or dict
StreamingChunkInput = (
    LangGraphEvent | BaseMessage | dict
)  # Can be LangGraph event, message, or dict


def transform_message(message: MessageInput) -> Message:
    """Transform message to core model."""
    # Handle dict objects (already in the right format)
    if isinstance(message, dict):
        return Message(**message)

    # Handle message objects
    # Extract all necessary data, no filtering
    message_data = {
        "content": str(message.content),
        "type": message.__class__.__name__.lower().replace("message", ""),
        "id": _safe_getattr(message, "id"),
        "tool_calls": _extract_tool_calls(message),
        "tool_call_chunks": _safe_getattr(message, "tool_call_chunks"),
        "invalid_tool_calls": _safe_getattr(message, "invalid_tool_calls"),
        "response_metadata": _safe_getattr(message, "response_metadata"),
        "usage": _extract_usage(message),
        "finish_reason": _extract_finish_reason(message),
        "tool_call_id": _safe_getattr(message, "tool_call_id"),
    }

    # Pydantic validates and creates the model
    return Message(**message_data)


def transform_streaming_chunk(
    chunk: StreamingChunkInput, conversation_id: str
) -> StreamingChunk | None:
    """Transform streaming chunk to core model with specific chunk types."""

    # Handle tuple-based events from LangGraph with stream_mode=["updates", "messages"]
    if _is_langgraph_event(chunk):
        event_type, event_data = chunk

        if event_type == "updates":
            # Handle updates events
            if not isinstance(event_data, dict):
                logger.warning(
                    "Unexpected updates event data type: %s", type(event_data)
                )
                return None

            # Get the first key-value pair
            if not event_data:
                logger.warning("Empty updates event data")
                return None

            event_key = next(iter(event_data))
            event_value = event_data[event_key]

            # Check if this is an interrupt event
            if event_key == "__interrupt__":
                return _handle_interrupt_update(event_data, conversation_id)

            # Check if this is a tool event (contains ToolMessage)
            if (
                isinstance(event_value, dict)
                and "name" in event_value
                and "tool_call_id" in event_value
            ):
                return _handle_tool_update(event_data, conversation_id)

            # Regular update event
            return _handle_regular_update(event_data, conversation_id)

        elif event_type == "messages":
            # Handle messages events
            if isinstance(event_data, tuple) and len(event_data) == 2:
                message, config = event_data

                # Check if this is a ToolMessage first
                if isinstance(message, ToolMessage):
                    return _handle_tool_message(message, config, conversation_id)

                # Extract message properties directly
                message_data = {
                    "id": getattr(message, "id", ""),
                    "content": str(getattr(message, "content", "")),
                    "additional_kwargs": getattr(message, "additional_kwargs", {}),
                    "usage_metadata": getattr(message, "response_metadata", {}),
                }

                # Check if this is a tool call
                if _is_tool_call_message(message_data):
                    return _handle_tool_call_message(
                        message_data, config, conversation_id
                    )

                # Regular message event
                return _handle_regular_message(message_data, config, conversation_id)
            else:
                logger.warning(
                    "Unexpected messages event data format: %s", type(event_data)
                )
                return None

    # Fallback: handle any other chunk types
    logger.warning("Unexpected streaming chunk type: %s", type(chunk))
    return None


def _is_langgraph_event(chunk: StreamingChunkInput) -> bool:
    """Check if chunk is a LangGraph event tuple."""
    return isinstance(chunk, tuple) and len(chunk) == 2 and isinstance(chunk[0], str)


def _is_tool_call_message(message_data: dict) -> bool:
    """Check if message data contains tool calls."""
    return (
        "additional_kwargs" in message_data
        and message_data["additional_kwargs"]
        and message_data["additional_kwargs"].get("tool_calls", [])
    )


def _handle_interrupt_update(event_data: dict, conversation_id: str) -> InterruptChunk:
    """Handle interrupt update event."""
    interrupt_data = event_data["__interrupt__"]

    # Extract the first interrupt value and parse it
    if isinstance(interrupt_data, tuple) and len(interrupt_data) > 0:
        interrupt_obj = interrupt_data[0]
        if hasattr(interrupt_obj, "value") and interrupt_obj.value:
            normalized_value = HumanInterrupt(**interrupt_obj.value[0])
        else:
            normalized_value = {}
        interrupt_id = getattr(interrupt_obj, "id", "")
    else:
        normalized_value = {}
        interrupt_id = ""

    return InterruptChunk(
        type="interrupt",
        conversation_id=conversation_id,
        id=interrupt_id,
        value=normalized_value,
    )


def _handle_tool_update(updates_data: dict, conversation_id: str) -> ToolChunk:
    """Handle tool update event."""
    event_key = next(iter(updates_data))
    event_data = updates_data[event_key]
    return ToolChunk(
        type="tool",
        conversation_id=conversation_id,
        id=event_data.get("id", ""),
        status=event_data.get("status", "success"),
        tool_call_id=event_data.get("tool_call_id", ""),
        content=event_data.get("content", ""),
        tool_name=event_data.get("name", ""),
    )


def _handle_regular_update(updates_data: dict, conversation_id: str) -> UpdateChunk:
    """Handle regular update event."""
    event_key = next(iter(updates_data))
    event_data = updates_data[event_key]

    # Transform LangChain messages to core Message objects
    messages = []
    for msg in event_data.get("messages", []):
        if isinstance(msg, BaseMessage | dict):
            messages.append(transform_message(msg))

    return UpdateChunk(
        type="update",
        conversation_id=conversation_id,
        task=event_key,
        messages=messages,
    )


def _handle_tool_call_message(
    message_data: dict, config: dict, conversation_id: str
) -> ToolCallChunk:
    """Handle tool call message event."""
    langgraph_node = config.get("langgraph_node", "")
    tool_calls = message_data["additional_kwargs"].get("tool_calls", [])
    return ToolCallChunk(
        type="tool_call",
        conversation_id=conversation_id,
        task=langgraph_node,
        id=message_data.get("id", ""),
        tool_calls=tool_calls,
    )


def _handle_regular_message(
    message_data: dict, config: dict, conversation_id: str
) -> MessageChunk:
    """Handle regular message event."""
    langgraph_node = config.get("langgraph_node", "")
    return MessageChunk(
        type="message",
        conversation_id=conversation_id,
        task=langgraph_node,
        content=message_data.get("content", ""),
        id=message_data.get("id", ""),
        metadata=message_data.get("usage_metadata"),
    )


def _handle_tool_message(
    message: ToolMessage, config: dict, conversation_id: str
) -> ToolChunk:
    """Handle tool message event."""
    return ToolChunk(
        type="tool",
        conversation_id=conversation_id,
        id=message.id,
        status=message.status,
        tool_call_id=message.tool_call_id,
        content=message.content,
        tool_name=message.name,
    )


def _extract_tool_calls(obj: MessageInput) -> list[ToolCall] | None:
    """Extract tool calls from an object."""
    raw_tool_calls = _safe_getattr(obj, "tool_calls")
    if not raw_tool_calls:
        return None

    tool_calls = []
    for tc in raw_tool_calls:
        if isinstance(tc, dict):
            # Ensure required fields are not None
            tool_id = tc.get("id")
            tool_name = tc.get("name")

            # Skip tool calls with missing required fields
            if tool_id is None or tool_name is None:
                continue

            tool_calls.append(
                ToolCall(
                    id=tool_id,
                    name=tool_name,
                    args=tc.get("args", {}),
                    type=tc.get("type"),
                )
            )
        else:
            # Handle tool call objects
            tool_id = getattr(tc, "id", None)
            tool_name = getattr(tc, "name", None)

            # Skip tool calls with missing required fields
            if tool_id is None or tool_name is None:
                continue

            tool_calls.append(
                ToolCall(
                    id=tool_id,
                    name=tool_name,
                    args=getattr(tc, "args", {}),
                    type=getattr(tc, "type", None),
                )
            )

    return tool_calls if tool_calls else None


def _safe_getattr(obj: MessageInput, attr: str, default=None):
    """Safely get attribute value, handling Mock objects."""
    try:
        value = getattr(obj, attr, default)
        # If it's a Mock object, return the default
        if hasattr(value, "_mock_name"):
            return default
        return value
    except Exception:
        return default


def extract_usage_from_messages(messages: list[MessageInput]) -> dict[str, int]:
    """Extract and aggregate usage information from multiple messages."""
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for message in messages:
        usage = _extract_usage(message)
        if usage and isinstance(usage, dict):
            total_prompt_tokens += usage.get("prompt_tokens", 0)
            total_completion_tokens += usage.get("completion_tokens", 0)
            total_tokens += usage.get("total_tokens", 0)

    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
    }


def _extract_usage(obj: MessageInput) -> dict[str, int] | None:
    """Extract usage information from an object."""
    # Try usage_metadata first
    usage_metadata = _safe_getattr(obj, "usage_metadata")
    if usage_metadata and isinstance(usage_metadata, dict):
        return {
            "prompt_tokens": usage_metadata.get("input_tokens", 0),
            "completion_tokens": usage_metadata.get("output_tokens", 0),
            "total_tokens": usage_metadata.get("total_tokens", 0),
        }

    # Try usage attribute
    usage = _safe_getattr(obj, "usage")
    if usage and isinstance(usage, dict):
        return usage

    return None


def _extract_finish_reason(obj: MessageInput) -> str | None:
    """Extract finish_reason from various possible locations in an object."""
    # Try direct finish_reason attribute
    finish_reason = _safe_getattr(obj, "finish_reason")
    if finish_reason is not None:
        return finish_reason

    # Try response_metadata
    response_metadata = _safe_getattr(obj, "response_metadata")
    if response_metadata and isinstance(response_metadata, dict):
        return response_metadata.get("finish_reason")

    # Try additional_kwargs
    additional_kwargs = _safe_getattr(obj, "additional_kwargs")
    if additional_kwargs and isinstance(additional_kwargs, dict):
        return additional_kwargs.get("finish_reason")

    return None
