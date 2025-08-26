"""
Conversation resource schemas.

This module contains all schemas for the conversation resource:
- /api/v1/conversations/{conversation_id} (GET) - Load conversation
- /api/v1/conversations (GET) - List conversations
- /api/v1/conversations/{conversation_id} (DELETE) - Delete conversation

Note: Conversations are created implicitly by the /api/v1/messages endpoint.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
        return v


class LoadConversationResponse(BaseModel):
    """Response model for loading a conversation."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    conversation_id: str = Field(..., description="Conversation identifier")
    messages: list[OutputMessage] = Field(
        ..., description="List of conversation messages"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Conversation metadata"
    )
    created_at: str | None = Field(None, description="Creation timestamp")
    last_updated: str | None = Field(None, description="Last update timestamp")
    status: Literal["active", "completed", "interrupted"] = Field(
        default="active", description="Conversation status"
    )

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        """Validate messages list."""
        if not isinstance(messages, list):
            raise ValueError("Messages must be a list")
        return messages

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, metadata):
        """Validate metadata."""
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")
        return metadata


class ConversationSummary(BaseModel):
    """Summary model for a conversation in the list."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    conversation_id: str = Field(..., description="Conversation identifier")
    created_at: str | None = Field(None, description="Creation timestamp")
    last_updated: str | None = Field(None, description="Last update timestamp")
    preview: str | None = Field(
        None, description="First 256 characters of conversation"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Conversation metadata"
    )

    @field_validator("preview")
    @classmethod
    def validate_preview(cls, preview):
        """Validate preview text."""
        if preview is not None and len(preview) > 256:
            raise ValueError("Preview cannot exceed 256 characters")
        return preview


class ListConversationsResponse(BaseModel):
    """Response model for listing conversations."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    conversations: list[ConversationSummary] = Field(
        ..., description="List of conversation summaries"
    )
    total_count: int = Field(..., description="Total number of conversations")

    @field_validator("conversations")
    @classmethod
    def validate_conversations(cls, conversations):
        """Validate conversations list."""
        if not isinstance(conversations, list):
            raise ValueError("Conversations must be a list")
        return conversations

    @field_validator("total_count")
    @classmethod
    def validate_total_count(cls, total_count):
        """Validate total count."""
        if total_count < 0:
            raise ValueError("Total count cannot be negative")
        return total_count
