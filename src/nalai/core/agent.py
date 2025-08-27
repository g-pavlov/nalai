"""
Agent interface and types.

This module defines the main agent interface and related types
for core package interactions, separating HTTP concerns from business logic.
"""

from collections.abc import AsyncGenerator
from typing import Any, Literal, Protocol

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_validator

# ===== Core Data Models =====
# These models represent the canonical data structure for messages and streaming chunks
# They are protocol-independent and contain all necessary data for any output format


class ToolCall(BaseModel):
    """Core representation of a tool call with all necessary data."""

    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    type: str | None = None

    class Config:
        extra = "allow"  # Allow extra fields during construction
        validate_assignment = True


class Message(BaseModel):
    """Core representation of a message with all necessary data."""

    content: str
    type: str = Field(description="human, ai, tool")
    id: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_chunks: list[Any] | None = None
    invalid_tool_calls: list[Any] | None = None
    response_metadata: dict[str, Any] | None = None
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    tool_call_id: str | None = None  # For tool messages

    class Config:
        extra = "allow"  # Allow extra fields during construction
        validate_assignment = True


class BaseStreamingChunk(BaseModel):
    """Base class for all streaming chunks."""

    type: str
    conversation_id: str

    class Config:
        extra = "allow"
        validate_assignment = True


class UpdateChunk(BaseStreamingChunk):
    """Update chunk for workflow progress events."""

    type: Literal["update"] = "update"
    task: str  # event_key
    messages: list["Message"] = Field(default_factory=list)


class MessageChunk(BaseStreamingChunk):
    """Message chunk for AI message content."""

    type: Literal["message"] = "message"
    task: str  # langgraph_node
    content: str
    id: str
    metadata: dict[str, Any] | None = None


class ToolCallChunk(BaseStreamingChunk):
    """Tool call chunk for AI tool call events."""

    type: Literal["tool_call"] = "tool_call"
    task: str  # langgraph_node
    id: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class InterruptChunk(BaseStreamingChunk):
    """Interrupt chunk for human-in-the-loop events."""

    type: Literal["interrupt"] = "interrupt"
    id: str
    value: dict[str, Any]  # serialized action request, config, description


class ToolChunk(BaseStreamingChunk):
    """Tool chunk for tool execution results."""

    type: Literal["tool"] = "tool"
    id: str
    status: Literal["success", "error", "pending"] = "success"
    tool_call_id: str
    content: str
    tool_name: str


# Union type for all chunk types
StreamingChunk = UpdateChunk | MessageChunk | ToolCallChunk | InterruptChunk | ToolChunk


class ModelConfig(BaseModel):
    name: str
    platform: str


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


class SelectApi(BaseModel):
    """A selected API"""

    api_title: str = Field(description="The title of a selected API")
    api_version: str = Field(description="The version of a selected API")


class SelectedApis(BaseModel):
    """List of APIs selected by the LLM"""

    selected_apis: list[SelectApi] = Field(
        default_factory=list,
        description="List of selected APIs. May be empty if no relevant APIs are found.",
    )


class ConversationInfo(BaseModel):
    """Conversation metadata and information."""

    conversation_id: str = Field(..., description="Unique conversation identifier")
    created_at: str | None = Field(
        None, description="ISO timestamp when conversation was created"
    )
    last_accessed: str | None = Field(None, description="ISO timestamp of last access")
    status: str = Field(
        "active", description="Conversation status (active, completed, interrupted)"
    )
    preview: str | None = Field(None, description="Conversation preview/summary")
    interrupt_info: dict | None = Field(
        None, description="Interrupt information if conversation was interrupted"
    )


class Conversation(ConversationInfo):
    """Full conversation with messages."""

    messages: list[Message] = Field(..., description="Conversation messages")


class ResumeDecision(BaseModel):
    """Resume decision input for interrupted conversations."""

    action: Literal["accept", "reject", "edit", "feedback"] = Field(
        ..., description="The action to take on the interrupt"
    )
    args: Any = Field(
        None,
        description="Optional arguments for the action (e.g., edited args for 'edit' action)",
    )
    tool_call_id: str = Field(..., description="The tool call ID to act upon")


class ConversationIdPathParam(BaseModel):
    """Path parameter for conversation ID validation."""

    conversation_id: str = Field(..., description="Conversation ID")

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: str) -> str:
        """Validate conversation ID format."""
        import uuid

        try:
            uuid.UUID(v)
        except ValueError as e:
            raise ValueError(f"Invalid conversation ID format: {e}") from e
        return v


# Exceptions
class Error(Exception):
    """Base exception for agent operations."""

    def __init__(
        self, message: str, error_code: str = "INTERNAL_ERROR", context: dict = None
    ):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(message)


class AccessDeniedError(Error):
    """Raised when access to conversation is denied."""

    def __init__(
        self, message: str = "Access denied to conversation", context: dict = None
    ):
        super().__init__(message, "ACCESS_DENIED", context)


class ConversationNotFoundError(Error):
    """Raised when conversation is not found."""

    def __init__(self, message: str = "Conversation not found", context: dict = None):
        super().__init__(message, "NOT_FOUND", context)


class ValidationError(Error):
    """Raised when request validation fails."""

    def __init__(self, message: str, context: dict = None):
        super().__init__(message, "VALIDATION_ERROR", context)


class ClientError(Error):
    """Raised when client request is invalid (4xx errors)."""

    def __init__(self, message: str, http_status: int = 400, context: dict = None):
        self.http_status = http_status
        super().__init__(message, "CLIENT_ERROR", context)


class InvocationError(Error):
    """Raised when agent invocation fails."""

    def __init__(
        self,
        message: str = "Agent invocation failed",
        context: dict = None,
        original_exception: Exception = None,
    ):
        self.original_exception = original_exception
        super().__init__(message, "AGENT_ERROR", context)


class Agent(Protocol):
    """Agent interface for business operations."""

    async def chat(
        self,
        messages: list[BaseMessage],
        conversation_id: str | None,
        config: dict,
        previous_response_id: str | None = None,
    ) -> tuple[list[Message], ConversationInfo]:
        """
        Start a new conversation or continue an existing one based on conversation_id.

        Args:
            messages: List of conversation messages
            conversation_id: Optional conversation ID. If None, starts new conversation
            config: Agent configuration

        Returns:
            tuple: (messages, conversation_info)
                - messages: List of conversation messages including response
                - conversation_info: Conversation metadata

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation_id provided but not found
            InvocationError: If agent invocation fails
        """
        ...

    async def chat_streaming(
        self,
        messages: list[BaseMessage],
        conversation_id: str | None,
        config: dict,
        previous_response_id: str | None = None,
    ) -> tuple[AsyncGenerator[StreamingChunk, None], ConversationInfo]:
        """
        Stream conversation events.

        Args:
            messages: List of conversation messages
            conversation_id: Optional conversation ID. If None, starts new conversation
            config: Agent configuration

        Returns:
            tuple: (stream_generator, conversation_info)
                - stream_generator: AsyncGenerator yielding StreamingChunk objects
                - conversation_info: Conversation metadata

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation_id provided but not found
            InvocationError: If agent invocation fails
        """
        ...

    async def load_conversation(
        self,
        conversation_id: str,
        config: dict,
    ) -> tuple[list[Message], ConversationInfo]:
        """
        Load conversation state.

        Args:
            conversation_id: The conversation ID to load
            config: Agent configuration

        Returns:
            tuple: (messages, conversation_info)
                - messages: List of conversation messages
                - conversation_info: Conversation metadata

        Raises:
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation is not found
            InvocationError: If loading fails
        """
        ...

    async def list_conversations(
        self,
        config: dict,
    ) -> list[ConversationInfo]:
        """
        List user's conversations.

        Args:
            config: Agent configuration

        Returns:
            list[ConversationInfo]: List of conversation summaries with previews

        Raises:
            InvocationError: If listing fails
        """
        ...

    async def delete_conversation(
        self,
        conversation_id: str,
        config: dict,
    ) -> bool:
        """
        Delete a conversation.

        Args:
            conversation_id: The conversation ID to delete
            config: Agent configuration

        Returns:
            bool: True if deleted successfully, False if not found

        Raises:
            AccessDeniedError: If access to conversation is denied
            InvocationError: If deletion fails
        """
        ...

    async def resume_interrupted(
        self,
        resume_decision: ResumeDecision,
        conversation_id: str,
        config: dict,
    ) -> tuple[list[Message], ConversationInfo]:
        """
        Resume an interrupted conversation.

        Args:
            resume_decision: Resume decision with action and optional args
            conversation_id: The conversation ID to resume
            config: Agent configuration

        Returns:
            tuple: (messages, conversation_info)
                - messages: List of conversation messages including response
                - conversation_info: Conversation metadata

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation is not found
            InvocationError: If resume fails
        """
        ...

    async def resume_interrupted_streaming(
        self,
        resume_decision: ResumeDecision,
        conversation_id: str,
        config: dict,
    ) -> tuple[AsyncGenerator[StreamingChunk, None], ConversationInfo]:
        """
        Stream resume conversation events.

        Args:
            resume_decision: Resume decision with action and optional args
            conversation_id: The conversation ID to resume
            config: Agent configuration

        Returns:
            tuple: (stream_generator, conversation_info)
                - stream_generator: Async generator yielding StreamingChunk objects
                - conversation_info: Conversation metadata

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation is not found
            InvocationError: If resume fails
        """
        ...

    async def resume_from_checkpoint(
        self,
        conversation_id: str,
        checkpoint_id: str,
        config: dict,
    ) -> tuple[list[Message], ConversationInfo]:
        """
        Resume conversation from a specific checkpoint.

        This allows restarting from any point in the conversation history,
        potentially after editing messages.

        Args:
            conversation_id: The conversation ID to resume
            checkpoint_id: The specific checkpoint ID to resume from
            config: Agent configuration

        Returns:
            tuple: (messages, conversation_info)
                - messages: List of conversation messages from the checkpoint
                - conversation_info: Conversation metadata

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation or checkpoint is not found
            InvocationError: If resume fails
        """
        ...

    async def list_conversation_checkpoints(
        self,
        conversation_id: str,
        config: dict,
    ) -> list[dict]:
        """
        List all checkpoints for a conversation.

        This enables users to see the conversation history and choose
        which checkpoint to resume from.

        Args:
            conversation_id: The conversation ID to list checkpoints for
            config: Agent configuration

        Returns:
            list[dict]: List of checkpoint information with IDs, timestamps, and versions

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation is not found
            InvocationError: If listing fails
        """
        ...

    async def edit_conversation_checkpoint(
        self,
        conversation_id: str,
        checkpoint_id: str,
        edited_messages: list[BaseMessage],
        config: dict,
    ) -> bool:
        """
        Edit a specific checkpoint with new messages.

        This allows users to modify conversation history and resume
        from the edited state.

        Args:
            conversation_id: The conversation ID containing the checkpoint
            checkpoint_id: The specific checkpoint ID to edit
            edited_messages: New list of messages to replace the checkpoint content
            config: Agent configuration

        Returns:
            bool: True if edited successfully

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation or checkpoint is not found
            InvocationError: If editing fails
        """
        ...
