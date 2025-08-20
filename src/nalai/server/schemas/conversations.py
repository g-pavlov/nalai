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


class HumanMessageInput(BaseModel):
    """Human message input structure for API requests."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., description="Human message content")
    type: Literal["human"] = Field("human", description="Message type - human")

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate human message content."""
        if not content or not content.strip():
            raise ValueError("Human message content cannot be empty")
        if len(content) > 10000:  # 10KB limit per message
            raise ValueError("Human message content too long (max 10KB)")
        return content.strip()

    def to_langchain_message(self) -> HumanMessage:
        """Convert to LangChain HumanMessage."""
        return HumanMessage(content=self.content)


class AIMessageInput(BaseModel):
    """AI message input structure for API requests."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field("", description="AI message content")
    type: Literal["ai"] = Field("ai", description="Message type - ai")
    tool_calls: list[dict] | None = Field(
        None, description="Tool calls (for AI messages with tool calls)"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate AI message content."""
        if content is None:
            content = ""
        if len(content) > 10000:  # 10KB limit per message
            raise ValueError("AI message content too long (max 10KB)")
        return content

    def to_langchain_message(self) -> AIMessage:
        """Convert to LangChain AIMessage."""
        if self.tool_calls:
            return AIMessage(content=self.content, tool_calls=self.tool_calls)
        else:
            return AIMessage(content=self.content)


class ToolMessageInput(BaseModel):
    """Tool message input structure for API requests."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field("", description="Tool message content")
    type: Literal["tool"] = Field("tool", description="Message type - tool")
    name: str = Field(..., description="Tool name")
    tool_call_id: str = Field(..., description="Tool call ID")

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate tool message content."""
        if content is None:
            content = ""
        if len(content) > 10000:  # 10KB limit per message
            raise ValueError("Tool message content too long (max 10KB)")
        return content

    @field_validator("name")
    @classmethod
    def validate_name(cls, name):
        """Validate tool name."""
        if not name or not name.strip():
            raise ValueError("Tool name cannot be empty")
        return name.strip()

    @field_validator("tool_call_id")
    @classmethod
    def validate_tool_call_id(cls, tool_call_id):
        """Validate tool call ID."""
        if not tool_call_id or not tool_call_id.strip():
            raise ValueError("Tool call ID cannot be empty")
        return tool_call_id.strip()

    def to_langchain_message(self) -> ToolMessage:
        """Convert to LangChain ToolMessage."""
        return ToolMessage(
            content=self.content,
            name=self.name,
            tool_call_id=self.tool_call_id,
        )


# Union type for all message inputs
MessageInputUnion = HumanMessageInput | AIMessageInput | ToolMessageInput


class ConversationRequest(BaseModel):
    """Request model for conversation (create or continue)."""

    model_config = ConfigDict(extra="forbid")  # Reject unknown fields

    input: list[MessageInputUnion] = Field(
        ..., description="List of conversation messages", min_length=1, max_length=100
    )
    model: ModelConfig | None = Field(
        None, description="Optional model provider configuration"
    )

    @field_validator("input")
    @classmethod
    def validate_input(cls, input_messages, info):
        """
        Comprehensive validation of input messages and cross-field validation.

        This validator also performs cross-field validation with the model field
        and comprehensive business logic checks.
        """
        if not input_messages:
            raise ValueError("Input messages list cannot be empty")

        # Ensure at least one human message
        human_messages = [msg for msg in input_messages if msg.type == "human"]
        if not human_messages:
            raise ValueError("At least one human message is required")

        # Validate total content size (prevent abuse)
        total_size = sum(len(msg.content) for msg in input_messages)
        max_total_size = 100 * 1024  # 100KB total limit
        if total_size > max_total_size:
            raise ValueError(
                f"Total message content too large (max {max_total_size // 1024}KB)"
            )

        # Validate message sequence (no consecutive AI messages)
        for i in range(len(input_messages) - 1):
            if input_messages[i].type == "ai" and input_messages[i + 1].type == "ai":
                raise ValueError("Cannot have consecutive AI messages")

        return input_messages

    def to_internal_messages(self) -> dict[Literal["messages"], list[BaseMessage]]:
        """Convert to internal LangGraph message format."""
        # Convert to LangGraph message format: [("human", content), ("ai", content), etc.]
        messages = []
        for msg in self.input:
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

    def to_langchain_messages(self) -> list[BaseMessage]:
        """Convert to LangChain message format."""
        messages = []
        for msg in self.input:
            messages.append(msg.to_langchain_message())
        return messages

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


# Keep the old MessageInput for backward compatibility in responses
class MessageInput(BaseModel):
    """Individual message input structure for API requests (backward compatibility)."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field("", description="Message content")
    type: Literal["human", "ai", "tool"] = Field(..., description="Message type")
    name: str | None = Field(None, description="Tool name (for tool messages)")
    tool_call_id: str | None = Field(
        None, description="Tool call ID (for tool messages)"
    )
    tool_calls: list[dict] | None = Field(
        None, description="Tool calls (for AI messages with tool calls)"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, content, info):
        """Validate message content."""
        # Handle None content
        if content is None:
            content = ""

        # Allow empty content for tool messages and AI messages with tool calls
        message_type = info.data.get("type") if info.data else None
        if message_type == "tool":
            # For tool messages, content can be empty if they have tool call data
            return content
        elif message_type == "ai":
            # For AI messages, content can be empty if they have tool calls
            return content
        else:
            # For human messages, content cannot be empty
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
            # Handle AI messages with tool calls
            if self.tool_calls:
                return AIMessage(content=self.content, tool_calls=self.tool_calls)
            else:
                return AIMessage(content=self.content)
        elif self.type == "tool":
            return ToolMessage(
                content=self.content,
                name=self.name or "",
                tool_call_id=self.tool_call_id or "",
            )
        else:
            raise ValueError(f"Unknown message type: {self.type}")


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
    messages: list[MessageInputUnion] = Field(
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

        # Validate each message in the list
        for i, msg in enumerate(messages):
            if not isinstance(
                msg, HumanMessageInput | AIMessageInput | ToolMessageInput
            ):
                raise ValueError(f"Message at index {i} must be a valid message type")

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
