import re
from typing import Literal

from langchain_core.runnables import RunnableConfig
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


# Add this default instance
DEFAULT_MODEL_CONFIG = ModelConfig(name="gpt-4.1", platform="openai")


class ConfigSchema(BaseModel):
    model: ModelConfig = Field(
        default=DEFAULT_MODEL_CONFIG,
        description=(
            "Configuration for the model to be used. "
            f"Defaults to {{'name': {DEFAULT_MODEL_CONFIG.name}, 'platform': {DEFAULT_MODEL_CONFIG.platform} }} ."
        ),
    )


__all__ = [
    "ModelConfig",
    "ConfigSchema",
]
