"""
Output models for API Assistant server.

This module contains models for outgoing responses:
- AgentInvokeResponse: Synchronous agent response
- ToolInterruptSyncResponse: Synchronous tool interrupt response
- ToolInterruptStreamEvent: Schema for streaming tool interrupt events
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentInvokeResponse(BaseModel):
    """Response model for agent invocation."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    output: dict[str, Any] = Field(..., description="Agent output")

    @field_validator("output")
    @classmethod
    def validate_output(cls, v):
        """Basic output validation."""
        if not isinstance(v, dict):
            raise ValueError("Output must be a dictionary")
        if not v:
            raise ValueError("Output cannot be empty")
        return v


class ToolInterruptSyncResponse(BaseModel):
    """Synchronous response model for tool interrupt operations."""

    model_config = ConfigDict(extra="forbid")

    output: dict[str, Any] = Field(..., description="Agent response output")


class ToolInterruptStreamEvent(BaseModel):
    """Schema for individual SSE events in tool interrupt stream."""

    model_config = ConfigDict(extra="forbid")

    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="Array of conversation messages"
    )
    selected_apis: list[dict[str, str]] = Field(
        default_factory=list, description="Selected APIs for the request"
    )
    cache_miss: str | None = Field(None, description="Cache status indicator")
