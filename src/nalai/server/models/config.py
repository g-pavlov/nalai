"""
Configuration models for API Assistant server.

This module contains models for configuration:
- ModelConfig: Model configuration (name, platform)
- AgentConfig: Agent configuration with model and configurable options
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
        ..., description="Model platform"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate model name."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()


class AgentConfig(BaseModel):
    """Configuration for the agent."""

    model_config = ConfigDict(extra="forbid")

    model: ModelConfig | None = Field(
        default=None,
        description="Model configuration (optional, can be provided in configurable.model)",
    )
    configurable: dict[str, Any] | None = Field(
        default=None,
        description="Additional configurable options",
    )
