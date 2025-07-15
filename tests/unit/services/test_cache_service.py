"""
Unit tests for cache service.

Tests the caching functionality including token-based similarity search,
cache operations, and configuration.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from api_assistant.services.cache_service import (
    CacheEntry,
    CacheService,
    TokenSimilarityMatcher,
    get_cache_service,
    set_cache_service,
)


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            response="Test response",
            tool_calls=[{"name": "test_tool", "args": {}}],
            canonical_intent="create product",
        )

        assert entry.response == "Test response"
        assert entry.tool_calls == [{"name": "test_tool", "args": {}}]
        assert entry.canonical_intent == "create product"
        assert entry.hit_count == 0
        assert entry.created_at is not None
        assert entry.expires_at is not None

    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        # Create entry with past expiration
        past_time = datetime.now() - timedelta(hours=1)
        entry = CacheEntry(response="Test response", expires_at=past_time)

        assert entry.is_expired() is True

        # Create entry with future expiration
        future_time = datetime.now() + timedelta(hours=1)
        entry = CacheEntry(response="Test response", expires_at=future_time)

        assert entry.is_expired() is False

    def test_cache_entry_serialization(self):
        """Test cache entry serialization."""
        entry = CacheEntry(
            response="Test response",
            tool_calls=[{"name": "test_tool"}],
            canonical_intent="create product",
            hit_count=5,
        )

        data = entry.to_dict()
        restored_entry = CacheEntry.from_dict(data)

        assert restored_entry.response == entry.response
        assert restored_entry.tool_calls == entry.tool_calls
        assert restored_entry.canonical_intent == entry.canonical_intent
        assert restored_entry.hit_count == entry.hit_count


class TestTokenSimilarityMatcher:
    """Test TokenSimilarityMatcher functionality."""

    def test_similarity_basic(self):
        """Test basic similarity calculation."""
        matcher = TokenSimilarityMatcher()

        # Exact match
        similarity = matcher.similarity("create product", "create product")
        assert similarity == 1.0

        # Similar intents
        similarity = matcher.similarity("create product", "create a product")
        assert similarity > 0.8

        # Different intents
        similarity = matcher.similarity("create product", "list products")
        assert similarity < 0.5

    def test_similarity_with_articles(self):
        """Test similarity with articles."""
        matcher = TokenSimilarityMatcher()

        # Should be similar despite articles
        similarity1 = matcher.similarity("create product", "create a product")
        similarity2 = matcher.similarity("create product", "create the product")

        assert similarity1 > 0.8
        assert similarity2 > 0.8

    def test_false_positive_detection(self):
        """Test detection of semantic opposites."""
        matcher = TokenSimilarityMatcher()

        # Semantic opposites should return 0.0
        similarity = matcher.similarity("create product", "delete product")
        assert similarity == 0.0

        similarity = matcher.similarity("add user", "remove user")
        assert similarity == 0.0

    def test_token_weighting(self):
        """Test that verbs and nouns are weighted appropriately."""
        matcher = TokenSimilarityMatcher()

        # Verbs should be weighted higher
        similarity1 = matcher.similarity("create product", "create item")
        similarity2 = matcher.similarity("create product", "list product")

        # create + product should be more similar than create + list
        assert similarity1 > similarity2

    def test_edge_cases(self):
        """Test edge cases."""
        matcher = TokenSimilarityMatcher()

        # Empty strings
        similarity = matcher.similarity("", "create product")
        assert similarity == 0.0

        # Single word
        similarity = matcher.similarity("create", "create product")
        assert similarity > 0.0


class TestCacheService:
    """Test CacheService functionality."""

    def setup_method(self):
        """Set up test method."""
        self.cache_service = CacheService(max_size=10, default_ttl_hours=1)

    def test_cache_get_set(self):
        """Test basic cache get/set operations."""
        messages = [HumanMessage(content="Create a product")]
        response = "Product created successfully"
        tool_calls = [{"name": "create_product", "args": {}}]

        # Set cache entry
        self.cache_service.set(messages, response, tool_calls)

        # Get cache entry
        result = self.cache_service.get(messages)

        assert result is not None
        cached_response, cached_tool_calls = result
        assert cached_response == response
        assert cached_tool_calls == tool_calls

    def test_cache_miss(self):
        """Test cache miss scenario."""
        messages = [HumanMessage(content="Create a product")]

        result = self.cache_service.get(messages)
        assert result is None

    def test_cache_expiration(self):
        """Test cache expiration."""
        messages = [HumanMessage(content="Create a product")]
        response = "Product created successfully"

        # Create entry with immediate expiration
        with patch("api_assistant.services.cache_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.now()
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # Set entry with past expiration
            past_time = datetime.now() - timedelta(hours=1)
            entry = CacheEntry(response=response, expires_at=past_time)
            message_key = self.cache_service._extract_message_key(messages)
            self.cache_service._cache[message_key] = entry

            # Should return None for expired entry
            result = self.cache_service.get(messages)
            assert result is None

    def test_cache_size_limit(self):
        """Test cache size limiting."""
        # Fill cache to capacity
        for i in range(15):  # More than max_size (10)
            messages = [HumanMessage(content=f"Request {i}")]
            self.cache_service.set(messages, f"Response {i}")

        # Should not exceed max size
        assert len(self.cache_service._cache) <= 10

    def test_cache_hit_count(self):
        """Test cache hit counting."""
        messages = [HumanMessage(content="Create a product")]
        response = "Product created successfully"

        self.cache_service.set(messages, response)

        # Get multiple times
        for _ in range(3):
            self.cache_service.get(messages)

        # Check hit count
        message_key = self.cache_service._extract_message_key(messages)
        entry = self.cache_service._cache[message_key]
        assert entry.hit_count == 3

    def test_find_similar_cached_responses(self):
        """Test finding similar cached responses."""
        # Add some test entries with different message contents
        messages1 = [HumanMessage(content="Create a product")]
        messages2 = [HumanMessage(content="Create the product")]
        messages3 = [HumanMessage(content="List products")]

        self.cache_service.set(messages1, "Product created")
        self.cache_service.set(messages2, "Product created")
        self.cache_service.set(messages3, "Products listed")

        # Find similar responses for "create product"
        similar = self.cache_service.find_similar_cached_responses("create product")

        assert (
            len(similar) == 2
        )  # Should find "Create a product" and "Create the product"
        messages = [msg for msg, _, _, _ in similar]
        assert "Create a product" in messages
        assert "Create the product" in messages

        # Test with different phrasing
        similar = self.cache_service.find_similar_cached_responses("create a product")
        assert len(similar) >= 1  # Should find similar messages

    def test_clear_cache(self):
        """Test cache clearing."""
        messages = [HumanMessage(content="Create a product")]
        self.cache_service.set(messages, "Response")

        assert len(self.cache_service._cache) > 0

        self.cache_service.clear()
        assert len(self.cache_service._cache) == 0

    def test_get_stats(self):
        """Test cache statistics."""
        messages = [HumanMessage(content="Create a product")]
        self.cache_service.set(messages, "Response")

        # Get cache entry to create a hit
        self.cache_service.get(messages)

        stats = self.cache_service.get_stats()

        assert stats["total_entries"] == 1
        assert stats["total_hits"] == 1
        assert stats["max_size"] == 10


class TestGlobalCacheService:
    """Test global cache service functionality."""

    def setup_method(self):
        """Set up test method."""
        # Clear global cache
        set_cache_service(None)

    def test_get_cache_service_default(self):
        """Test getting default cache service."""
        cache_service = get_cache_service()

        assert cache_service is not None
        assert isinstance(cache_service, CacheService)

    def test_set_cache_service(self):
        """Test setting custom cache service."""
        custom_cache = CacheService(max_size=5, default_ttl_hours=2)
        set_cache_service(custom_cache)

        cache_service = get_cache_service()
        assert cache_service is custom_cache
        assert cache_service.max_size == 5
        assert cache_service.default_ttl_hours == 2
