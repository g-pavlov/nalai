"""Base schemas for the server."""

from typing import Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field


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

    def to_internal_config(self) -> RunnableConfig:
        """Convert to internal RunnableConfig for LangChain/LangGraph."""
        return {
            "configurable": {"model": {"name": self.name, "platform": self.platform}}
        }
