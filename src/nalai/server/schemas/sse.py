"""
Event handling utilities for API Assistant server.

This module contains functions for processing, serializing, and formatting
events from the agent, including specialized handlers for different event types.
"""

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from ...utils.id_generator import generate_run_id

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
    conversation_id: str = Field(..., description="Conversation ID")

    def to_sse(self) -> str:
        """Convert the event to SSE format."""
        return serialize_to_sse(self.model_dump())


class ResponseOutputTextDeltaEvent(BaseSSEEvent):
    """Response output text delta event - sent for streaming text content."""

    event: Literal["response.output_text.delta"] = "response.output_text.delta"
    content: str = Field(..., description="Text content delta")
    usage: dict[str, Any] | None = Field(None, description="Usage metadata")

    @classmethod
    def create(
        cls,
        conversation_id: str,
        content: str,
        usage: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> str:
        """Create a response.output_text.delta event."""
        event = cls(
            conversation_id=conversation_id,
            content=content,
            usage=usage,
            id=id,
        )
        return event.to_sse()


class ResponseOutputTextCompleteEvent(BaseSSEEvent):
    """Response output text complete event - sent when text streaming is complete."""

    event: Literal["response.output_text.complete"] = "response.output_text.complete"


class ResponseOutputToolCallsDeltaEvent(BaseSSEEvent):
    """Response output tool calls delta event - sent for streaming tool calls."""

    event: Literal["response.output_tool_calls.delta"] = (
        "response.output_tool_calls.delta"
    )
    tool_calls: list[dict[str, Any]] = Field(..., description="Tool calls")

    @classmethod
    def create(
        cls,
        conversation_id: str,
        tool_calls: list[dict[str, Any]],
        id: str | None = None,
    ) -> str:
        """Create a response.output_tool_calls.delta event."""
        event = cls(
            conversation_id=conversation_id,
            tool_calls=tool_calls,
            id=id,
        )
        return event.to_sse()


class ResponseOutputToolCallsCompleteEvent(BaseSSEEvent):
    """Response output tool calls complete event - sent when tool calls streaming is complete."""

    event: Literal["response.output_tool_calls.complete"] = (
        "response.output_tool_calls.complete"
    )
    tool_calls: list[dict[str, Any]] = Field(..., description="Tool calls")

    @classmethod
    def create(
        cls,
        conversation_id: str,
        tool_calls: list[dict[str, Any]],
        id: str | None = None,
    ) -> str:
        """Create a response.output_tool_calls.complete event."""
        event = cls(
            conversation_id=conversation_id,
            tool_calls=tool_calls,
            id=id,
        )
        return event.to_sse()


class ResponseInterruptEvent(BaseSSEEvent):
    """Response interrupt event - sent when a response is interrupted."""

    event: Literal["response.interrupt"] = "response.interrupt"
    interrupts: list[dict[str, Any]] = Field(..., description="Interrupt information")

    @classmethod
    def create(
        cls,
        conversation_id: str,
        interrupts: list[dict[str, Any]],
        id: str | None = None,
    ) -> str:
        """Create a response.interrupt event."""
        event = cls(
            conversation_id=conversation_id,
            interrupts=interrupts,
            id=id,
        )
        return event.to_sse()


class ResponseUpdateEvent(BaseSSEEvent):
    """Response update event - sent when a workflow node/task completes."""

    event: Literal["response.update"] = "response.update"
    task: str = Field(..., description="Task/node that completed")
    messages: list[dict[str, Any]] | None = Field(
        None, description="Messages from the task"
    )

    @classmethod
    def create(
        cls,
        conversation_id: str,
        task: str,
        messages: list[dict[str, Any]] | None = None,
        id: str | None = None,
    ) -> str:
        """Create a response.update event."""
        event = cls(
            conversation_id=conversation_id,
            task=task,
            messages=messages,
            id=id,
        )
        return event.to_sse()


class ResponseToolEvent(BaseSSEEvent):
    """Response tool event - sent when a tool execution completes."""

    event: Literal["response.tool"] = "response.tool"
    tool_call_id: str = Field(..., description="Tool call ID")
    tool_name: str = Field(..., description="Tool name")
    status: str = Field(..., description="Tool execution status")
    content: str = Field(..., description="Tool execution result")
    args: dict[str, Any] | None = Field(
        None, description="Actual args used for execution"
    )

    @classmethod
    def create(
        cls,
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        status: str,
        content: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        """Create a response.tool event."""
        event = cls(
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=status,
            content=content,
            args=args,
        )
        return event.to_sse()
