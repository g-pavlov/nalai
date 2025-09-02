"""
Message serialization utilities for API Assistant server.

This module transforms core Message objects to JSON response format
that complies with the schema defined in messages.py.
"""

import logging
from datetime import UTC, datetime

from ..core.agent import ConversationInfo, Message
from .schemas.conversations import LoadConversationResponse
from .schemas.messages import (
    AssistantOutputMessage,
    Interrupt,
    MessageResponse,
    OutputMessage,
    ResponseMetadata,
    TextContent,
    ToolOutputMessage,
)

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
    # All message types use run-scoped IDs
    message_id = f"{run_id}-{message_index}"

    # Create appropriate output message based on type
    if core_message.type == "human":
        from .schemas.messages import HumanOutputMessage

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
        # Extract tool information directly from the core message structure
        # Tool messages have tool_calls populated with execution details
        if not core_message.tool_calls:
            raise ValueError(f"Tool message {core_message.id} has no tool_calls data")

        # Get the first (and should be only) tool call
        tool_call = core_message.tool_calls[0]
        tool_name = tool_call.name
        status = core_message.status or "completed"
        args = tool_call.args

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


def serialize_messages(
    core_messages: list["Message"], run_id: str
) -> list[OutputMessage]:
    """
    Convert multiple core messages to JSON API response format.

    This function performs pure serialization without filtering.
    Filtering should be done before calling this function.
    """
    response_messages = []

    for index, msg in enumerate(core_messages):
        try:
            output_message = serialize_for_json_response(msg, run_id, index)
            response_messages.append(output_message)
        except ValueError as e:
            # Log and skip messages that can't be serialized
            logger.warning(f"Skipping message {msg.id}: {e}")
            continue

    return response_messages


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


def serialize_conversation(
    conversation_info: ConversationInfo,
    messages: list[Message],
) -> LoadConversationResponse:
    """Serialize conversation to output format for JSON responses."""

    conversation_id = conversation_info.conversation_id
    if not conversation_id:
        raise ValueError("Conversation ID is required")

    output_messages = serialize_messages(messages, conversation_id)

    return LoadConversationResponse(
        conversation_id=conversation_info.conversation_id,
        messages=output_messages,
        created_at=conversation_info.created_at,
        last_updated=conversation_info.last_accessed,
        status=conversation_info.status,
    )


def serialize_message_response(
    messages: list[Message],
    run_id: str,
    conversation_info: ConversationInfo,
    previous_response_id: str | None,
    status: str,
    interrupts_list: list[Interrupt] | None,
) -> MessageResponse:
    """Serialize message response to output format for JSON responses."""

    # Create response output with run-scoped IDs
    output_messages = serialize_messages(messages, run_id)

    response_data = {
        "id": run_id,
        "conversation_id": conversation_info.conversation_id,
        "previous_response_id": previous_response_id,
        "output": output_messages,
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "interrupts": interrupts_list if interrupts_list else None,
        "metadata": None,
        "usage": extract_usage_from_core_messages(messages),
    }

    return MessageResponse(**response_data)


def serialize_error_response(
    error: Exception,
    run_id: str,
    conversation_id: str | None,
    previous_response_id: str | None,
) -> MessageResponse:
    """Serialize error response to output format for JSON responses."""

    # Create a placeholder error message to satisfy the schema requirement
    error_message = {
        "id": f"msg_{run_id.replace('run_', '')}",
        "role": "assistant",
        "content": [{"type": "text", "text": f"Error: {str(error)}"}],
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

    response_data = {
        "id": run_id,
        "conversation_id": conversation_id,
        "previous_response_id": previous_response_id,
        "output": [error_message],
        "created_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "interrupts": None,
        "metadata": ResponseMetadata(error=str(error)),
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

    return MessageResponse(**response_data)
