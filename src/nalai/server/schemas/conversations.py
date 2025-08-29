"""
Conversation resource schemas.

This module contains all schemas for the conversation resource:
- /api/v1/conversations/{conversation_id} (GET) - Load conversation
- /api/v1/conversations (GET) - List conversations
- /api/v1/conversations/{conversation_id} (DELETE) - Delete conversation

Note: Conversations are created implicitly by the /api/v1/messages endpoint.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...utils.id_generator import validate_domain_id_format
from .messages import OutputMessage


class ConversationResponse(BaseModel):
    """Response model for conversation operations."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    output: dict[str, Any] = Field(..., description="Conversation output")

    @field_validator("output")
    @classmethod
    def validate_output(cls, v):
        """Basic output validation."""
        if not isinstance(v, dict):
            raise ValueError("Output must be a dictionary")
        if not v:
            raise ValueError("Output cannot be empty")

        # Validate output size
        if len(str(v)) > 100000:  # 100KB limit
            raise ValueError("Output serialized size cannot exceed 100KB")

        return v


class LoadConversationResponse(BaseModel):
    """Response model for loading a conversation."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    conversation_id: str = Field(
        ..., description="Conversation identifier", min_length=1, max_length=100
    )
    messages: list[OutputMessage] = Field(
        ..., description="List of conversation messages", min_length=0
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Conversation metadata",
        max_length=10000,  # 10KB limit for metadata
    )
    created_at: str | None = Field(
        None, description="Creation timestamp", max_length=50
    )
    last_updated: str | None = Field(
        None, description="Last update timestamp", max_length=50
    )
    status: Literal["active", "completed", "interrupted"] = Field(
        default="active", description="Conversation status"
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate conversation ID format."""
        if not validate_domain_id_format(v, "conv"):
            raise ValueError(
                "conversation_id must be a valid domain-prefixed format: conv_xxx"
            )
        return v

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        """Validate messages list."""
        if not isinstance(messages, list):
            raise ValueError("Messages must be a list")

        if len(messages) > 1000:  # Limit conversation length
            raise ValueError("Conversation cannot exceed 1000 messages")

        # Validate message order (should be chronological)
        for i, msg in enumerate(messages):
            if not hasattr(msg, "id") or not msg.id:
                raise ValueError(f"Message at position {i} must have a valid ID")

        return messages

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, metadata):
        """Validate metadata."""
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        if len(str(metadata)) > 10000:
            raise ValueError("Metadata serialized size cannot exceed 10KB")

        return metadata

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v):
        """Validate creation timestamp format."""
        if v is not None:
            if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$", v):
                raise ValueError(
                    "created_at must be in ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.mmm]Z)"
                )
        return v

    @field_validator("last_updated")
    @classmethod
    def validate_last_updated(cls, v):
        """Validate last updated timestamp format."""
        if v is not None:
            if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$", v):
                raise ValueError(
                    "last_updated must be in ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.mmm]Z)"
                )
        return v

    @model_validator(mode="after")
    def validate_timestamp_consistency(self):
        """Validate timestamp consistency."""
        if self.created_at and self.last_updated:
            # Basic string comparison for ISO timestamps
            if self.last_updated < self.created_at:
                raise ValueError("last_updated cannot be earlier than created_at")

        return self


class ConversationSummary(BaseModel):
    """Summary model for a conversation in the list."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    conversation_id: str = Field(
        ..., description="Conversation identifier", min_length=1, max_length=100
    )
    created_at: str | None = Field(
        None, description="Creation timestamp", max_length=50
    )
    last_updated: str | None = Field(
        None, description="Last update timestamp", max_length=50
    )
    preview: str | None = Field(
        None, description="First 256 characters of conversation", max_length=256
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Conversation metadata",
        max_length=5000,  # 5KB limit for summary metadata
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate conversation ID format."""
        if not validate_domain_id_format(v, "conv"):
            raise ValueError(
                "conversation_id must be a valid domain-prefixed format: conv_xxx"
            )
        return v

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v):
        """Validate creation timestamp format."""
        if v is not None:
            if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$", v):
                raise ValueError(
                    "created_at must be in ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.mmm]Z)"
                )
        return v

    @field_validator("last_updated")
    @classmethod
    def validate_last_updated(cls, v):
        """Validate last updated timestamp format."""
        if v is not None:
            if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$", v):
                raise ValueError(
                    "last_updated must be in ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.mmm]Z)"
                )
        return v

    @field_validator("preview")
    @classmethod
    def validate_preview(cls, preview):
        """Validate preview text."""
        if preview is not None:
            if len(preview) > 256:
                raise ValueError("Preview cannot exceed 256 characters")

            # Check for control characters (except newlines and tabs)
            if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", preview):
                raise ValueError("Preview contains invalid control characters")

        return preview

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, metadata):
        """Validate metadata."""
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        if len(str(metadata)) > 5000:
            raise ValueError("Metadata serialized size cannot exceed 5KB")

        return metadata

    @model_validator(mode="after")
    def validate_timestamp_consistency(self):
        """Validate timestamp consistency."""
        if self.created_at and self.last_updated:
            # Basic string comparison for ISO timestamps
            if self.last_updated < self.created_at:
                raise ValueError("last_updated cannot be earlier than created_at")

        return self


class ListConversationsResponse(BaseModel):
    """Response model for listing conversations."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    conversations: list[ConversationSummary] = Field(
        ..., description="List of conversation summaries", min_length=0
    )
    total_count: int = Field(
        ...,
        description="Total number of conversations",
        ge=0,  # Must be non-negative
    )

    @field_validator("conversations")
    @classmethod
    def validate_conversations(cls, conversations):
        """Validate conversations list."""
        if not isinstance(conversations, list):
            raise ValueError("Conversations must be a list")

        if len(conversations) > 1000:  # Limit pagination size
            raise ValueError("Conversations list cannot exceed 1000 items")

        # Validate unique conversation IDs
        conversation_ids = [conv.conversation_id for conv in conversations]
        if len(conversation_ids) != len(set(conversation_ids)):
            raise ValueError("Conversation IDs must be unique")

        return conversations

    @field_validator("total_count")
    @classmethod
    def validate_total_count(cls, total_count):
        """Validate total count."""
        if total_count < 0:
            raise ValueError("Total count cannot be negative")

        if total_count > 1000000:  # Reasonable upper limit
            raise ValueError("Total count cannot exceed 1,000,000")

        return total_count

    @model_validator(mode="after")
    def validate_count_consistency(self):
        """Validate that total_count is consistent with conversations list."""
        if self.total_count < len(self.conversations):
            raise ValueError(
                "Total count cannot be less than the number of conversations in the list"
            )

        return self
