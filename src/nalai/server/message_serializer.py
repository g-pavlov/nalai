"""
Message serialization utilities for API Assistant server.

This module transforms core Message objects to JSON response format
that complies with the schema defined in messages.py.
"""

import logging
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage

from .schemas.messages import (
    AssistantOutputMessage,
    OutputMessage,
    TextContent,
    ToolOutputMessage,
)

if TYPE_CHECKING:
    from ..core.agent import Message

logger = logging.getLogger("nalai")


def serialize_for_json_response(
    core_message: "Message", run_id: str, message_index: int
) -> OutputMessage:
    """
    Convert core Message model to JSON API response format.

    This function transforms core messages to output messages that will be
    included in the MessageResponse. Only messages that constitute the
    current response should be included, not conversation history.
    """
    # Create content blocks from message content
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

    # Convert tool calls to API format for assistant messages
    api_tool_calls = None
    if core_message.tool_calls:
        api_tool_calls = []
        for tc in core_message.tool_calls:
            api_tool_calls.append({"id": tc.id, "name": tc.name, "args": tc.args})

    # Determine the appropriate message ID based on message type
    if core_message.type == "human":
        # Human messages should not be included in responses
        # They are part of conversation history, not the current response
        raise ValueError("Human messages should not be serialized for responses")
    else:
        # AI and Tool messages: Use run-scoped IDs
        message_id = f"{run_id}-{message_index}"

    # Create appropriate output message based on type
    if core_message.type == "ai":
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
        # CRITICAL: Ensure 1:1 parity with SSE ResponseToolEvent structure
        # Tool messages must have the same fields as response.tool events

        # Extract tool information directly from the core message structure
        # The data should be in response_metadata or not at all
        tool_name = None
        status = None
        args = None

        for tc in api_tool_calls:
            if core_message.tool_call_id == tc["id"]:
                tool_name = tc.get("name")
                status = core_message.status
                args = tc.get("args")
                break

        # If the core message doesn't have the required fields, that's a data issue
        # Don't try to guess or infer - let the validation fail
        if not tool_name or not status:
            logger.warning(
                f"Tool message missing required fields: tool_name={tool_name}, status={status}"
            )

        return ToolOutputMessage(
            id=message_id,
            content=content_blocks,
            tool_call_id=core_message.tool_call_id or "",
            tool_name=tool_name,
            status=status,
            args=args,
        )
    else:
        # Fallback for unknown message types
        raise ValueError(f"Unknown message type: {core_message.type}")


def serialize_messages_for_json_response(
    core_messages: list["Message"], run_id: str
) -> list[OutputMessage]:
    """
    Convert multiple core messages to JSON API response format.

    This function filters and transforms only the messages that constitute
    the current response, excluding conversation history.
    """
    response_messages = []

    for index, msg in enumerate(core_messages):
        try:
            # Only include messages that are part of the current response
            # Skip human messages (conversation history)
            if msg.type != "human":
                output_message = serialize_for_json_response(msg, run_id, index)
                response_messages.append(output_message)
        except ValueError as e:
            # Log and skip messages that can't be serialized
            logger.warning(f"Skipping message {msg.id}: {e}")
            continue

    return response_messages


def convert_messages_to_output(
    messages: list["BaseMessage | Message"], run_id: str
) -> list[OutputMessage]:
    """
    Convert messages to output format for JSON responses.

    This function transforms either LangChain messages or core Message models
    to the output format expected by the MessageResponse schema.

    Args:
        messages: List of either LangChain messages or core Message models
        run_id: Run ID to scope AI and tool messages in this response

    Returns:
        List of OutputMessage objects for API responses
    """
    # Import here to avoid circular imports
    from ..core.lc_transformers import transform_message

    # Transform to core models if needed
    core_messages = []
    for message in messages:
        if hasattr(message, "type") and message.type:  # Core Message model
            core_messages.append(message)
        else:
            # LangChain message - transform to core model with run_id
            core_message = transform_message(message, run_id)
            core_messages.append(core_message)

    # Serialize core models to API response format
    return serialize_messages_for_json_response(core_messages, run_id)


def extract_usage_from_core_messages(messages: list["Message"]) -> dict[str, int]:
    """
    Extract and aggregate usage information from core message models.

    This function calculates total token usage across all messages
    in the current response.
    """
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
