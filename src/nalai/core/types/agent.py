"""
Agent interface and types.

This module defines the main agent interface and related types
for core package interactions, separating HTTP concerns from business logic.
"""

from collections.abc import AsyncGenerator
from typing import Protocol

from pydantic import BaseModel, Field

from .messages import InputMessage, OutputMessage, ToolCallDecision
from .streaming import StreamingChunk


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
        messages: list[InputMessage],
        conversation_id: str | None,
        config: dict,
        previous_response_id: str | None = None,
    ) -> tuple[list[OutputMessage], ConversationInfo]:
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
        messages: list[InputMessage],
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
    ) -> tuple[list[InputMessage | OutputMessage], ConversationInfo]:
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
        resume_decision: ToolCallDecision,
        conversation_id: str,
        config: dict,
    ) -> tuple[list[InputMessage | OutputMessage], ConversationInfo]:
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
        resume_decision: ToolCallDecision,
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
    ) -> tuple[list[InputMessage | OutputMessage], ConversationInfo]:
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
        edited_messages: list[InputMessage | OutputMessage],
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
