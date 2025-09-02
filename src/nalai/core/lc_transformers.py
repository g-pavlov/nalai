"""
Data transformation utilities for core package.

This module contains functions for transforming LangGraph/LangChain objects
to internal data models.
"""

import logging
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.messages.tool import ToolMessage

from ..config import ExecutionContext, ToolCallMetadata
from ..utils.id_generator import generate_message_id, generate_run_id
from .agent import (
    InterruptChunk,
    Message,
    MessageChunk,
    StreamingChunk,
    ToolCallChunk,
    ToolCallUpdateChunk,
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


def transform_message(
    message: MessageInput,
    run_id: str | None = None,
    config: dict | None = None,
    conversation_id: str | None = None,
) -> Message:
    """Transform message to core model with consistent ID handling."""
    # Handle dict objects (already in the right format)
    if isinstance(message, dict):
        return Message(**message)

    # Handle message objects
    # Extract existing ID
    message_id = _safe_getattr(message, "id")

    # Determine the appropriate ID based on message type and our consistency rules
    final_message_id = _determine_message_id(message, message_id, run_id)

    message_data = {
        "content": str(message.content),
        "type": message.__class__.__name__.lower().replace("message", ""),
        "id": final_message_id,
        "tool_calls": _extract_tool_calls(message),
        "tool_call_chunks": _safe_getattr(message, "tool_call_chunks"),
        "invalid_tool_calls": _safe_getattr(message, "invalid_tool_calls"),
        "response_metadata": _safe_getattr(message, "response_metadata"),
        "usage": _extract_usage(message),
        "finish_reason": _extract_finish_reason(message),
        "tool_call_id": _safe_getattr(message, "tool_call_id"),
        "status": _safe_getattr(message, "status"),
    }

    if message_data["type"] == "tool":
        tool_chunk = _handle_tool_message(message, config, conversation_id)
        if tool_chunk:
            message_data["content"] = tool_chunk.content
            message_data["tool_calls"] = [
                {
                    "id": tool_chunk.tool_call_id,
                    "name": tool_chunk.tool_name,
                    "args": tool_chunk.args,
                }
            ]
    # Pydantic validates and creates the model
    return Message(**message_data)


def _determine_message_id(
    message: BaseMessage, existing_id: str | None, run_id: str | None
) -> str:
    """
    Determine the appropriate message ID based on our consistency rules.

    Rules:
    1. Human messages: Always use msg_ prefix (preserve if already msg_, generate if not)
    2. AI/Tool messages: Always use run_ prefix for consistency (use run_id with index if provided, otherwise generate run_ ID)
    """
    message_type = message.__class__.__name__.lower().replace("message", "")

    if message_type == "human":
        # Human messages: Always use msg_ prefix
        if (
            existing_id
            and _is_domain_prefixed_format(existing_id)
            and existing_id.startswith("msg_")
        ):
            # Already has our msg_ format, preserve it
            return existing_id
        else:
            # Generate new msg_ ID
            return generate_message_id()

    elif message_type in ["ai", "tool"]:
        # AI and Tool messages: Always use run_ prefix for consistency
        if run_id:
            # Use run_id directly - it should already be in the correct format
            return run_id
        else:
            # No run_id provided, generate a run_ ID to maintain consistency
            return generate_run_id()

    else:
        # Unknown message type, generate msg_ ID
        return generate_message_id()


def transform_streaming_chunk(
    chunk: StreamingChunkInput, conversation_id: str
) -> StreamingChunk | None:
    """Transform streaming chunk to core model with specific chunk types."""

    # Handle tuple-based events from LangGraph with stream_mode=["updates", "messages"]
    if _is_langgraph_event(chunk):
        event_type, event_data = chunk

        if event_type == "updates":
            if not isinstance(event_data, dict):
                logger.warning(
                    "Unexpected updates event data type: %s", type(event_data)
                )
                return None

            if not event_data:
                logger.warning("Empty updates event data")
                return None

            if _is_interrupt_update_event(event_data):
                return _handle_interrupt_update(event_data, conversation_id)

            if _is_tool_call_update_event(event_data):
                return _handle_tool_call_update(event_data, conversation_id)

            if _is_tool_update_event(event_data):
                return _handle_tool_update(event_data, conversation_id)

            return _handle_regular_update(event_data, conversation_id)

        elif event_type == "messages":
            # Handle messages events
            if isinstance(event_data, tuple) and len(event_data) == 2:
                message, config = event_data

                # Check if this is a ToolMessage first
                if _is_tool_message(message):
                    return _handle_tool_message(message, config, conversation_id)

                # Extract message properties directly
                message_data = {
                    "id": getattr(message, "id", ""),
                    "content": str(getattr(message, "content", "")),
                    "additional_kwargs": getattr(message, "additional_kwargs", {}),
                    "response_metadata": getattr(message, "response_metadata", {}),
                    "usage_metadata": getattr(message, "usage_metadata", {}),
                    "finish_reason": getattr(message, "finish_reason", None),
                    "tool_calls": getattr(message, "tool_calls", []),
                    "invalid_tool_calls": getattr(message, "invalid_tool_calls", []),
                    "tool_call_chunks": getattr(message, "tool_call_chunks", []),
                    "tool_call_id": getattr(message, "tool_call_id", None),
                }

                # Check if this is a tool call message
                if _is_tool_call_message(message):
                    return _handle_tool_call_message(
                        message_data, config, conversation_id
                    )

                # Regular message event
                return _handle_regular_message(message_data, config, conversation_id)

            # # Handle single message
            # elif isinstance(event_data, BaseMessage):
            #     # Transform to core message model
            #     core_message = transform_message(event_data, config, conversation_id)
            #     return MessageChunk(**core_message.model_dump())

    logger.warning("Unrecognized chunk type: %s", type(chunk))
    return None


def _is_langgraph_event(chunk: Any) -> bool:
    """Check if chunk is a LangGraph event tuple."""
    return isinstance(chunk, tuple) and len(chunk) == 2


def _is_tool_call_update_event(event_data: dict) -> bool:
    """Check if event data contains tool calls."""
    event_key = next(iter(event_data.keys()))
    messages = event_data[event_key].get("messages", [])
    if not messages:
        return False

    # Check only the last message in the array
    last_message = messages[-1]
    if isinstance(last_message, AIMessage):
        if last_message.tool_calls:
            return True
    return False


def _is_tool_update_event(event_data: dict) -> bool:
    """Check if event data is a tool update event."""
    event_value = next(iter(event_data.values()))
    return (
        isinstance(event_value, dict)
        and "name" in event_value
        and "tool_call_id" in event_value
    )


def _is_interrupt_update_event(event_data: dict) -> bool:
    """Check if event data is an interrupt update event."""
    event_key = next(iter(event_data.keys()))
    return event_key == "__interrupt__"


def _handle_tool_call_update(
    event_data: dict, conversation_id: str
) -> ToolCallUpdateChunk | None:
    """Handle tool call update events."""
    try:
        event_key = next(iter(event_data.keys()))
        messages = event_data[event_key].get("messages", [])
        if not messages:
            return None

        # Check only the last message in the array
        last_message = messages[-1]
        if isinstance(last_message, AIMessage):
            if last_message.tool_calls:
                return ToolCallUpdateChunk(
                    id=last_message.id,
                    conversation_id=conversation_id,
                    task=event_key,
                    tool_calls=last_message.tool_calls,
                )
        return None
    except Exception as e:
        logger.error("Error handling tool call update: %s", e)
        return None


def _handle_interrupt_update(
    event_data: dict, conversation_id: str
) -> InterruptChunk | None:
    """Handle interrupt update events."""
    try:
        interrupt = event_data.get("__interrupt__", {})
        # Handle interrupt_data as tuple (normative case)
        if not isinstance(interrupt, tuple):
            raise ValueError("Interrupt must be a tuple")
        if len(interrupt) < 1:
            raise ValueError("Interrupt elements must be > 0")
        if len(interrupt[0].value) < 1:
            raise ValueError("Interrupt value lenght must be > 0")
        if not isinstance(interrupt[0].value[0], dict):
            raise ValueError("Interrupt value must be a dict")
        interrupt_values = interrupt[0].value
        interrupt_id = interrupt[0].id
        return InterruptChunk(
            id=interrupt_id,
            values=interrupt_values,
            conversation_id=conversation_id,
        )
    except Exception as e:
        logger.error("Error handling interrupt update: %s", e)
        return None


def _handle_tool_update(event_data: dict, conversation_id: str) -> ToolChunk | None:
    """Handle tool update events."""
    try:
        tool_data = next(iter(event_data.values()))
        return ToolChunk(
            tool_call_id=tool_data.get("tool_call_id", ""),
            tool_name=tool_data.get("name", ""),
            status=tool_data.get("status"),
            content=tool_data.get("content", ""),
            conversation_id=conversation_id,
        )
    except Exception as e:
        logger.error("Error handling tool update: %s", e)
        return None


def _handle_regular_update(
    event_data: dict, conversation_id: str
) -> UpdateChunk | None:
    """Handle regular update events."""
    try:
        return UpdateChunk(
            task=next(iter(event_data.keys())),
            messages=event_data.get("messages", []),
            conversation_id=conversation_id,
        )
    except Exception as e:
        logger.error("Error handling regular update: %s", e)
        return None


def _handle_tool_message(
    message: ToolMessage, config: dict, conversation_id: str
) -> ToolChunk | None:
    """Handle ToolMessage events with execution context enrichment."""
    try:
        tc_meta = None
        content = message.content

        # Check for structured metadata in content. Tool wrappers use this format.
        if hasattr(message, "content") and message.content:
            content_dict = None

            # Try to parse JSON string or use dict directly
            if isinstance(message.content, str):
                try:
                    import json

                    content_dict = json.loads(message.content)
                except (json.JSONDecodeError, ValueError):
                    pass
            elif isinstance(message.content, dict):
                content_dict = message.content

            # Extract from structured metadata format if found
            if content_dict:
                content = content_dict.get("tool_response", message.content)
                # Try to enrich with metadata from execution context first (non-interrupted flows)
                exec_ctx_dict = content_dict.get("execution_context", {})
                if exec_ctx_dict.get("args") is not None:
                    tc_meta = ToolCallMetadata(**exec_ctx_dict)
                elif exec_ctx_dict.get("tool_calls") is not None:
                    exec_ctx = ExecutionContext(**exec_ctx_dict)
                    # Look for execution context structure in content
                    if exec_ctx.tool_calls:
                        try:
                            # Find matching tool call by args
                            for tc_meta in exec_ctx.tool_calls.values():
                                tc_meta = tc_meta
                                break
                        except Exception as e:
                            logger.debug(
                                f"Failed to parse execution context from content: {e}"
                            )

        return ToolChunk(
            id=message.tool_call_id or "",
            tool_call_id=message.tool_call_id or "",
            tool_name=tc_meta.name if tc_meta else "",
            # status=tc_meta.status if tc_meta else "unknown",
            content=content,
            args=tc_meta.args if tc_meta else {},
            conversation_id=conversation_id,
        )
    except Exception as e:
        logger.error("Error handling tool message: %s", e)
        return None


def _is_tool_message(message: object) -> bool:
    """Check if message is a ToolMessage."""
    return isinstance(message, ToolMessage)


def _is_tool_call_message(message: object) -> bool:
    """Check if message data contains tool calls."""
    return isinstance(message, AIMessageChunk) and message.tool_call_chunks


def _handle_tool_call_message(
    message_data: dict, config: dict, conversation_id: str
) -> ToolCallChunk:
    """Handle tool call message event."""
    langgraph_node = config.get("langgraph_node", "")
    tool_calls_chunks = message_data["tool_call_chunks"]

    # Register tool calls in execution context for later enrichment
    execution_context = config.get("execution_context")

    # Create ExecutionContext if it doesn't exist
    if execution_context is None:
        execution_context = ExecutionContext()
        config["execution_context"] = execution_context
    elif not isinstance(execution_context, ExecutionContext):
        # Convert dict to ExecutionContext if needed
        execution_context = ExecutionContext(**execution_context)
        config["execution_context"] = execution_context

    # Extract tool calls from message_data and create ToolCallMetadata instances
    tool_calls = message_data.get("tool_calls", [])
    for tc in tool_calls:
        if isinstance(tc, dict) and "id" in tc:
            tool_call_metadata = ToolCallMetadata(
                name=tc.get("name", ""),
                args=tc.get("args", {}),
                status="pending",
                node=langgraph_node,
            )
            execution_context.tool_calls[tc["id"]] = tool_call_metadata

    return ToolCallChunk(
        type="tool_call",
        conversation_id=conversation_id,
        task=langgraph_node,
        id=message_data.get("id", ""),
        tool_calls_chunks=tool_calls_chunks,
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
        usage=message_data.get("usage_metadata"),
    )


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


def _safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get attribute from object, returning default if not found."""
    try:
        return getattr(obj, attr, default)
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
