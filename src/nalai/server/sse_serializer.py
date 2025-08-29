"""
Event handling utilities for API Assistant server.

This module contains functions for processing, serializing, and formatting
events from the agent, including specialized handlers for different event types.
"""

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..core.agent import (
    InterruptChunk,
    MessageChunk,
    StreamingChunk,
    ToolCallChunk,
    ToolChunk,
    UpdateChunk,
)
from ..utils.id_generator import generate_run_id

logger = logging.getLogger("nalai")


def serialize_to_sse(data: dict[str, Any]) -> str:
    """Serialize data to SSE format."""
    event_type = data.get("event", None)
    if event_type:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    else:
        return f"data: {json.dumps(data)}\n\n"


class BaseSSEEvent(BaseModel):
    """Base event model with common fields for all SSE events."""

    event: str = Field(..., description="Event type identifier")
    id: str = Field(default_factory=generate_run_id, description="Unique event ID")
    conversation: str = Field(..., description="Conversation ID")

    def to_sse(self) -> str:
        """Convert the event to SSE format."""
        return serialize_to_sse(self.model_dump())


class ResponseCreatedEvent(BaseSSEEvent):
    """Response created event - sent when a new response is initiated."""

    event: Literal["response.created"] = "response.created"


class ResponseCompletedEvent(BaseSSEEvent):
    """Response completed event - sent when a response is fully completed."""

    event: Literal["response.completed"] = "response.completed"
    usage: dict[str, int] = Field(..., description="Token usage information")


class ResponseErrorEvent(BaseSSEEvent):
    """Response error event - sent when a response encounters an error."""

    event: Literal["response.error"] = "response.error"
    error: str = Field(..., description="Error message")


class ResponseOutputEvent(BaseSSEEvent):
    """Response output event - sent when output messages are available."""

    event: Literal["response.output"] = "response.output"
    output: list[dict[str, Any]] = Field(..., description="Output messages")


class ResponseOutputTextDeltaEvent(BaseSSEEvent):
    """Response output text delta event - sent for streaming text content."""

    event: Literal["response.output_text.delta"] = "response.output_text.delta"
    content: str = Field(..., description="Text content delta")
    usage: dict[str, Any] | None = Field(None, description="Usage metadata")


class ResponseOutputTextCompleteEvent(BaseSSEEvent):
    """Response output text complete event - sent when text streaming is complete."""

    event: Literal["response.output_text.complete"] = "response.output_text.complete"


class ResponseOutputToolCallsDeltaEvent(BaseSSEEvent):
    """Response output tool calls delta event - sent for streaming tool calls."""

    event: Literal["response.output_tool_calls.delta"] = (
        "response.output_tool_calls.delta"
    )
    tool_calls: list[dict[str, Any]] = Field(..., description="Tool calls delta")


class ResponseOutputToolCallsCompleteEvent(BaseSSEEvent):
    """Response output tool calls complete event - sent when tool calls streaming is complete."""

    event: Literal["response.output_tool_calls.complete"] = (
        "response.output_tool_calls.complete"
    )


class ResponseInterruptEvent(BaseSSEEvent):
    """Response interrupt event - sent when a response is interrupted."""

    event: Literal["response.interrupt"] = "response.interrupt"
    interrupts: list[dict[str, Any]] = Field(..., description="Interrupt information")


class ResponseUpdateEvent(BaseSSEEvent):
    """Response update event - sent when a workflow node/task completes."""

    event: Literal["response.update"] = "response.update"
    task: str = Field(..., description="Task/node that completed")
    messages: list[dict[str, Any]] | None = Field(None, description="Messages from the task")


class ResponseToolEvent(BaseSSEEvent):
    """Response tool event - sent when a tool execution completes."""

    event: Literal["response.tool"] = "response.tool"
    tool_call_id: str = Field(..., description="Tool call ID")
    tool_name: str = Field(..., description="Tool name")
    status: str = Field(..., description="Tool execution status")
    content: str = Field(..., description="Tool execution result")

    @classmethod
    def create(
        cls,
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        status: str,
        content: str,
    ) -> str:
        """Create a response.tool event."""
        event = cls(
            conversation=conversation_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=status,
            content=content,
        )
        return event.to_sse()


def create_streaming_event_from_chunk(
    chunk: StreamingChunk, conversation_id: str, context: Any, run_id: str
) -> str | None:
    """Create SSE event from streaming chunk."""
    try:
        if isinstance(chunk, MessageChunk):
            # Handle message chunks
            if chunk.content:
                event = ResponseOutputTextDeltaEvent(
                    id=run_id,
                    conversation=conversation_id,
                    content=chunk.content,
                    usage=chunk.usage,
                )
                return event.to_sse()

        elif isinstance(chunk, ToolCallChunk):
            # Handle tool call chunks
            if chunk.tool_calls:
                event = ResponseOutputToolCallsDeltaEvent(
                    id=run_id,
                    conversation=conversation_id,
                    tool_calls=chunk.tool_calls,
                )
                return event.to_sse()

        elif isinstance(chunk, InterruptChunk):
            # Handle interrupt chunks
            if chunk.values:
                event = ResponseInterruptEvent(
                    id=run_id,
                    conversation=conversation_id,
                    interrupts=chunk.values,
                )
                return event.to_sse()

        elif isinstance(chunk, ToolChunk):
            # Handle tool chunks (tool execution results)
            event = ResponseToolEvent.create(
                conversation_id=conversation_id,
                tool_call_id=chunk.tool_call_id,
                tool_name=chunk.tool_name,
                status=chunk.status,
                content=chunk.content,
            )
            return event

        elif isinstance(chunk, UpdateChunk):
            # Handle update chunks (workflow progress events)
            event = ResponseUpdateEvent(
                id=run_id,
                conversation=conversation_id,
                task=chunk.task,
                messages=[msg.model_dump() for msg in chunk.messages] if chunk.messages else None,
            )
            return event.to_sse()

        return None

    except Exception as e:
        logger.error(f"Error creating streaming event from chunk: {e}")
        return None


def create_response_created_event(conversation_id: str, run_id: str) -> str:
    """Create response created event."""
    event = ResponseCreatedEvent(
        id=run_id,
        conversation=conversation_id,
    )
    return event.to_sse()


def create_response_completed_event(
    conversation_id: str, run_id: str, usage: dict[str, int]
) -> str:
    """Create response completed event."""
    event = ResponseCompletedEvent(
        id=run_id,
        conversation=conversation_id,
        usage=usage,
    )
    return event.to_sse()


def create_response_error_event(conversation_id: str, run_id: str, error: str) -> str:
    """Create response error event."""
    event = ResponseErrorEvent(
        id=run_id,
        conversation=conversation_id,
        error=error,
    )
    return event.to_sse()


def create_response_output_event(
    conversation_id: str, run_id: str, output: list[dict[str, Any]]
) -> str:
    """Create response output event."""
    event = ResponseOutputEvent(
        id=run_id,
        conversation=conversation_id,
        output=output,
    )
    return event.to_sse()


def create_response_output_tool_calls_complete_event(
    conversation_id: str, run_id: str, tool_calls: list[dict[str, Any]]
) -> str:
    """Create response output tool calls complete event."""
    event = ResponseOutputToolCallsCompleteEvent(
        id=run_id,
        conversation=conversation_id,
        tool_calls=tool_calls,
    )
    return event.to_sse()
