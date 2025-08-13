"""
Input models for API Assistant server.

This module contains models for incoming requests and messages:
- MessageInput: Individual message structure
- AgentInput: Collection of messages for agent processing
- AgentInvokeRequest: Synchronous agent invocation request
- AgentStreamEventsRequest: Event streaming request
- ToolInterruptRequest: Tool interrupt operation request
"""

import uuid
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import AgentConfig


class InterruptResponse(BaseModel):
    """Type-safe model for interrupt response protocol."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["accept", "edit", "response"] = Field(
        ..., description="Response type"
    )
    args: dict | str | None = Field(
        None, description="Arguments for edit or response types"
    )

    @field_validator("args")
    @classmethod
    def validate_args(cls, args, info):
        """Validate that args is provided for response types that require it."""
        if info.data.get("type") in ["edit", "response"] and args is None:
            raise ValueError("Args are required for 'edit' or 'response' types")
        return args


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

    @classmethod
    def from_langchain_message(cls, message: BaseMessage) -> "MessageInput":
        """Create MessageInput from LangChain message."""
        if isinstance(message, HumanMessage):
            return cls(content=message.content, type="human")
        elif isinstance(message, AIMessage):
            return cls(content=message.content, type="ai")
        elif isinstance(message, ToolMessage):
            return cls(
                content=message.content,
                type="tool",
                name=message.name,
                tool_call_id=message.tool_call_id,
            )
        else:
            # Handle other message types by converting to string
            return cls(content=str(message.content), type="ai")


class AgentInput(BaseModel):
    """Input data for the agent."""

    model_config = ConfigDict(extra="forbid")

    messages: list[MessageInput] = Field(
        ..., description="List of conversation messages", min_length=1, max_length=100
    )

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        """Validate that messages list is not empty and contains valid message types."""
        if not messages:
            raise ValueError("Messages list cannot be empty")

        # Ensure at least one human message
        human_messages = [msg for msg in messages if msg.type == "human"]
        if not human_messages:
            raise ValueError("At least one human message is required")

        return messages

    def to_langchain_messages(self) -> list[BaseMessage]:
        """Convert to list of LangChain messages."""
        return [msg.to_langchain_message() for msg in self.messages]

    @classmethod
    def from_langchain_messages(cls, messages: list[BaseMessage]) -> "AgentInput":
        """Create AgentInput from list of LangChain messages."""
        message_inputs = [MessageInput.from_langchain_message(msg) for msg in messages]
        return cls(messages=message_inputs)

    def model_dump(self, **kwargs):
        """Custom dump method that converts to LangGraph format."""
        data = super().model_dump(**kwargs)
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
        data["messages"] = messages
        return data


class AgentInvokeRequest(BaseModel):
    """Request model for agent invocation."""

    model_config = ConfigDict(extra="forbid")  # Reject unknown fields

    input: AgentInput = Field(..., description="Input data for the agent")
    config: AgentConfig | None = Field(None, description="Optional configuration")


class AgentStreamEventsRequest(BaseModel):
    """Request model for agent stream events."""

    model_config = ConfigDict(extra="forbid")  # Reject unknown fields

    input: AgentInput = Field(..., description="Input data for the agent")
    config: AgentConfig | None = Field(None, description="Optional configuration")
    allowed_events: list[str] | None = Field(
        None,
        description="List of event types to allow, None means default events",
        max_length=50,
    )
    debug: bool = Field(
        False, description="Enable debug mode to bypass event filtering"
    )

    @field_validator("allowed_events")
    @classmethod
    def validate_allowed_events(cls, allowed_events):
        """Validate that allowed_events contains valid event types."""
        if allowed_events is not None:
            valid_event_types = {
                "on_chat_model_stream",
                "on_chat_model_start",
                "on_chat_model_end",
                "on_tool_start",
                "on_tool_stream",
                "on_tool_end",
                "on_chain_stream",
                "on_chain_start",
                "on_chain_end",
            }
            invalid_events = [
                event for event in allowed_events if event not in valid_event_types
            ]
            if invalid_events:
                raise ValueError(
                    f"Invalid event types: {invalid_events}. Valid types: {list(valid_event_types)}"
                )
        return allowed_events


class ToolInterruptRequest(BaseModel):
    """Request model for tool-level interrupt operations."""

    thread_id: str
    response_type: Literal["accept", "edit", "response"]
    args: dict | str | None = (
        None  # Used for "edit" (updated args) or "response" (feedback)
    )

    @field_validator("args")
    @classmethod
    def validate_args(cls, args, info):
        """Validate that args is provided for response types that require it."""
        if info.data.get("response_type") in ["edit", "response"] and args is None:
            raise ValueError("Args are required for 'edit' or 'response' types")
        return args

    @field_validator("thread_id")
    @classmethod
    def validate_thread_id(cls, thread_id):
        """Validate that thread_id is either a valid UUID4 or a user-scoped thread ID."""
        # Check if it's a user-scoped thread ID (format: user:dev-user:uuid)
        if ":" in thread_id:
            parts = thread_id.split(":")
            if len(parts) == 3 and parts[0] == "user" and parts[1] == "dev-user":
                try:
                    uuid.UUID(parts[2], version=4)
                    return thread_id
                except ValueError:
                    raise ValueError("Invalid UUID in user-scoped thread_id") from None
            else:
                raise ValueError(
                    "Invalid user-scoped thread_id format. Expected: user:dev-user:uuid"
                )

        # Check if it's a plain UUID4
        try:
            uuid_obj = uuid.UUID(thread_id, version=4)
        except ValueError:
            raise ValueError(
                "thread_id must be a valid UUID4 or user-scoped thread ID"
            ) from None
        if str(uuid_obj) != thread_id:
            raise ValueError("thread_id must be a canonical UUID4 string")
        return thread_id
