"""
Agent interface and types.

This module defines the main agent interface and related types
for core package interactions, separating HTTP concerns from business logic.
"""

from collections.abc import AsyncGenerator
from typing import Any, Literal, Protocol

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_validator


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


class Conversation(ConversationInfo):
    """Full conversation with messages."""

    messages: list[BaseMessage] = Field(..., description="Conversation messages")


class ResumeDecision(BaseModel):
    """Resume decision input for interrupted conversations."""

    action: Literal["accept", "reject", "edit", "feedback"] = Field(
        ..., description="The action to take on the interrupt"
    )
    args: Any = Field(
        None,
        description="Optional arguments for the action (e.g., edited args for 'edit' action)",
    )


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


class InvocationError(Error):
    """Raised when agent invocation fails."""

    def __init__(self, message: str = "Agent invocation failed", context: dict = None):
        super().__init__(message, "AGENT_ERROR", context)


class Agent(Protocol):
    """Agent interface for business operations."""

    async def chat(
        self,
        messages: list[BaseMessage],
        conversation_id: str | None,
        config: dict,
    ) -> tuple[list[BaseMessage], ConversationInfo]:
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
    ) -> tuple[AsyncGenerator[str, None], ConversationInfo]:
        """
        Stream conversation events.

        Args:
            messages: List of conversation messages
            conversation_id: Optional conversation ID. If None, starts new conversation
            config: Agent configuration

        Returns:
            tuple: (stream_generator, conversation_info)
                - stream_generator: AsyncGenerator yielding serialized SSE event strings
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
    ) -> tuple[list[BaseMessage], ConversationInfo]:
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
    ) -> tuple[list[BaseMessage], ConversationInfo]:
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
    ) -> tuple[AsyncGenerator[str, None], ConversationInfo]:
        """
        Stream resume interrupted conversation events.

        Args:
            resume_decision: Resume decision dict with "action" and optional "args"
            conversation_id: The conversation ID to resume
            config: Agent configuration

        Returns:
            tuple: (stream_generator, conversation_info)
                - stream_generator: AsyncGenerator yielding serialized SSE event strings
                - conversation_info: Conversation metadata

        Raises:
            ValidationError: If input validation fails
            AccessDeniedError: If access to conversation is denied
            ConversationNotFoundError: If conversation is not found
            InvocationError: If resume fails
        """
        ...
