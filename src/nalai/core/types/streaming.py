from typing import Any, Literal

from pydantic import BaseModel, Field

from ...utils.id_generator import generate_run_id
from .messages import InputMessage, OutputMessage

#  ==== Events ====


class BaseEvent(BaseModel):
    """Base event model with common fields for all SSE events."""

    event: str = Field(..., description="Event type identifier")
    id: str = Field(default_factory=generate_run_id, description="Unique event ID")
    conversation_id: str = Field(
        ..., description="The id of the conversation to which this event belongs"
    )


class ResponseCreatedEvent(BaseEvent):
    """Response created event - sent when a new response is initiated."""

    event: Literal["response.created"] = "response.created"


class ResponseCompletedEvent(BaseEvent):
    """Response completed event - sent when a response is fully completed."""

    event: Literal["response.completed"] = "response.completed"
    usage: dict[str, int] = Field(..., description="Token usage information")


class ResponseErrorEvent(BaseEvent):
    """Response error event - sent when a response encounters an error."""

    event: Literal["response.error"] = "response.error"
    error: str = Field(..., description="Error message")


Event = ResponseCreatedEvent | ResponseCompletedEvent | ResponseErrorEvent


# ==== Stremaing Data Chunks ====


class BaseStreamingChunk(BaseModel):
    """Base class for all streaming chunks."""

    type: str
    conversation_id: str

    class Config:
        extra = "allow"
        validate_assignment = True


class UpdateChunk(BaseStreamingChunk):
    """Update chunk for workflow progress events."""

    type: Literal["update"] = "update"
    task: str  # event_key
    messages: list[InputMessage | OutputMessage] = Field(default_factory=list)


class ToolCallUpdateChunk(BaseStreamingChunk):
    """Update chunk for workflow progress events."""

    type: Literal["tool_call_update"] = "tool_call_update"
    task: str  # event_key
    tool_calls: list[dict[str, Any]] | None = Field(default=None)


class MessageChunk(BaseStreamingChunk):
    """Message chunk for AI message content."""

    type: Literal["message"] = "message"
    task: str  # langgraph_node
    content: str
    id: str
    metadata: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None


class ToolCallChunk(BaseStreamingChunk):
    """Tool call chunk for AI tool call events."""

    type: Literal["tool_call"] = "tool_call"
    task: str  # langgraph_node
    id: str
    tool_calls_chunks: list[dict[str, Any]] | None = Field(default=None)


class InterruptChunk(BaseStreamingChunk):
    """Interrupt chunk for human-in-the-loop events."""

    type: Literal["interrupt"] = "interrupt"
    id: str
    values: list[dict[str, Any]]  # serialized action request, config, description


class ToolChunk(BaseStreamingChunk):
    """Tool chunk for tool execution results."""

    type: Literal["tool"] = "tool"
    id: str
    status: Literal["success", "error", "pending"] = "success"
    tool_call_id: str
    content: str
    tool_name: str
    args: dict[str, Any] | None = Field(
        None, description="Actual args used for execution"
    )


# Union type for all chunk types
StreamingChunk = (
    UpdateChunk
    | ToolCallUpdateChunk
    | MessageChunk
    | ToolCallChunk
    | InterruptChunk
    | ToolChunk
)


def extract_usage_from_streaming_chunks(chunks: list[StreamingChunk]) -> dict[str, int]:
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
