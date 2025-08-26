"""
Event handling utilities for API Assistant server.

This module contains functions for processing, serializing, and formatting
events from the agent, including specialized handlers for different event types.
"""

import json
import logging
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger("nalai")


def serialize_to_sse(event: object, serialize_func: Callable[[object], object]) -> str:
    """Serialize event to SSE format."""
    serialized = serialize_func(event)
    return f"data: {json.dumps(serialized)}\n\n"


# Pydantic models for type-safe event creation
class BaseEvent(BaseModel):
    """Base event model with common fields."""

    event: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation: str


class ResponseResumedEvent(BaseEvent):
    """Response resumed event."""

    event: str = "response.resumed"


class ResponseMessageEvent(BaseEvent):
    """Response message event."""

    event: str = "response.message"
    content: str
    role: str = "assistant"


class ResponseCompletedEvent(BaseEvent):
    """Response completed event."""

    event: str = "response.completed"
    usage: dict[str, Any] | None = None


class ResponseErrorEvent(BaseEvent):
    """Response error event."""

    event: str = "response.error"
    error: str


class ResponseCreatedEvent(BaseEvent):
    """Response created event."""

    event: str = "response.created"


# Generic event factory for type-safe event creation
T = TypeVar("T", bound=BaseEvent)


def create_event[T: BaseEvent](
    event_class: type[T], conversation_id: str, **kwargs
) -> str:
    """Generic event factory using Pydantic models."""
    event = event_class(conversation=conversation_id, **kwargs)
    return serialize_to_sse(event.model_dump(), lambda x: x)


def create_streaming_event(
    event: object, serialize_func: Callable[[object], object]
) -> str:
    """Create a streaming event from an agent event without exposing SSE format."""
    return serialize_to_sse(event, serialize_func)


def create_custom_event(event_type: str, conversation_id: str, **kwargs) -> str:
    """Create a custom event without exposing SSE format."""
    event_data = {
        "event": event_type,
        "id": str(uuid.uuid4()),
        "conversation": conversation_id,
        **kwargs,
    }
    return serialize_to_sse(event_data, lambda x: x)
