"""
Message serialization utilities for API Assistant server.

This module contains functions for converting between different message formats
and serializing messages for API responses.
"""

import logging
from typing import Any

from langchain_core.messages import BaseMessage

from ..core.agent import Message
from ..utils.id_generator import generate_message_id
from .schemas.messages import (
    AssistantOutputMessage,
    HumanOutputMessage,
    OutputMessage,
    TextContent,
    ToolOutputMessage,
)

logger = logging.getLogger("nalai")


def _safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get attribute from object, returning default if not found."""
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def _extract_tool_calls(message: BaseMessage) -> list[dict] | None:
    """Extract tool calls from message."""
    tool_calls = _safe_getattr(message, "tool_calls")
    if not tool_calls:
        return None

    result = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            result.append(tc)
        else:
            # Handle tool call objects
            result.append(
                {
                    "id": _safe_getattr(tc, "id"),
                    "name": _safe_getattr(tc, "name"),
                    "args": _safe_getattr(tc, "args", {}),
                }
            )

    return result if result else None


def _extract_usage(message: BaseMessage) -> dict[str, int] | None:
    """Extract usage information from message."""
    # Check usage attribute first
    usage = _safe_getattr(message, "usage")
    if usage:
        if isinstance(usage, dict):
            return usage
        # Handle usage objects
        return {
            "prompt_tokens": _safe_getattr(usage, "prompt_tokens", 0),
            "completion_tokens": _safe_getattr(usage, "completion_tokens", 0),
            "total_tokens": _safe_getattr(usage, "total_tokens", 0),
        }

    # Check usage_metadata
    usage_metadata = _safe_getattr(message, "usage_metadata")
    if usage_metadata and isinstance(usage_metadata, dict):
        return {
            "prompt_tokens": usage_metadata.get("input_tokens", 0),
            "completion_tokens": usage_metadata.get("output_tokens", 0),
            "total_tokens": usage_metadata.get("total_tokens", 0),
        }

    return None


def _extract_finish_reason(message: BaseMessage) -> str | None:
    """Extract finish reason from message."""
    # Check direct finish_reason attribute first
    finish_reason = _safe_getattr(message, "finish_reason")
    if finish_reason:
        return finish_reason

    # Check response_metadata
    response_metadata = _safe_getattr(message, "response_metadata")
    if response_metadata and isinstance(response_metadata, dict):
        finish_reason = response_metadata.get("finish_reason")
        if finish_reason:
            return finish_reason

    # Check additional_kwargs
    additional_kwargs = _safe_getattr(message, "additional_kwargs")
    if additional_kwargs and isinstance(additional_kwargs, dict):
        finish_reason = additional_kwargs.get("finish_reason")
        if finish_reason:
            return finish_reason

    return None


def transform_message(message: BaseMessage, run_id: str | None = None) -> Message:
    """Transform LangChain message to core Message model with consistent ID handling."""
    # Import here to avoid circular imports
    from ..core.lc_transformers import transform_message as core_transform_message

    return core_transform_message(message, run_id)


def _is_domain_prefixed_format(id_str: str) -> bool:
    """
    Check if ID follows basic domain-prefixed format (more lenient than strict validation).

    Args:
        id_str: ID string to check

    Returns:
        True if follows basic domain-prefixed pattern
    """
    if not id_str or not isinstance(id_str, str):
        return False

    if "_" not in id_str:
        return False

    domain, base62_part = id_str.split("_", 1)

    from ..utils.id_generator import DomainPrefix

    if domain not in DomainPrefix.__args__:  # type: ignore
        return False

    if not base62_part:
        return False

    from ..utils.id_generator import BASE62_ALPHABET

    for char in base62_part:
        if char not in BASE62_ALPHABET:
            return False

    return True


def serialize_for_json_response(
    core_message: Message, run_id: str, message_index: int
) -> OutputMessage:
    """Convert core message model to JSON API response format with consistent ID handling."""
    # Create content blocks - handle empty content for tool calls
    content_blocks = []
    if core_message.content and core_message.content.strip():
        content_blocks = [TextContent(text=core_message.content)]
    elif core_message.type == "ai" and core_message.tool_calls:
        # For AI messages with tool calls but no content, use a placeholder
        content_blocks = [TextContent(text="I'll help you with that request.")]
    elif core_message.type == "tool":
        # For tool messages, we need some content
        content_blocks = [
            TextContent(text=core_message.content or "Tool execution completed.")
        ]
    else:
        # For other cases with empty content, use a placeholder
        content_blocks = [TextContent(text="Message processed.")]

    # Convert tool calls to API format
    api_tool_calls = None
    if core_message.tool_calls:
        api_tool_calls = []
        for tc in core_message.tool_calls:
            api_tool_calls.append({"id": tc.id, "name": tc.name, "args": tc.args})

    # Determine the appropriate message ID based on message type
    if core_message.type == "human":
        # Human messages: Use msg_ prefix (preserve existing or generate new)
        if core_message.id.startswith("msg_"):
            message_id = core_message.id  # Preserve existing msg_ ID
        else:
            message_id = generate_message_id()  # Generate new msg_ ID
    else:
        # AI and Tool messages: Use run-scoped IDs
        message_id = f"{run_id}-{message_index}"

    # Create appropriate output message based on type
    if core_message.type == "human":
        return HumanOutputMessage(
            id=message_id,
            content=content_blocks,
        )
    elif core_message.type == "ai":
        return AssistantOutputMessage(
            id=message_id,
            content=content_blocks,
            tool_calls=api_tool_calls,
            invalid_tool_calls=core_message.invalid_tool_calls,
            finish_reason=core_message.finish_reason,
            usage=core_message.usage
            or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
    elif core_message.type == "tool":
        return ToolOutputMessage(
            id=message_id,
            content=content_blocks,
            tool_call_id=core_message.tool_call_id or "",
        )
    else:
        # Fallback for unknown message types
        return HumanOutputMessage(
            id=message_id,
            content=content_blocks,
        )


def serialize_messages_for_json_response(
    core_messages: list[Message], run_id: str
) -> list[OutputMessage]:
    """Convert multiple core messages to JSON API response format with consistent ID handling."""
    return [
        serialize_for_json_response(msg, run_id, index)
        for index, msg in enumerate(core_messages)
    ]


def convert_messages_to_output(
    messages: list[BaseMessage | Message], run_id: str
) -> list[OutputMessage]:
    """Convert messages to output format with consistent ID handling.

    Args:
        messages: List of either LangChain messages or core Message models
        run_id: Run ID to scope AI and tool messages in this response

    Returns:
        List of OutputMessage objects for API responses with consistent ID handling
    """
    # Transform to core models if needed
    core_messages = []
    for message in messages:
        if isinstance(message, Message):
            # Already a core model
            core_messages.append(message)
        else:
            # LangChain message - transform to core model with run_id
            core_message = transform_message(message, run_id)
            core_messages.append(core_message)

    # Serialize core models to API response format with consistent ID handling
    return serialize_messages_for_json_response(core_messages, run_id)


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


def extract_usage_from_streaming_chunks(chunks: list) -> dict[str, int]:
    """Extract and aggregate usage information from streaming chunks."""
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for chunk in chunks:
        if hasattr(chunk, "usage") and chunk.usage and isinstance(chunk.usage, dict):
            total_prompt_tokens += chunk.usage.get("prompt_tokens", 0)
            total_completion_tokens += chunk.usage.get("completion_tokens", 0)
            total_tokens += chunk.usage.get("total_tokens", 0)

    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
    }
