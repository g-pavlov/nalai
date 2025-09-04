"""
Message schemas for the server.

This module defines the request and response schemas for the agent message exchange API.
"""

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...core import (
    HumanInputMessage,
    InputMessage,
    OutputMessage,
)
from ...core.internal.base_models import StrictModelMixin
from ...utils.id_generator import validate_domain_id_format

logger = logging.getLogger("nalai")


class MessageRequest(BaseModel):
    """Request model for agent message exchange endpoint.

    This endpoint supports multiple conversation flows:

    **Stateful Conversations (store: true):**
    - New conversation: no conversation_id
    - Continue conversation: with conversation_id
    - Tool decision: single tool_decision message
    - Human message: single human message

    **Stateless Conversations (store: false):**
    - Multiple human messages only
    - Must start with human message
    - No history constraints

    **Transport Compatibility:**
    - stream="full"/"events" requires Accept: text/event-stream
    - stream="off" requires Accept: application/json

    **Content Limits:**
    - Individual text blocks: max 10KB
    - Total conversation: max 100KB
    - Content blocks per message: max 10
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(
        None, description="Conversation ID for continuation", max_length=100
    )
    previous_response_id: str | None = Field(
        None, description="Response ID to branch from", max_length=100
    )
    input: str | list[InputMessage] = Field(
        ...,
        description="Input messages - string (implicit human message) or list of structured messages. String input is converted to implicit human message. List input supports human messages and tool decision messages only.",
        min_length=1,
    )
    stream: Literal["full", "events", "off"] = Field(
        "full",
        description="Streaming mode - full (typed events + tokens), events (typed events only), off (non-streaming). Requires compatible Accept header: 'full'/'events' need 'text/event-stream', 'off' needs 'application/json'",
    )
    store: bool = Field(True, description="Whether to store the response")

    cache: bool = Field(
        True,
        description="Whether to use caching for this request. Set to false to bypass cache and get fresh responses.",
    )

    model_settings: dict[str, Any] | None = Field(
        None,
        description="Model-specific settings to override default configuration",
        max_length=10000,  # Limit model settings size
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate conversation ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "conv"):
                raise ValueError(
                    "conversation_id must be a valid domain-prefixed format: conv_xxx"
                )
        return v

    @field_validator("previous_response_id")
    @classmethod
    def validate_previous_response_id(cls, v):
        """Validate previous response ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "run"):
                raise ValueError(
                    "previous_response_id must be a valid domain-prefixed format: run_xxx"
                )
        return v

    @field_validator("input")
    @classmethod
    def validate_input(cls, input_data, info):
        """Validate input messages for basic structure."""
        # Handle string input - convert to implicit human message
        if isinstance(input_data, str):
            if not input_data.strip():
                raise ValueError("String input cannot be empty")
            if len(input_data) > 50000:
                raise ValueError("String input cannot exceed 50KB")
            # Return string as-is - it will be converted to human message in to_langchain_messages
            return input_data

        # Handle list input
        if not isinstance(input_data, list):
            raise ValueError("Input must be a string or list of messages")

        if not input_data:
            raise ValueError("Input messages list cannot be empty")

        if len(input_data) > 50:
            raise ValueError("Input messages list cannot exceed 50 messages")

        return input_data

    @field_validator("model_settings")
    @classmethod
    def validate_model_settings(cls, v):
        """Validate model settings structure."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("model_settings must be a dictionary")

            # Validate model settings keys
            allowed_keys = {
                "temperature",
                "max_tokens",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
            }
            invalid_keys = set(v.keys()) - allowed_keys
            if invalid_keys:
                raise ValueError(
                    f"Invalid model_settings keys: {invalid_keys}. Allowed: {allowed_keys}"
                )

            # Validate temperature range
            if "temperature" in v:
                temp = v["temperature"]
                if not isinstance(temp, int | float) or temp < 0 or temp > 2:
                    raise ValueError("temperature must be a number between 0 and 2")

            # Validate max_tokens
            if "max_tokens" in v:
                max_tokens = v["max_tokens"]
                if not isinstance(max_tokens, int) or max_tokens < 1:
                    raise ValueError("max_tokens must be a positive integer")

        return v

    @model_validator(mode="after")
    def validate_input_message_list(self):
        """Validate input message list for proper conversation flow."""
        if isinstance(self.input, list):
            self._validate_conversation_sequence(self.input)

        return self

    def _validate_conversation_sequence(self, messages):
        """Validate proper conversation flow sequence - only human messages supported."""
        for i in range(len(messages) - 1):
            current_msg = messages[i]
            next_msg = messages[i + 1]

            # Validate proper conversation flow - only human messages allowed
            if isinstance(current_msg, HumanInputMessage):
                # Human message can be followed by another human message
                if not isinstance(next_msg, HumanInputMessage):
                    raise ValueError(
                        f"Human message at position {i} can only be followed by another human message"
                    )

    def to_runtime_overrides(self) -> dict[str, Any]:
        """Convert runtime configuration overrides to dict."""
        overrides = {}

        # Cache override (always include since it has a default)
        overrides["disable_cache"] = not self.cache

        # Model settings override
        if self.model_settings:
            overrides["model_settings"] = self.model_settings

        return overrides


class Interrupt(BaseModel, StrictModelMixin):
    """Single interrupt information structure."""

    type: str = Field(..., description="Interrupt type", min_length=1, max_length=50)
    tool_call_id: str = Field(
        ..., description="Tool call ID", min_length=1, max_length=100
    )
    action: str = Field(..., description="Tool action", min_length=1, max_length=100)
    args: dict[str, Any] = Field(
        ...,
        description="Tool arguments",
        max_length=10000,  # Limit args size
    )

    @field_validator("tool_call_id")
    @classmethod
    def validate_tool_call_id(cls, v):
        """Validate tool call ID format."""
        # Accept both tool_ and call_ prefixes (system uses call_ prefix)
        if validate_domain_id_format(v, "tool"):
            return v
        elif validate_domain_id_format(v, "call"):
            return v

        raise ValueError("Tool call ID must be either tool_xxx or call_xxx format")

    @field_validator("args")
    @classmethod
    def validate_args(cls, v):
        """Validate tool arguments."""
        if not isinstance(v, dict):
            raise ValueError("Tool arguments must be a dictionary")

        if len(str(v)) > 10000:
            raise ValueError("Tool arguments serialized size cannot exceed 10KB")

        return v


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
