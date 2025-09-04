"""
Service interfaces for dependency injection.

This module defines the public interfaces that external services
can implement to integrate with the core agent functionality.
"""

from typing import Any, Protocol


class CheckpointingService(Protocol):
    """Public interface for checkpointing service implementations."""

    def get_checkpointer(self) -> Any:
        """Get the LangGraph checkpointer instance.

        Returns:
            Any: LangGraph checkpointer instance (e.g., MemorySaver, PostgresSaver)
        """
        ...

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics.

        Returns:
            dict[str, Any]: Statistics about checkpointing operations
        """
        ...

    async def health_check(self) -> bool:
        """Check if the checkpointing service is healthy.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        ...


class CacheService(Protocol):
    """Public interface for cache service implementations."""

    async def get(
        self, messages: list[Any], user_id: str
    ) -> tuple[Any, list[Any]] | None:
        """Get cached response for messages and user.

        Args:
            messages: List of conversation messages
            user_id: User identifier for cache isolation

        Returns:
            tuple[Any, list[Any]] | None: Cached (response, tool_calls) or None
        """
        ...

    async def set(
        self,
        messages: list[Any],
        response: str,
        tool_calls: list[Any] | None,
        user_id: str,
        ttl_seconds: int = 3600,
    ) -> None:
        """Set cached response for messages and user.

        Args:
            messages: List of conversation messages
            response: AI response content
            tool_calls: List of tool calls (if any)
            user_id: User identifier for cache isolation
            ttl_seconds: Time-to-live in seconds
        """
        ...

    async def find_similar_cached_responses(
        self, message: Any, user_id: str, similarity_threshold: float = 0.8
    ) -> list[tuple[Any, list[Any]]]:
        """Find similar cached responses for a message.

        Args:
            message: Message to find similar responses for
            user_id: User identifier for cache isolation
            similarity_threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            list[tuple[Any, list[Any]]]: List of similar cached (response, tool_calls)
        """
        ...

    async def clear_user_cache(self, user_id: str) -> int:
        """Clear all cache entries for a user.

        Args:
            user_id: User identifier

        Returns:
            int: Number of entries cleared
        """
        ...


class ModelService(Protocol):
    """Public interface for model service implementations."""

    def get_model_from_config(self, config: dict[str, Any], **kwargs: Any) -> Any:
        """Get configured model instance from config with additional parameters.

        Args:
            config: Model configuration dictionary
            **kwargs: Additional model initialization parameters

        Returns:
            Any: Configured model instance (e.g., BaseChatModel)
        """
        ...

    def get_model_id_from_config(self, config: dict[str, Any]) -> str:
        """Get model ID from configuration.

        Args:
            config: Model configuration dictionary

        Returns:
            str: Model identifier
        """
        ...

    @staticmethod
    def extract_message_content(message: Any) -> str:
        """Extract text content from a message object.

        Args:
            message: Message object (e.g., BaseMessage)

        Returns:
            str: Extracted text content
        """
        ...

    @staticmethod
    def get_context_window_size(model_name: str, platform: str) -> int:
        """Get context window size for a model.

        Args:
            model_name: Name of the model
            platform: Platform (e.g., 'openai', 'ollama', 'aws_bedrock')

        Returns:
            int: Context window size in tokens
        """
        ...


class APIService(Protocol):
    """Public interface for API docs service implementations."""

    def load_api_summaries(self, state: dict[str, Any]) -> dict[str, Any]:
        """Load API summaries from configured data path.

        Args:
            state: Current state dictionary

        Returns:
            dict[str, Any]: Updated state with API summaries
        """
        ...

    def load_openapi_specifications(self, state: dict[str, Any]) -> dict[str, Any]:
        """Load OpenAPI specifications for selected APIs.

        Args:
            state: Current state dictionary

        Returns:
            dict[str, Any]: Updated state with OpenAPI specifications
        """
        ...


class AuditService(Protocol):
    """Public interface for audit service implementations."""

    async def log_conversation_access_event(
        self,
        user_id: str,
        conversation_id: str,
        action: str,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log a conversation access event.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier
            action: Action performed (e.g., 'read', 'write', 'delete')
            success: Whether the action was successful
            metadata: Additional metadata
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session identifier
            request_id: Request identifier
        """
        ...

    async def log_thread_access(
        self,
        user_id: str,
        thread_id: str,
        action: str,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log a thread access event.

        Args:
            user_id: User identifier
            thread_id: Thread identifier
            action: Action performed
            success: Whether the action was successful
            metadata: Additional metadata
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session identifier
            request_id: Request identifier
        """
        ...


__all__ = [
    "CheckpointingService",
    "CacheService",
    "ModelService",
    "APIService",
    "AuditService",
]
