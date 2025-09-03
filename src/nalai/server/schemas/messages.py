"""
Message schemas for the server.

This module defines the request and response schemas for the agent message exchange API.
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.types.messages import Interrupt, OutputMessage
from ...utils.id_generator import validate_domain_id_format
from .base import StrictModelMixin

logger = logging.getLogger("nalai")


class ResponseMetadata(BaseModel, StrictModelMixin):
    """Response-level metadata structure."""

    error: str | None = Field(
        None, description="Error message if response failed", max_length=10000
    )
    cache_hit: bool | None = Field(
        None, description="Whether this response was served from cache"
    )
    processing_time_ms: float | None = Field(
        None,
        description="Response processing time in milliseconds",
        ge=0.0,  # Must be non-negative
    )

    @field_validator("processing_time_ms")
    @classmethod
    def validate_processing_time(cls, v):
        """Validate processing time."""
        if v is not None and (v < 0 or v > 3600000):  # Max 1 hour
            raise ValueError(
                "Processing time must be between 0 and 3,600,000 ms (1 hour)"
            )
        return v


class MessageResponse(BaseModel):
    """Response model for agent message exchange endpoint."""

    id: str = Field(..., description="Response ID", min_length=1, max_length=100)
    conversation_id: str | None = Field(
        None, description="Conversation ID", max_length=100
    )
    previous_response_id: str | None = Field(
        None,
        description="Previous response ID if this response branches from another",
        max_length=100,
    )
    output: list[OutputMessage] = Field(
        ..., description="Output messages", min_length=1
    )
    created_at: str = Field(..., description="Creation timestamp", max_length=50)
    status: Literal["completed", "interrupted", "error", "cancelled", "processing"] = (
        Field(..., description="Response status")
    )
    interrupts: list[Interrupt] | None = Field(
        None,
        description="List of interrupts if response was interrupted",
        max_length=10,  # Limit number of interrupts
    )
    metadata: ResponseMetadata | None = Field(None, description="Response metadata")
    usage: dict[str, int] = Field(..., description="Token usage information")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        """Validate response ID format."""
        if not validate_domain_id_format(v, "run"):
            raise ValueError(
                "Response ID must be a valid domain-prefixed format: run_xxx"
            )
        return v

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate conversation ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "conv"):
                raise ValueError(
                    "Conversation ID must be a valid domain-prefixed format: conv_xxx"
                )
        return v

    @field_validator("previous_response_id")
    @classmethod
    def validate_previous_response_id(cls, v):
        """Validate previous response ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "run"):
                raise ValueError(
                    "Previous response ID must be a valid domain-prefixed format: run_xxx"
                )
        return v

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v):
        """Validate creation timestamp format."""
        # Accept ISO 8601 format with or without timezone offset
        if not re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3,6})?(Z|[+-]\d{2}:\d{2})?$", v
        ):
            raise ValueError(
                "created_at must be in ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.mmm][Z|±HH:MM])"
            )
        return v

    @field_validator("usage")
    @classmethod
    def validate_usage(cls, v):
        """Validate token usage information."""
        if not isinstance(v, dict):
            raise ValueError("Usage must be a dictionary")

        required_keys = {"prompt_tokens", "completion_tokens", "total_tokens"}
        missing_keys = required_keys - set(v.keys())
        if missing_keys:
            raise ValueError(f"Usage missing required keys: {missing_keys}")

        for key, value in v.items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"Usage value for {key} must be a non-negative integer"
                )

        return v

    @model_validator(mode="after")
    def validate_response_consistency(self):
        """Validate response consistency."""
        # If status is interrupted, interrupts should be provided
        if self.status == "interrupted" and not self.interrupts:
            raise ValueError("Interrupted status requires interrupts list")

        # If status is error, metadata should contain error
        if self.status == "error" and (not self.metadata or not self.metadata.error):
            raise ValueError("Error status requires error message in metadata")

        return self

    @model_validator(mode="after")
    def validate_response_structure(self):
        """Validate complete response structure."""
        # Verify required fields are present
        if not self.id:
            raise ValueError("Response must have an ID")

        if not self.output:
            raise ValueError("Response must have output messages")

        if not self.created_at:
            raise ValueError("Response must have creation timestamp")

        if not self.status:
            raise ValueError("Response must have status")

        # Verify output contains at least one message
        if len(self.output) == 0:
            raise ValueError("Response output must contain at least one message")

        # Verify all output messages have valid structure
        for i, message in enumerate(self.output):
            if not message.id:
                raise ValueError(f"Output message {i} must have an ID")

            if not message.content:
                raise ValueError(f"Output message {i} must have content")

            if not message.role:
                raise ValueError(f"Output message {i} must have a role")

        return self
