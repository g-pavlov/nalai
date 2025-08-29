"""
LangChain cache integration for enhanced caching with similarity search and user isolation.

This module provides a LangChain-compatible cache implementation that uses the existing
CacheService as a backend, focusing only on the integration bridge to LangChain.
"""

import logging
from typing import Any

from langchain_core.caches import BaseCache
from langchain_core.messages import BaseMessage, HumanMessage

from ..config import settings
from ..utils.id_generator import generate_message_id
from .cache_service import CacheService, get_cache_service

logger = logging.getLogger(__name__)


class EnhancedLangChainCache(BaseCache):
    """
    Enhanced LangChain cache with similarity search and user isolation.

    Uses the existing CacheService as a backend, providing:
    - Token-based similarity search for semantic matching
    - User-scoped cache isolation
    - Configurable tool call caching
    - Performance optimizations
    """

    def __init__(
        self,
        cache_service: CacheService | None = None,
        similarity_threshold: float | None = None,
        similarity_enabled: bool | None = None,
        cache_tool_calls: bool | None = None,
    ):
        """
        Initialize the enhanced LangChain cache.

        Args:
            cache_service: CacheService instance to use as backend (uses global if None)
            similarity_threshold: Override similarity threshold
            similarity_enabled: Override similarity enabled setting
            cache_tool_calls: Override tool calls caching setting
        """
        # Use provided cache service or get global one
        self.cache_service = cache_service or get_cache_service()

        # Override settings if provided
        self.similarity_threshold = (
            similarity_threshold or settings.cache_similarity_threshold
        )
        self.similarity_enabled = (
            similarity_enabled
            if similarity_enabled is not None
            else settings.cache_similarity_enabled
        )
        self.cache_tool_calls = (
            cache_tool_calls
            if cache_tool_calls is not None
            else settings.cache_tool_calls
        )

        logger.debug(
            f"Enhanced LangChain cache initialized: "
            f"similarity_threshold={self.similarity_threshold}, "
            f"similarity_enabled={self.similarity_enabled}, "
            f"cache_tool_calls={self.cache_tool_calls}"
        )

    def _extract_message_content(self, prompt: str | list[BaseMessage]) -> str:
        """
        Extract message content for similarity matching.

        Args:
            prompt: The input prompt

        Returns:
            Extracted message content string
        """
        if isinstance(prompt, str):
            return prompt

        # Extract content from the last message
        if prompt and len(prompt) > 0:
            last_message = prompt[-1]
            if hasattr(last_message, "content") and last_message.content:
                return str(last_message.content)

        return ""

    def _convert_to_messages(
        self, prompt: str | list[BaseMessage]
    ) -> list[BaseMessage]:
        """
        Convert prompt to list of messages for CacheService.

        Args:
            prompt: The input prompt

        Returns:
            List of BaseMessage objects
        """
        if isinstance(prompt, str):
            return [HumanMessage(content=prompt, id=generate_message_id())]
        else:
            return prompt

    def _extract_user_id_from_metadata(
        self, metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Extract user ID from LangChain metadata.

        Args:
            metadata: LangChain metadata dictionary

        Returns:
            User ID string
        """
        if metadata and "user_id" in metadata:
            return metadata["user_id"]
        return "anonymous"

    async def lookup_async(
        self,
        prompt: str | list[BaseMessage],
        llm_string: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | list[BaseMessage] | None:
        """
        Async version: Look up a cached response for the given prompt and LLM.

        Args:
            prompt: The input prompt
            llm_string: The LLM identifier string
            metadata: LangChain metadata (may contain user_id)

        Returns:
            Cached response if found and not expired, None otherwise
        """
        try:
            # Extract user ID from metadata
            user_id = self._extract_user_id_from_metadata(metadata)

            # Convert to messages for CacheService
            messages = self._convert_to_messages(prompt)

            # 1. Try exact match first
            try:
                cached_result = await self.cache_service.get_async(messages, user_id)
                if cached_result:
                    cached_response, cached_tool_calls = cached_result
                    logger.debug(f"Cache hit (exact match) for user {user_id}")
                    return cached_response
            except Exception as e:
                logger.warning(f"Cache service error during exact match lookup: {e}")
                # Continue to similarity search or return None

            # 2. Try similarity search if enabled
            if self.similarity_enabled:
                try:
                    message_content = self._extract_message_content(prompt)
                    if message_content:
                        similar_responses = await self.cache_service.find_similar_cached_responses_async(
                            message_content, user_id, self.similarity_threshold
                        )

                        if similar_responses:
                            (
                                best_content,
                                best_response,
                                best_tool_calls,
                                similarity_score,
                            ) = similar_responses[0]
                            logger.debug(
                                f"Cache hit (similarity) for user {user_id} with score {similarity_score:.3f}"
                            )
                            return best_response
                except Exception as e:
                    logger.warning(f"Cache service error during similarity search: {e}")
                    # Continue to return None

            logger.debug(f"Cache miss for user {user_id}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in cache lookup: {e}")
            return None

    def lookup(
        self,
        prompt: str | list[BaseMessage],
        llm_string: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | list[BaseMessage] | None:
        """
        Synchronous wrapper for lookup_async.
        Note: This creates a new event loop if one doesn't exist.
        For better performance in async contexts, use lookup_async() directly.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, but this is a sync method
                logger.warning(
                    "Using sync lookup() in async context. Consider using lookup_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.lookup_async(prompt, llm_string, metadata)
                    )
                    return future.result()
            else:
                # We're in a sync context, safe to run
                return asyncio.run(self.lookup_async(prompt, llm_string, metadata))
        except RuntimeError:
            # No event loop, safe to create one
            return asyncio.run(self.lookup_async(prompt, llm_string, metadata))

    async def update_async(
        self,
        prompt: str | list[BaseMessage],
        llm_string: str,
        response: str | list[BaseMessage],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Async version: Update the cache with a new response.

        Args:
            prompt: The input prompt
            llm_string: The LLM identifier string
            response: The response to cache
            metadata: LangChain metadata (may contain user_id)
        """
        try:
            # Extract user ID from metadata
            user_id = self._extract_user_id_from_metadata(metadata)

            # Convert to messages for CacheService
            messages = self._convert_to_messages(prompt)

            # Convert response to string if it's a message list
            if isinstance(response, list) and response:
                # Extract content from the first message
                response_content = (
                    response[0].content
                    if hasattr(response[0], "content")
                    else str(response[0])
                )
            else:
                response_content = str(response)

            # Extract tool calls if present
            tool_calls = None
            if isinstance(response, list) and response:
                tool_calls = getattr(response[0], "tool_calls", None)

            # Cache the response
            try:
                await self.cache_service.set_async(
                    messages=messages,
                    response=response_content,
                    tool_calls=tool_calls,
                    user_id=user_id,
                )
                logger.debug(f"Cached response for user {user_id}")
            except Exception as e:
                logger.warning(f"Cache service error during update: {e}")
                # Don't raise exception - cache failures shouldn't break LangChain operations

        except Exception as e:
            logger.error(f"Unexpected error in cache update: {e}")
            # Don't raise exception - cache failures shouldn't break LangChain operations

    def update(
        self,
        prompt: str | list[BaseMessage],
        llm_string: str,
        response: str | list[BaseMessage],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Synchronous wrapper for update_async.
        Note: This creates a new event loop if one doesn't exist.
        For better performance in async contexts, use update_async() directly.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, but this is a sync method
                logger.warning(
                    "Using sync update() in async context. Consider using update_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.update_async(prompt, llm_string, response, metadata),
                    )
                    future.result()
            else:
                # We're in a sync context, safe to run
                asyncio.run(self.update_async(prompt, llm_string, response, metadata))
        except RuntimeError:
            # No event loop, safe to create one
            asyncio.run(self.update_async(prompt, llm_string, response, metadata))

    async def clear_async(self, user_id: str | None = None) -> None:
        """
        Async version: Clear cache entries.

        Args:
            user_id: If provided, clear only entries for this user
        """
        if user_id:
            await self.cache_service.clear_user_cache_async(user_id)
            logger.debug(f"Cleared cache for user {user_id}")
        else:
            await self.cache_service.clear_async()
            logger.debug("Cleared all cache entries")

    def clear(self, user_id: str | None = None) -> None:
        """
        Synchronous wrapper for clear_async.
        Note: This creates a new event loop if one doesn't exist.
        For better performance in async contexts, use clear_async() directly.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning(
                    "Using sync clear() in async context. Consider using clear_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.clear_async(user_id))
                    future.result()
            else:
                asyncio.run(self.clear_async(user_id))
        except RuntimeError:
            asyncio.run(self.clear_async(user_id))

    async def get_stats_async(self) -> dict[str, Any]:
        """
        Async version: Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = await self.cache_service.get_stats_async()

        # Add LangChain-specific stats
        stats.update(
            {
                "similarity_enabled": self.similarity_enabled,
                "similarity_threshold": self.similarity_threshold,
                "cache_tool_calls": self.cache_tool_calls,
            }
        )

        return stats

    def get_stats(self) -> dict[str, Any]:
        """
        Synchronous wrapper for get_stats_async.
        Note: This creates a new event loop if one doesn't exist.
        For better performance in async contexts, use get_stats_async() directly.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning(
                    "Using sync get_stats() in async context. Consider using get_stats_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.get_stats_async())
                    return future.result()
            else:
                return asyncio.run(self.get_stats_async())
        except RuntimeError:
            return asyncio.run(self.get_stats_async())


# Factory function for easy integration
def create_enhanced_langchain_cache(
    cache_service: CacheService | None = None,
    similarity_threshold: float | None = None,
    similarity_enabled: bool | None = None,
    cache_tool_calls: bool | None = None,
) -> EnhancedLangChainCache:
    """
    Create an enhanced LangChain cache instance.

    Args:
        cache_service: CacheService instance to use as backend
        similarity_threshold: Override similarity threshold
        similarity_enabled: Override similarity enabled setting
        cache_tool_calls: Override tool calls caching setting

    Returns:
        Configured EnhancedLangChainCache instance
    """
    return EnhancedLangChainCache(
        cache_service=cache_service,
        similarity_threshold=similarity_threshold,
        similarity_enabled=similarity_enabled,
        cache_tool_calls=cache_tool_calls,
    )
