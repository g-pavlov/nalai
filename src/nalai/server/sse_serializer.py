"""
Event handling utilities for API Assistant server.

This module contains functions for processing, serializing, and formatting
events from the agent, including specialized handlers for different event types.
"""

import json
import logging
import uuid
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

logger = logging.getLogger("nalai")


class BaseSSEEvent(BaseModel):
    """Base event model with common fields for all SSE events."""

    event: str = Field(..., description="Event type identifier")
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique event ID"
    )
    conversation: str = Field(..., description="Conversation ID")

    def to_sse(self) -> str:
        """Convert the event to SSE format."""
        return serialize_to_sse(self.model_dump())


class ResponseCreatedEvent(BaseSSEEvent):
    """Response created event - sent when a new response is initiated."""

    event: Literal["response.created"] = "response.created"

    @classmethod
    def create(cls, conversation_id: str) -> str:
        """Create a response.created event."""
        event = cls(conversation=conversation_id)
        return event.to_sse()


class ResponseOutputTextDeltaEvent(BaseSSEEvent):
    """Response output text delta event - sent for streaming text content."""

    event: Literal["response.output_text.delta"] = "response.output_text.delta"
    content: str = Field(..., description="Text content chunk")

    @classmethod
    def create(cls, conversation_id: str, content: str) -> str:
        """Create a response.output_text.delta event."""
        event = cls(conversation=conversation_id, content=content)
        return event.to_sse()


class ResponseOutputTextCompleteEvent(BaseSSEEvent):
    """Response output text complete event - sent when text content is complete."""

    event: Literal["response.output_text.complete"] = "response.output_text.complete"
    content: str = Field(..., description="Complete text content")

    @classmethod
    def create(cls, conversation_id: str, content: str) -> str:
        """Create a response.output_text.complete event."""
        event = cls(conversation=conversation_id, content=content)
        return event.to_sse()


class ResponseToolCallsDeltaEvent(BaseSSEEvent):
    """Response tool calls delta event - sent for streaming tool call content."""

    event: Literal["response.tool_calls.delta"] = "response.tool_calls.delta"
    tool_calls: list[dict[str, Any]] = Field(..., description="Tool call chunks")

    @classmethod
    def create(cls, conversation_id: str, tool_calls: list[dict[str, Any]]) -> str:
        """Create a response.tool_calls.delta event."""
        event = cls(conversation=conversation_id, tool_calls=tool_calls)
        return event.to_sse()


class ResponseToolCallsCompleteEvent(BaseSSEEvent):
    """Response tool calls complete event - sent when tool calls are complete."""

    event: Literal["response.tool_calls.complete"] = "response.tool_calls.complete"
    tool_calls: list[dict[str, Any]] = Field(..., description="Complete tool calls")

    @classmethod
    def create(cls, conversation_id: str, tool_calls: list[dict[str, Any]]) -> str:
        """Create a response.tool_calls.complete event."""
        event = cls(conversation=conversation_id, tool_calls=tool_calls)
        return event.to_sse()


class ResponseInterruptEvent(BaseSSEEvent):
    """Response interrupt event - sent when an interrupt occurs."""

    event: Literal["response.interrupt"] = "response.interrupt"
    interrupt_id: str | None = Field(None, description="Interrupt ID")
    action: str = Field(..., description="Action to be taken")
    args: dict[str, Any] = Field(default_factory=dict, description="Action arguments")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Action configuration"
    )
    description: str = Field("", description="Interrupt description")

    @classmethod
    def create(
        cls,
        conversation_id: str,
        interrupt_id: str | None = None,
        action: str = "unknown",
        args: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        description: str = "",
    ) -> str:
        """Create a response.interrupt event."""
        event = cls(
            conversation=conversation_id,
            interrupt_id=interrupt_id,
            action=action,
            args=args or {},
            config=config or {},
            description=description,
        )
        return event.to_sse()


class ResponseResumedEvent(BaseSSEEvent):
    """Response resumed event - sent when a response is resumed."""

    event: Literal["response.resumed"] = "response.resumed"

    @classmethod
    def create(cls, conversation_id: str) -> str:
        """Create a response.resumed event."""
        event = cls(conversation=conversation_id)
        return event.to_sse()


class ResponseCompletedEvent(BaseSSEEvent):
    """Response completed event - sent when a response is complete."""

    event: Literal["response.completed"] = "response.completed"
    usage: dict[str, Any] | None = Field(None, description="Usage statistics")

    @classmethod
    def create(cls, conversation_id: str, usage: dict[str, Any] | None = None) -> str:
        """Create a response.completed event."""
        event = cls(conversation=conversation_id, usage=usage)
        return event.to_sse()


class ResponseErrorEvent(BaseSSEEvent):
    """Response error event - sent when an error occurs."""

    event: Literal["response.error"] = "response.error"
    error: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Error details")

    @classmethod
    def create(cls, conversation_id: str, error: str, detail: str | None = None) -> str:
        """Create a response.error event."""
        event = cls(conversation=conversation_id, error=error, detail=detail)
        return event.to_sse()


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


class ResponseUpdateEvent(BaseSSEEvent):
    """Response update event - sent for workflow progress updates."""

    event: Literal["response.update"] = "response.update"
    task: str = Field(..., description="Task name")
    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="Messages in the update"
    )

    @classmethod
    def create(
        cls,
        conversation_id: str,
        task: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create a response.update event."""
        event = cls(conversation=conversation_id, task=task, messages=messages or [])
        return event.to_sse()


# ===== Core Serialization Functions =====


def serialize_to_sse(event: object) -> str:
    """Serialize an event object to SSE format."""
    return f"data: {json.dumps(event)}\n\n"


class StreamingContext:
    """Manages streaming state and accumulation for SSE events."""

    def __init__(self, conversation_id: str, stream_mode: str = "full"):
        self.conversation_id = conversation_id
        self.stream_mode = stream_mode
        self.accumulated_content = ""
        self.accumulated_tool_calls = []
        self.has_sent_created = False
        self.has_sent_completed = False
        self.previous_was_text = False  # Track if previous chunk was text

    def create_created_event(self) -> str:
        """Create and mark response.created event as sent."""
        if not self.has_sent_created:
            self.has_sent_created = True
            # Reset accumulated content when starting a new streaming session
            self.accumulated_content = ""
            self.accumulated_tool_calls.clear()
            return ResponseCreatedEvent.create(self.conversation_id)
        return ""

    def create_resumed_event(self) -> str:
        """Create response.resumed event."""
        return ResponseResumedEvent.create(self.conversation_id)

    def create_error_event(self, error: str, detail: str | None = None) -> str:
        """Create response.error event."""
        return ResponseErrorEvent.create(self.conversation_id, error, detail)

    def create_tool_event(self, chunk: ToolChunk) -> str:
        """Create response.tool event from tool chunk."""
        return ResponseToolEvent.create(
            self.conversation_id,
            chunk.tool_call_id,
            chunk.tool_name,
            chunk.status,
            chunk.content,
        )

    def create_update_event(
        self, task: str, messages: list[dict[str, Any]] | None = None
    ) -> str:
        """Create response.update event."""
        return ResponseUpdateEvent.create(self.conversation_id, task, messages)

    def create_interrupt_event(self, chunk: InterruptChunk) -> str:
        """Create response.interrupt event from interrupt chunk."""
        # Use the InterruptChunk interface directly
        action_request = chunk.value.get("action_request", {})
        if not action_request:
            logger.warning(
                "Interrupt chunk %s has no action request: %s", chunk.id, chunk
            )

        return ResponseInterruptEvent.create(
            conversation_id=self.conversation_id,
            interrupt_id=chunk.id,
            action=action_request.get("action", "unknown"),
            args=action_request.get("args", {}),
            config=chunk.value.get("config", {}),
            description=chunk.value.get("description", ""),
        )

    def create_text_chunk_event(self, content: str) -> str:
        """Process text chunk and return appropriate event based on stream mode."""
        # Always accumulate content for complete events, regardless of stream mode
        self.accumulated_content += content

        if self.stream_mode == "events":
            # Don't emit delta events in events mode
            return ""
        else:
            # Emit delta events immediately in full mode
            return ResponseOutputTextDeltaEvent.create(self.conversation_id, content)

    def create_text_complete_event(self) -> str:
        """Create text complete event with accumulated content."""
        if self.accumulated_content:
            content = self.accumulated_content
            self.accumulated_content = ""  # Reset for next message
            return ResponseOutputTextCompleteEvent.create(self.conversation_id, content)
        return ""

    def create_tool_call_chunk_event(self, tool_calls: list[dict[str, Any]]) -> str:
        """Process tool call chunk and return appropriate event."""
        if self.stream_mode == "events":
            # Accumulate tool calls for single complete event
            self.accumulated_tool_calls.extend(tool_calls)
            return ""  # Don't emit delta events in events mode
        else:
            # Emit delta events immediately
            return ResponseToolCallsDeltaEvent.create(self.conversation_id, tool_calls)

    def create_tool_calls_complete_event(self) -> str:
        """Create tool calls complete event with accumulated tool calls."""
        if self.accumulated_tool_calls:
            tool_calls = self.accumulated_tool_calls.copy()
            self.accumulated_tool_calls.clear()  # Reset for next message
            return ResponseToolCallsCompleteEvent.create(
                self.conversation_id, tool_calls
            )
        return ""

    def create_completed_event(self, usage: dict[str, Any] | None = None) -> str:
        """Create and mark response.completed event as sent."""
        if not self.has_sent_completed:
            self.has_sent_completed = True
            return ResponseCompletedEvent.create(self.conversation_id, usage)
        return ""


def create_streaming_event_from_chunk(
    chunk: StreamingChunk, conversation_id: str, context: StreamingContext
) -> str:
    """Create a streaming event from a strongly-typed streaming chunk."""

    # Check if we're transitioning from text to non-text (and have accumulated content)
    complete_event = ""
    if (
        context.previous_was_text
        and context.accumulated_content
        and not isinstance(chunk, MessageChunk)
    ):
        complete_event = context.create_text_complete_event()

    # Use type-based dispatching for efficient processing
    if isinstance(chunk, InterruptChunk):
        event = context.create_interrupt_event(chunk)
        context.previous_was_text = False
        return complete_event + event if complete_event else event

    elif isinstance(chunk, ToolCallChunk):
        event = context.create_tool_call_chunk_event(chunk.tool_calls)
        context.previous_was_text = False
        return complete_event + event if complete_event else event

    elif isinstance(chunk, MessageChunk):
        # For text chunks, just accumulate and send delta
        event = context.create_text_chunk_event(chunk.content)
        context.previous_was_text = True
        return event

    elif isinstance(chunk, ToolChunk):
        event = context.create_tool_event(chunk)
        context.previous_was_text = False
        return complete_event + event if complete_event else event

    elif isinstance(chunk, UpdateChunk):
        messages = (
            [msg.model_dump() for msg in chunk.messages] if chunk.messages else []
        )
        event = context.create_update_event(task=chunk.task, messages=messages)
        context.previous_was_text = False
        return complete_event + event if complete_event else event

    else:
        # Fallback for unrecognized chunk types
        logger.warning("Unrecognized chunk type: %s", type(chunk))
        context.previous_was_text = False
        return ""
