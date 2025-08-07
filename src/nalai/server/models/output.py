"""
Output models for API Assistant server.

This module contains models for outgoing responses:
- AgentInvokeResponse: Synchronous agent response
- ErrorResponse: Error response structure
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


class ErrorResponse(BaseModel):
    """Error response model."""

    model_config = ConfigDict(extra="forbid")

    error: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Additional error details")
    status_code: int = Field(400, description="HTTP status code")
