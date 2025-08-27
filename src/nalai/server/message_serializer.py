"""
Message serialization utilities for API Assistant server.

This module contains functions for converting LangChain messages to output
message types used in API responses.
"""

import uuid
from typing import Any

from langchain_core.messages import BaseMessage

from ..core.agent import Message
from .schemas.messages import (
    AssistantOutputMessage,
    HumanOutputMessage,
    OutputMessage,
    TextContent,
    ToolOutputMessage,
)


def _safe_getattr(obj: Any, attr: str, default=None):
    """Safely get attribute value, handling Mock objects."""
    try:
        value = getattr(obj, attr, default)
        # If it's a Mock object, return the default
        if hasattr(value, "_mock_name"):
            return default
        return value
    except Exception:
        return default


def _extract_tool_calls(obj: Any) -> list[dict] | None:
    """Extract tool calls from an object."""
    raw_tool_calls = _safe_getattr(obj, "tool_calls")
    if not raw_tool_calls:
        return None

    tool_calls = []
    for tc in raw_tool_calls:
        if isinstance(tc, dict):
            tool_calls.append(
                {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "args": tc.get("args", {}),
                }
            )
        else:
            # Handle tool call objects
            tool_calls.append(
                {
                    "id": getattr(tc, "id", None),
                    "name": getattr(tc, "name", None),
                    "args": getattr(tc, "args", {}),
                }
            )

    return tool_calls


def _extract_usage(obj: Any) -> dict[str, int] | None:
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


def _extract_finish_reason(obj: Any) -> str | None:
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


def transform_message(message: Any) -> Message:
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


def serialize_for_json_response(core_message: Message) -> OutputMessage:
    """Convert core message model to JSON API response format."""
    # Create content blocks
    content_blocks = [TextContent(text=core_message.content)]

    # Convert tool calls to API format
    api_tool_calls = None
    if core_message.tool_calls:
        api_tool_calls = []
        for tc in core_message.tool_calls:
            api_tool_calls.append({"id": tc.id, "name": tc.name, "args": tc.args})

    # Create appropriate output message based on type
    if core_message.type == "human":
        return HumanOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
        )
    elif core_message.type == "ai":
        return AssistantOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
            tool_calls=api_tool_calls,
            invalid_tool_calls=core_message.invalid_tool_calls,
            finish_reason=core_message.finish_reason,
            usage=core_message.usage
            or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
    elif core_message.type == "tool":
        return ToolOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
            tool_call_id=core_message.tool_call_id or "",
        )
    else:
        # Fallback for unknown message types
        return HumanOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
        )


def serialize_messages_for_json_response(
    core_messages: list[Message],
) -> list[OutputMessage]:
    """Convert multiple core messages to JSON API response format."""
    return [serialize_for_json_response(msg) for msg in core_messages]


def convert_messages_to_output(
    messages: list[BaseMessage | Message],
) -> list[OutputMessage]:
    """Convert messages to output format.

    Args:
        messages: List of either LangChain messages or core Message models

    Returns:
        List of OutputMessage objects for API responses
    """
    # Transform to core models if needed
    core_messages = []
    for message in messages:
        if isinstance(message, Message):
            # Already a core model
            core_messages.append(message)
        else:
            # LangChain message - transform to core model
            core_message = transform_message(message)
            core_messages.append(core_message)

    # Serialize core models to API response format
    return serialize_messages_for_json_response(core_messages)


def extract_usage_from_core_messages(messages: list[Message]) -> dict[str, int]:
    """Extract and aggregate usage information from core message models."""
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for message in messages:
        if (
            hasattr(message, "usage")
            and message.usage
            and isinstance(message.usage, dict)
        ):
            total_prompt_tokens += message.usage.get("prompt_tokens", 0)
            total_completion_tokens += message.usage.get("completion_tokens", 0)
            total_tokens += message.usage.get("total_tokens", 0)

    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
    }
