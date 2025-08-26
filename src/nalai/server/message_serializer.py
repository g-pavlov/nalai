"""
Message serialization utilities for API Assistant server.

This module contains functions for converting LangChain messages to output
message types used in API responses.
"""

import uuid
from typing import Any

from .schemas.messages import (
    AssistantOutputMessage,
    HumanOutputMessage,
    OutputMessage,
    TextContent,
    ToolCall,
    ToolOutputMessage,
)


def convert_messages_to_output(messages: list) -> list[OutputMessage]:
    """Convert LangChain messages to output format."""
    output_messages = []
    for message in messages:
        # Extract metadata fields
        raw_tool_calls = getattr(message, "tool_calls", None)
        invalid_tool_calls = getattr(message, "invalid_tool_calls", None)

        # Extract finish_reason from various possible locations (only for assistant messages)
        finish_reason = _extract_finish_reason(message)

        # Extract usage information from message (only for assistant messages)
        usage = _extract_usage(message)

        # Convert raw tool calls to ToolCall objects
        tool_calls = _convert_tool_calls(raw_tool_calls)

        # Create content blocks
        content_blocks = _create_content_blocks(message)

        # Determine message type and create appropriate output
        message_type = message.__class__.__name__.lower().replace("message", "")

        output_message = _create_output_message(
            message_type, content_blocks, tool_calls, invalid_tool_calls, finish_reason, usage, message
        )

        output_messages.append(output_message)

    return output_messages


def _extract_finish_reason(message: Any) -> str | None:
    """Extract finish_reason from various possible locations in a message."""
    if hasattr(message, "finish_reason") and message.finish_reason is not None:
        return message.finish_reason
    elif hasattr(message, "response_metadata") and message.response_metadata:
        return message.response_metadata.get("finish_reason")
    elif hasattr(message, "additional_kwargs") and message.additional_kwargs:
        return message.additional_kwargs.get("finish_reason")
    return None


def _extract_usage(message: Any) -> dict[str, int]:
    """Extract usage information from a message."""
    if hasattr(message, "usage_metadata") and message.usage_metadata:
        # Convert usage format to standard format
        usage_metadata = message.usage_metadata
        if isinstance(usage_metadata, dict):
            return {
                "prompt_tokens": usage_metadata.get("input_tokens", 0),
                "completion_tokens": usage_metadata.get("output_tokens", 0),
                "total_tokens": usage_metadata.get("total_tokens", 0),
            }
    elif hasattr(message, "usage") and message.usage:
        return message.usage
    else:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def extract_usage_from_messages(messages: list) -> dict[str, int]:
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


def _convert_tool_calls(raw_tool_calls: list | None) -> list[ToolCall] | None:
    """Convert raw tool calls to ToolCall objects."""
    if not raw_tool_calls:
        return None

    tool_calls = []
    for tc in raw_tool_calls:
        tool_calls.append(
            ToolCall(
                id=tc.get("id"), name=tc.get("name"), args=tc.get("args", {})
            )
        )
    return tool_calls


def _create_content_blocks(message: Any) -> list[TextContent]:
    """Create content blocks from message content."""
    content_blocks = []
    if hasattr(message, "content") and message.content:
        content_blocks.append(TextContent(text=str(message.content)))
    return content_blocks


def _create_output_message(
    message_type: str,
    content_blocks: list[TextContent],
    tool_calls: list[ToolCall] | None,
    invalid_tool_calls: list | None,
    finish_reason: str | None,
    usage: dict[str, int],
    message: Any = None,
) -> OutputMessage:
    """Create the appropriate output message based on message type."""
    if message_type == "human":
        return HumanOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
        )
    elif message_type == "ai":
        return AssistantOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
            tool_calls=tool_calls,
            invalid_tool_calls=invalid_tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )
    elif message_type == "tool":
        # Extract tool_call_id for tool messages
        tool_call_id = None
        if message and hasattr(message, "tool_call_id"):
            tool_call_id = message.tool_call_id

        return ToolOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
            tool_call_id=tool_call_id,
        )
    else:
        # Fallback for unknown message types
        return HumanOutputMessage(
            id=str(uuid.uuid4()),
            content=content_blocks,
        )
