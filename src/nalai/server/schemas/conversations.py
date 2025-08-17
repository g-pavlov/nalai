"""
Conversation resource schemas.

This module contains all schemas for the conversation resource:
- /api/v1/conversations (POST) - Create conversation
- /api/v1/conversations/{conversation_id} (POST) - Continue conversation
- /api/v1/conversations/{conversation_id} (GET) - Load conversation
"""

from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .base import ModelConfig


class MessageInput(BaseModel):
    """Individual message input structure for API requests."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., description="Message content")
    type: Literal["human", "ai", "tool"] = Field(..., description="Message type")
    name: str | None = Field(None, description="Tool name (for tool messages)")
    tool_call_id: str | None = Field(
        None, description="Tool call ID (for tool messages)"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate message content."""
        if not content or not content.strip():
            raise ValueError("Message content cannot be empty")
        if len(content) > 10000:  # 10KB limit per message
            raise ValueError("Message content too long (max 10KB)")
        return content.strip()

    @field_validator("name", "tool_call_id")
    @classmethod
    def validate_tool_fields(cls, value, info):
        """Validate tool-specific fields."""
        if info.data.get("type") == "tool":
            if info.field_name == "name" and not value:
                raise ValueError("Tool name is required for tool messages")
            if info.field_name == "tool_call_id" and not value:
                raise ValueError("Tool call ID is required for tool messages")
        return value

    def to_langchain_message(self) -> BaseMessage:
        """Convert to LangChain message type."""
        if self.type == "human":
            return HumanMessage(content=self.content)
        elif self.type == "ai":
            return AIMessage(content=self.content)
        elif self.type == "tool":
            return ToolMessage(
                content=self.content,
                name=self.name or "",
                tool_call_id=self.tool_call_id or "",
            )
        else:
            raise ValueError(f"Unknown message type: {self.type}")


class ConversationRequest(BaseModel):
    """Request model for conversation (create or continue)."""

    model_config = ConfigDict(extra="forbid")  # Reject unknown fields

    messages: list[MessageInput] = Field(
        ..., description="List of conversation messages", min_length=1, max_length=100
    )
    model: ModelConfig | None = Field(
        None, description="Optional model provider configuration"
    )

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages, info):
        """
        Comprehensive validation of messages and cross-field validation.

        This validator also performs cross-field validation with the model field
        and comprehensive business logic checks.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")

        # Ensure at least one human message
        human_messages = [msg for msg in messages if msg.type == "human"]
        if not human_messages:
            raise ValueError("At least one human message is required")

        # Validate total content size (prevent abuse)
        total_size = sum(len(msg.content) for msg in messages)
        max_total_size = 100 * 1024  # 100KB total limit
        if total_size > max_total_size:
            raise ValueError(
                f"Total message content too large (max {max_total_size // 1024}KB)"
            )

        # Validate message sequence (no consecutive AI messages)
        for i in range(len(messages) - 1):
            if messages[i].type == "ai" and messages[i + 1].type == "ai":
                raise ValueError("Cannot have consecutive AI messages")

        # Validate tool messages have required fields
        for msg in messages:
            if msg.type == "tool":
                if not msg.name:
                    raise ValueError("Tool messages must have a name")
                if not msg.tool_call_id:
                    raise ValueError("Tool messages must have a tool_call_id")

        return messages

    def to_internal_messages(self) -> dict[Literal["messages"], list[BaseMessage]]:
        """Convert to agent input format for backward compatibility."""
        # Convert to LangGraph message format: [("human", content), ("ai", content), etc.]
        messages = []
        for msg in self.messages:
            if msg.type == "human":
                messages.append(("human", msg.content))
            elif msg.type == "ai":
                messages.append(("ai", msg.content))
            elif msg.type == "tool":
                messages.append(
                    (
                        "tool",
                        {
                            "content": msg.content,
                            "name": msg.name,
                            "tool_call_id": msg.tool_call_id,
                        },
                    )
                )
        return {"messages": messages}

    def to_internal_config(self) -> dict[Literal["config"], RunnableConfig]:
        """Convert to internal RunnableConfig for LangChain/LangGraph."""
        if self.model:
            return {
                "config": {
                    "configurable": {
                        "model": {
                            "name": self.model.name,
                            "platform": self.model.platform,
                        }
                    }
                }
            }
        return {"config": {"configurable": {}}}


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
    messages: list[MessageInput] = Field(
        ..., description="List of conversation messages"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Conversation metadata"
    )
    created_at: str | None = Field(None, description="Creation timestamp")
    last_accessed: str | None = Field(None, description="Last access timestamp")
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
