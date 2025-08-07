"""
Unit tests for identity-aware cache service.

Tests cover user-scoped cache keys, different backends, and cache
isolation between users with proper TTL and size management.
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.services.identity_aware_cache import (
    CacheBackend,
    IdentityAwareCache,
    InMemoryCacheBackend,
    RedisCacheBackend,
    cache_clear,
    cache_delete,
    cache_get,
    cache_set,
    get_cache_service,
    set_cache_service,
)


class TestCacheBackend:
    """Test cases for cache backend."""

    def test_backend_abstract_methods(self):
        """Test that CacheBackend is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            CacheBackend()


class TestInMemoryCacheBackend:
    """Test cases for in-memory cache backend."""

    @pytest.fixture
    def backend(self):
        """Create in-memory backend instance."""
        return InMemoryCacheBackend(max_size=100, default_ttl_hours=1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "key,value",
        [
            ("test-key", {"data": "test-value", "timestamp": datetime.utcnow()}),
            ("another-key", "simple-value"),
        ],
    )
    async def test_set_and_get(self, backend, key, value):
        """Test setting and getting cache entries."""
        await backend.set(key, value)
        result = await backend.get(key)
        assert result == value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "key",
        [
            "nonexistent-key",
            "missing-key",
        ],
    )
    async def test_get_nonexistent(self, backend, key):
        """Test getting nonexistent cache entry."""
        result = await backend.get(key)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "key,value",
        [
            ("test-key", {"data": "test-value"}),
            ("another-key", "simple-value"),
        ],
    )
    async def test_delete(self, backend, key, value):
        """Test deleting cache entry."""
        await backend.set(key, value)
        result = await backend.get(key)
        assert result == value
        await backend.delete(key)
        result = await backend.get(key)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "key",
        [
            "nonexistent-key",
            "missing-key",
        ],
    )
    async def test_delete_nonexistent(self, backend, key):
        """Test deleting nonexistent cache entry."""
        await backend.delete(key)  # Should not raise error

    @pytest.mark.asyncio
    async def test_clear(self, backend):
        """Test clearing all cache entries."""
        await backend.set("key1", "value1")
        await backend.set("key2", "value2")
        await backend.set("key3", "value3")
        assert await backend.get("key1") == "value1"
        assert await backend.get("key2") == "value2"
        assert await backend.get("key3") == "value3"
        await backend.clear()
        assert await backend.get("key1") is None
        assert await backend.get("key2") is None
        assert await backend.get("key3") is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, backend):
        """Test TTL expiration."""
        key = "test-key"
        value = {"data": "test-value"}
        await backend.set(key, value)
        result = await backend.get(key)
        assert result == value
        entry = backend._cache[key]
        entry["expires_at"] = datetime.now() - timedelta(seconds=1)
        result = await backend.get(key)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "max_size,keys,evicted_key",
        [
            (3, ["key1", "key2", "key3", "key4"], "key1"),
            (2, ["a", "b", "c"], "a"),
        ],
    )
    async def test_max_size_limit(self, max_size, keys, evicted_key):
        """Test max size limit enforcement."""
        small_backend = InMemoryCacheBackend(max_size=max_size, default_ttl_hours=1)
        for k in keys:
            await small_backend.set(k, k)
        assert await small_backend.get(evicted_key) is None
        for k in keys[1:]:
            assert await small_backend.get(k) == k

    @pytest.mark.asyncio
    async def test_lru_eviction(self, backend):
        """Test LRU eviction policy."""
        small_backend = InMemoryCacheBackend(max_size=2, default_ttl_hours=1)
        await small_backend.set("key1", "value1")
        await small_backend.set("key2", "value2")
        await small_backend.get("key1")
        await small_backend.set("key3", "value3")
        assert await small_backend.get("key1") == "value1"
        assert await small_backend.get("key2") is None
        assert await small_backend.get("key3") == "value3"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "key,value",
        [
            ("test-key", {"data": "test-value"}),
            ("another-key", "simple-value"),
        ],
    )
    async def test_cache_entry_properties(self, backend, key, value):
        """Test cache entry properties with dict-based implementation."""
        await backend.set(key, value)
        entry = backend._cache[key]
        assert entry["value"] == value
        assert entry["created_at"] is not None
        assert entry["last_accessed"] is not None
        assert entry["access_count"] == 1
        await backend.get(key)
        assert entry["access_count"] == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "key,value,expired_hours",
        [
            ("test-key", {"data": "test-value"}, 2),
            ("another-key", "simple-value", 3),
        ],
    )
    async def test_cache_entry_ttl(self, backend, key, value, expired_hours):
        """Test cache entry TTL calculation with dict-based implementation."""
        await backend.set(key, value)
        entry = backend._cache[key]
        assert entry["expires_at"] > entry["created_at"]
        entry["created_at"] = datetime.utcnow() - timedelta(hours=expired_hours)
        entry["expires_at"] = entry["created_at"] + timedelta(hours=1)
        result = await backend.get(key)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "key,value",
        [
            ("test-key", {"data": "test-value"}),
            ("another-key", "simple-value"),
        ],
    )
    async def test_cache_entry_string_representation(self, backend, key, value):
        """Test cache entry string representation with dict-based implementation."""
        await backend.set(key, value)
        entry = backend._cache[key]
        entry_str = str(entry)
        assert str(value).split()[0] in entry_str
        assert "created_at" in entry_str


class TestRedisCacheBackend:
    """Test cases for Redis cache backend."""

    @pytest.fixture
    def backend(self):
        """Create Redis backend instance."""
        return RedisCacheBackend("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_redis_backend_not_implemented(self, backend):
        """Test that Redis backend raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await backend.set("key", "value")

        with pytest.raises(NotImplementedError):
            await backend.get("key")

        with pytest.raises(NotImplementedError):
            await backend.delete("key")

        with pytest.raises(NotImplementedError):
            await backend.clear()


class TestIdentityAwareCache:
    """Test cases for identity-aware cache service."""

    @pytest.fixture
    def cache_service(self):
        """Create identity-aware cache instance."""
        return IdentityAwareCache(backend="memory")

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_service):
        """Test setting and getting cache entries with user scoping."""
        user_id = "user-123"
        key = "test-key"
        value = {"data": "test-value"}

        # Set value for user
        await cache_service.set(user_id, key, value)

        # Get value for user
        result = await cache_service.get(user_id, key)

        assert result == value

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache_service):
        """Test getting nonexistent cache entry."""
        user_id = "user-123"
        key = "nonexistent-key"

        result = await cache_service.get(user_id, key)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache_service):
        """Test deleting cache entry."""
        user_id = "user-123"
        key = "test-key"
        value = {"data": "test-value"}

        # Set value
        await cache_service.set(user_id, key, value)

        # Verify it exists
        result = await cache_service.get(user_id, key)
        assert result == value

        # Delete value
        await cache_service.delete(user_id, key)

        # Verify it's gone
        result = await cache_service.get(user_id, key)
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_user_cache(self, cache_service):
        """Test clearing cache for specific user."""
        user1_id = "user-123"
        user2_id = "user-789"

        # Set values for both users
        await cache_service.set(user1_id, "key1", "value1")
        await cache_service.set(user1_id, "key2", "value2")
        await cache_service.set(user2_id, "key3", "value3")

        # Verify they exist
        assert await cache_service.get(user1_id, "key1") == "value1"
        assert await cache_service.get(user1_id, "key2") == "value2"
        assert await cache_service.get(user2_id, "key3") == "value3"

        # Clear cache for user1 only
        await cache_service.clear_user(user1_id)

        # Verify user1's cache is cleared, user2's remains
        assert await cache_service.get(user1_id, "key1") is None
        assert await cache_service.get(user1_id, "key2") is None
        assert await cache_service.get(user2_id, "key3") == "value3"

    @pytest.mark.asyncio
    async def test_clear_all(self, cache_service):
        """Test clearing all cache entries."""
        user1_id = "user-123"
        user2_id = "user-789"

        # Set values for both users
        await cache_service.set(user1_id, "key1", "value1")
        await cache_service.set(user2_id, "key2", "value2")

        # Verify they exist
        assert await cache_service.get(user1_id, "key1") == "value1"
        assert await cache_service.get(user2_id, "key2") == "value2"

        # Clear all cache
        await cache_service.clear_all()

        # Verify all are gone
        assert await cache_service.get(user1_id, "key1") is None
        assert await cache_service.get(user2_id, "key2") is None

    @pytest.mark.asyncio
    async def test_user_isolation(self, cache_service):
        """Test that cache entries are isolated between users."""
        user1_id = "user-123"
        user2_id = "user-789"
        key = "shared-key"

        # Set different values for same key for different users
        await cache_service.set(user1_id, key, "value1")
        await cache_service.set(user2_id, key, "value2")

        # Verify isolation
        assert await cache_service.get(user1_id, key) == "value1"
        assert await cache_service.get(user2_id, key) == "value2"

    @pytest.mark.asyncio
    async def test_get_user_scoped_key(self, cache_service):
        """Test user-scoped key generation."""
        user_id = "user-123"
        key = "test-key"

        scoped_key = cache_service.get_user_scoped_key(user_id, key)

        assert scoped_key == f"user:{user_id}:{key}"

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_service):
        """Test getting cache statistics."""
        user_id = "user-123"

        # Set some values
        await cache_service.set(user_id, "key1", "value1")
        await cache_service.set(user_id, "key2", "value2")

        # Get stats
        stats = await cache_service.get_stats()

        assert "total_entries" in stats
        assert "total_size" in stats
        assert "hit_rate" in stats
        assert stats["total_entries"] >= 2

    def test_unsupported_backend(self):
        """Test initialization with unsupported backend."""
        with pytest.raises(ValueError, match="Unsupported cache backend"):
            IdentityAwareCache(backend="unsupported")

    def test_redis_backend_not_implemented(self):
        """Test that Redis backend raises NotImplementedError."""
        with patch("nalai.services.identity_aware_cache.settings") as mock_settings:
            mock_settings.cache_redis_url = "redis://localhost:6379"

            with pytest.raises(NotImplementedError):
                IdentityAwareCache(backend="redis")


class TestIdentityAwareCacheGlobal:
    """Test cases for global identity-aware cache functions."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("nalai.services.identity_aware_cache.settings") as mock_settings:
            mock_settings.cache_backend = "memory"
            yield mock_settings

    def test_get_cache_service_singleton(self, mock_settings):
        """Test get_cache_service returns singleton instance."""
        # Clear any existing instance
        set_cache_service(None)

        service1 = get_cache_service()
        service2 = get_cache_service()

        assert service1 is service2
        assert isinstance(service1, IdentityAwareCache)

    def test_set_cache_service(self, mock_settings):
        """Test set_cache_service."""
        custom_service = IdentityAwareCache(backend="memory")
        set_cache_service(custom_service)

        service = get_cache_service()
        assert service is custom_service

    @pytest.mark.asyncio
    async def test_cache_get_global(self, mock_settings):
        """Test cache_get global function."""
        user_id = "user-123"
        key = "test-key"
        value = {"data": "test-value"}

        # Set value
        cache_service = get_cache_service()
        await cache_service.set(user_id, key, value)

        # Get value using global function
        result = await cache_get(user_id, key)

        assert result == value

    @pytest.mark.asyncio
    async def test_cache_set_global(self, mock_settings):
        """Test cache_set global function."""
        user_id = "user-123"
        key = "test-key"
        value = {"data": "test-value"}

        # Set value using global function
        await cache_set(user_id, key, value)

        # Verify value was set
        cache_service = get_cache_service()
        result = await cache_service.get(user_id, key)

        assert result == value

    @pytest.mark.asyncio
    async def test_cache_delete_global(self, mock_settings):
        """Test cache_delete global function."""
        user_id = "user-123"
        key = "test-key"
        value = {"data": "test-value"}

        # Set value
        cache_service = get_cache_service()
        await cache_service.set(user_id, key, value)

        # Delete value using global function
        await cache_delete(user_id, key)

        # Verify value was deleted
        result = await cache_service.get(user_id, key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear_global(self, mock_settings):
        """Test cache_clear global function."""
        user_id = "user-123"

        # Set values
        cache_service = get_cache_service()
        await cache_service.set(user_id, "key1", "value1")
        await cache_service.set(user_id, "key2", "value2")

        # Clear cache using global function
        await cache_clear(user_id)

        # Verify cache was cleared
        assert await cache_service.get(user_id, "key1") is None
        assert await cache_service.get(user_id, "key2") is None


class TestIdentityAwareCacheIntegration:
    """Integration tests for identity-aware cache service."""

    @pytest.mark.asyncio
    async def test_cache_isolation_completeness(self):
        """Test that cache provides complete isolation between users."""
        cache_service = IdentityAwareCache(backend="memory")

        user1_id = "user-123"
        user2_id = "user-789"

        # Test with various data types
        test_data = [
            ("string", "simple string"),
            ("number", 42),
            ("boolean", True),
            ("list", [1, 2, 3]),
            ("dict", {"key": "value"}),
            ("complex", {"nested": {"data": [1, 2, 3]}}),
        ]

        for key, value in test_data:
            # Set same key with different values for different users
            await cache_service.set(user1_id, key, value)
            await cache_service.set(user2_id, key, f"user2_{value}")

            # Verify isolation
            user1_result = await cache_service.get(user1_id, key)
            user2_result = await cache_service.get(user2_id, key)

            assert user1_result == value
            assert user2_result == f"user2_{value}"
            assert user1_result != user2_result

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Test cache performance with many entries."""
        cache_service = IdentityAwareCache(backend="memory")

        user_id = "user-123"

        # Set many entries
        start_time = datetime.utcnow()
        for i in range(1000):
            await cache_service.set(user_id, f"key_{i}", f"value_{i}")
        set_time = datetime.utcnow()

        # Get many entries
        for i in range(1000):
            result = await cache_service.get(user_id, f"key_{i}")
            assert result == f"value_{i}"
        get_time = datetime.utcnow()

        # Verify performance is reasonable
        set_duration = (set_time - start_time).total_seconds()
        get_duration = (get_time - set_time).total_seconds()

        assert set_duration < 1.0  # Less than 1 second for 1000 sets
        assert get_duration < 1.0  # Less than 1 second for 1000 gets

    @pytest.mark.asyncio
    async def test_cache_ttl_behavior(self):
        """Test cache TTL behavior across users."""
        # Create cache with short TTL
        cache_service = IdentityAwareCache(backend="memory")
        cache_service.backend.default_ttl_hours = 0.001  # ~3.6 seconds

        user1_id = "user-123"
        user2_id = "user-789"

        # Set values for both users
        await cache_service.set(user1_id, "key1", "value1")
        await cache_service.set(user2_id, "key2", "value2")

        # Verify they exist immediately
        assert await cache_service.get(user1_id, "key1") == "value1"
        assert await cache_service.get(user2_id, "key2") == "value2"

        # Manually set expiration to past time
        user1_key = cache_service.get_user_scoped_key(user1_id, "key1")
        user2_key = cache_service.get_user_scoped_key(user2_id, "key2")
        cache_service.backend._cache[user1_key]["expires_at"] = (
            datetime.now() - timedelta(seconds=1)
        )
        cache_service.backend._cache[user2_key]["expires_at"] = (
            datetime.now() - timedelta(seconds=1)
        )

        # Verify both are expired
        assert await cache_service.get(user1_id, "key1") is None
        assert await cache_service.get(user2_id, "key2") is None

    @pytest.mark.asyncio
    async def test_cache_size_management(self):
        """Test cache size management with user isolation."""
        # Create cache with small size limit
        cache_service = IdentityAwareCache(backend="memory")
        cache_service.backend.max_size = 4  # Small limit

        user1_id = "user-123"
        user2_id = "user-789"

        # Fill cache with user1's data
        await cache_service.set(user1_id, "key1", "value1")
        await cache_service.set(user1_id, "key2", "value2")
        await cache_service.set(user1_id, "key3", "value3")
        await cache_service.set(user1_id, "key4", "value4")

        # Add user2's data (should evict user1's data)
        await cache_service.set(user2_id, "key5", "value5")

        # Verify user1's data was evicted
        assert await cache_service.get(user1_id, "key1") is None
        assert await cache_service.get(user2_id, "key5") == "value5"

    @pytest.mark.asyncio
    async def test_cache_key_collision_prevention(self):
        """Test that user-scoped keys prevent collisions."""
        cache_service = IdentityAwareCache(backend="memory")

        user1_id = "user-123"
        user2_id = "user-789"
        base_key = "shared-key"

        # Set different values for same base key
        await cache_service.set(user1_id, base_key, "user1-value")
        await cache_service.set(user2_id, base_key, "user2-value")

        # Verify no collision
        assert await cache_service.get(user1_id, base_key) == "user1-value"
        assert await cache_service.get(user2_id, base_key) == "user2-value"

        # Verify internal keys are different
        user1_scoped_key = cache_service.get_user_scoped_key(user1_id, base_key)
        user2_scoped_key = cache_service.get_user_scoped_key(user2_id, base_key)

        assert user1_scoped_key != user2_scoped_key
        assert user1_scoped_key == f"user:{user1_id}:{base_key}"
        assert user2_scoped_key == f"user:{user2_id}:{base_key}"


# Import asyncio for sleep function
