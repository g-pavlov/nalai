"""
Tests for LangChain cache integration with async support.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.nalai.services.cache_service import CacheService
from src.nalai.services.langchain_cache import (
    EnhancedLangChainCache,
    create_enhanced_langchain_cache,
)


class TestEnhancedLangChainCache:
    """Test enhanced LangChain cache functionality."""

    @pytest.mark.asyncio
    async def test_async_lookup_and_update(self):
        """Test async lookup and update operations."""
        # Create cache service
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Create LangChain cache
        langchain_cache = EnhancedLangChainCache(cache_service=cache_service)

        # Test messages
        messages = [HumanMessage(content="Hello, how are you?")]
        response = AIMessage(content="I'm doing well, thank you!")

        # Test async update
        await langchain_cache.update_async(
            messages, "test-llm", [response], {"user_id": "user1"}
        )

        # Test async lookup
        result = await langchain_cache.lookup_async(
            messages, "test-llm", {"user_id": "user1"}
        )
        assert result is not None
        assert "I'm doing well" in str(result)

    @pytest.mark.asyncio
    async def test_user_isolation_in_langchain_cache(self):
        """Test that LangChain cache respects user isolation."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )
        langchain_cache = EnhancedLangChainCache(cache_service=cache_service)

        messages = [HumanMessage(content="What's the weather?")]
        response = AIMessage(content="It's sunny today!")

        # Cache for user1
        await langchain_cache.update_async(
            messages, "test-llm", [response], {"user_id": "user1"}
        )

        # Should find for user1
        result1 = await langchain_cache.lookup_async(
            messages, "test-llm", {"user_id": "user1"}
        )
        assert result1 is not None

        # Should not find for user2
        result2 = await langchain_cache.lookup_async(
            messages, "test-llm", {"user_id": "user2"}
        )
        assert result2 is None

    def test_sync_wrapper_compatibility(self):
        """Test that sync methods still work for backward compatibility."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )
        langchain_cache = EnhancedLangChainCache(cache_service=cache_service)

        messages = [HumanMessage(content="Test message")]
        response = AIMessage(content="Test response")

        # Test sync update
        langchain_cache.update(messages, "test-llm", [response], {"user_id": "user1"})

        # Test sync lookup
        result = langchain_cache.lookup(messages, "test-llm", {"user_id": "user1"})
        assert result is not None

    def test_factory_function(self):
        """Test the factory function for creating cache instances."""
        cache = create_enhanced_langchain_cache(
            similarity_threshold=0.7, similarity_enabled=True, cache_tool_calls=False
        )

        assert cache.similarity_threshold == 0.7
        assert cache.similarity_enabled is True
        assert cache.cache_tool_calls is False

    @pytest.mark.asyncio
    async def test_async_stats(self):
        """Test async stats retrieval."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )
        langchain_cache = EnhancedLangChainCache(cache_service=cache_service)

        # Add some data
        messages = [HumanMessage(content="Test")]
        response = AIMessage(content="Response")
        await langchain_cache.update_async(
            messages, "test-llm", [response], {"user_id": "user1"}
        )

        # Get async stats
        stats = await langchain_cache.get_stats_async()
        assert "total_entries" in stats
        assert "similarity_enabled" in stats
        assert "cache_tool_calls" in stats

    @pytest.mark.asyncio
    async def test_async_clear(self):
        """Test async clear operations."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )
        langchain_cache = EnhancedLangChainCache(cache_service=cache_service)

        # Add data
        messages = [HumanMessage(content="Test")]
        response = AIMessage(content="Response")
        await langchain_cache.update_async(
            messages, "test-llm", [response], {"user_id": "user1"}
        )

        # Verify data exists
        result = await langchain_cache.lookup_async(
            messages, "test-llm", {"user_id": "user1"}
        )
        assert result is not None

        # Clear all
        await langchain_cache.clear_async()

        # Verify data is gone
        result = await langchain_cache.lookup_async(
            messages, "test-llm", {"user_id": "user1"}
        )
        assert result is None
