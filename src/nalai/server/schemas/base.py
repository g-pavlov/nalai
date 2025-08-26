"""Base schemas for the server."""

import uuid
from typing import Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationIdPathParam(BaseModel):
    """Path parameter for conversation ID with UUID validation."""

    conversation_id: str = Field(
        ..., description="Conversation ID (must be valid UUID4 format)"
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_uuid(cls, v):
        """Validate that conversation_id is a valid UUID4."""
        try:
            uuid.UUID(v, version=4)
            return v
        except ValueError:
            raise ValueError("conversation_id must be a valid UUID4") from None


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

    def to_internal_config(self) -> RunnableConfig:
        """Convert to internal RunnableConfig for LangChain/LangGraph."""
        return {
            "configurable": {"model": {"name": self.name, "platform": self.platform}}
        }
