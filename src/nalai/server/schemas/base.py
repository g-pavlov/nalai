"""Base schemas for the server."""

import re
from typing import Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Import validation function locally to avoid circular imports
class StrictModelMixin:
    """Mixin for models that forbid extra fields."""

    model_config = ConfigDict(extra="forbid")


class ConversationIdPathParam(BaseModel):
    """Path parameter for conversation ID with domain-prefixed validation."""

    conversation_id: str = Field(
        ...,
        description="Conversation ID (must be valid domain-prefixed format: conv_xxx)",
        min_length=1,
        max_length=100,
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate that conversation_id is a valid domain-prefixed ID."""
        # Import validation function locally to avoid circular imports
        from ...utils.id_generator import validate_domain_id_format

        if not validate_domain_id_format(v, "conv"):
            raise ValueError(
                "conversation_id must be a valid domain-prefixed format: conv_xxx"
            ) from None
        return v


class ModelConfig(BaseModel):
    """Model configuration for the agent."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        description="Model name (e.g., 'llama3.1:8b', 'claude-3-5-sonnet')",
        min_length=1,
        max_length=100,
    )
    platform: Literal["ollama", "aws_bedrock", "openai"] = Field(
        ..., description="Model platform. Must be one of the supported platforms."
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate model name format."""
        if not v.strip():
            raise ValueError("Model name cannot be empty or whitespace-only")

        # Check for control characters
        if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", v):
            raise ValueError("Model name contains invalid control characters")

        # Check for reasonable model name format
        if not re.match(r"^[a-zA-Z0-9\-_:\.]+$", v):
            raise ValueError(
                "Model name must contain only letters, numbers, hyphens, underscores, colons, and dots"
            )

        return v.strip()

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v):
        """Validate model platform."""
        valid_platforms = {"ollama", "aws_bedrock", "openai"}
        if v not in valid_platforms:
            raise ValueError(f"Platform must be one of: {valid_platforms}")
        return v

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, v):
        """Normalize platform name to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return v

    def to_internal_config(self) -> RunnableConfig:
        """Convert to internal RunnableConfig for LangChain/LangGraph."""
        return {
            "configurable": {"model": {"name": self.name, "platform": self.platform}}
        }
