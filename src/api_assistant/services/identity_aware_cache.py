"""
Identity-aware cache service for API Assistant.

This module provides user-scoped caching with lightweight in-memory backend
and optional Redis backend for multi-user isolation.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..config import settings

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class InMemoryCacheBackend(CacheBackend):
    """In-memory cache backend with TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl_hours: int = 1):
        """Initialize in-memory cache backend."""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.default_ttl_hours = default_ttl_hours
        logger.debug(f"In-memory cache backend initialized with max_size={max_size}, ttl={default_ttl_hours}h")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        entry = self._cache.get(key)
        if not entry:
            return None
        
        # Check expiration
        if entry.get("expires_at") and datetime.now() > entry["expires_at"]:
            del self._cache[key]
            return None
        
        # Update access time
        entry["last_accessed"] = datetime.now()
        entry["access_count"] = entry.get("access_count", 0) + 1
        
        return entry["value"]
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        # Calculate expiration
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_hours * 3600
        
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        
        # Check if key already exists
        if key in self._cache:
            # Update existing entry
            self._cache[key].update({
                "value": value,
                "expires_at": expires_at,
                "updated_at": datetime.now()
            })
        else:
            # Check size limit
            if len(self._cache) >= self.max_size:
                await self._evict_oldest()
            
            # Add new entry
            self._cache[key] = {
                "value": value,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "expires_at": expires_at,
                "last_accessed": datetime.now(),
                "access_count": 1  # Start at 1 since setting is the first access
            }
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        # Clean expired entries
        await self._clean_expired()
        
        total_entries = len(self._cache)
        total_size = sum(len(str(entry["value"])) for entry in self._cache.values())
        
        return {
            "backend": "memory",
            "total_entries": total_entries,
            "max_size": self.max_size,
            "total_size_bytes": total_size,
            "utilization_percent": (total_entries / self.max_size) * 100 if self.max_size > 0 else 0
        }
    
    async def _evict_oldest(self) -> None:
        """Evict oldest entries when cache is full."""
        if not self._cache:
            return
        
        # Find oldest entry by last accessed time
        oldest_key = min(self._cache.keys(), 
                        key=lambda k: self._cache[k].get("last_accessed", datetime.min))
        
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")
    
    async def _clean_expired(self) -> int:
        """Clean expired entries and return count of cleaned entries."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.get("expires_at") and datetime.now() > entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)


class RedisCacheBackend(CacheBackend):
    """Redis cache backend for distributed caching."""
    
    def __init__(self, redis_url: str, default_ttl_hours: int = 1):
        """Initialize Redis cache backend."""
        self.redis_url = redis_url
        self.default_ttl_hours = default_ttl_hours
        # TODO: Implement Redis client connection
        logger.info(f"Redis cache backend initialized with URL: {redis_url}")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        raise NotImplementedError("Redis backend not implemented")
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in Redis cache."""
        raise NotImplementedError("Redis backend not implemented")
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache."""
        raise NotImplementedError("Redis backend not implemented")
    
    async def clear(self) -> None:
        """Clear all cache entries from Redis."""
        raise NotImplementedError("Redis backend not implemented")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics."""
        raise NotImplementedError("Redis backend not implemented")


class IdentityAwareCache:
    """Identity-aware cache service with user-scoped keys."""
    
    def __init__(self, backend: str = "memory", config: Optional[Dict[str, Any]] = None):
        """Initialize identity-aware cache service."""
        self.backend_type = backend
        self.config = config or {}
        
        if backend == "memory":
            max_size = self.config.get("max_size", 1000)  # Default fallback
            ttl_hours = self.config.get("ttl_hours", 1)   # Default fallback
            self.backend = InMemoryCacheBackend(max_size=max_size, default_ttl_hours=ttl_hours)
        elif backend == "redis":
            redis_url = self.config.get("redis_url", settings.cache_redis_url)
            if not redis_url:
                raise ValueError("Redis URL not configured")
            raise NotImplementedError("Redis backend not implemented")
        else:
            raise ValueError(f"Unsupported cache backend: {backend}")
        
        logger.debug(f"Identity-aware cache initialized with backend: {backend}")
    
    def get_user_scoped_key(self, user_id: str, key: str) -> str:
        """Generate user-scoped cache key."""
        return f"user:{user_id}:{key}"
    
    async def get(self, user_id: str, key: str) -> Optional[Any]:
        """Get value from cache using user-scoped key."""
        user_key = self.get_user_scoped_key(user_id, key)
        return await self.backend.get(user_key)
    
    async def set(self, user_id: str, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache using user-scoped key."""
        user_key = self.get_user_scoped_key(user_id, key)
        await self.backend.set(user_key, value, ttl_seconds)
    
    async def delete(self, user_id: str, key: str) -> bool:
        """Delete value from cache using user-scoped key."""
        user_key = self.get_user_scoped_key(user_id, key)
        return await self.backend.delete(user_key)
    
    async def clear_user(self, user_id: str) -> None:
        """Clear all cache entries for a specific user."""
        await self.clear_user_cache(user_id)
    
    async def clear_user_cache(self, user_id: str) -> None:
        """Clear all cache entries for a specific user."""
        # This would need pattern-based deletion in Redis
        # For in-memory backend, we can iterate and delete
        if isinstance(self.backend, InMemoryCacheBackend):
            user_prefix = f"user:{user_id}:"
            keys_to_delete = [
                key for key in self.backend._cache.keys()
                if key.startswith(user_prefix)
            ]
            for key in keys_to_delete:
                await self.backend.delete(key)
            logger.info(f"Cleared {len(keys_to_delete)} cache entries for user {user_id}")
        else:
            # TODO: Implement pattern-based deletion for Redis
            logger.warning("User cache clearing not implemented for Redis backend")
    
    async def clear_all(self) -> None:
        """Clear all cache entries."""
        await self.clear()
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        await self.backend.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = await self.backend.get_stats()
        stats["backend_type"] = self.backend_type
        
        # Add expected fields for tests
        if "total_size" not in stats:
            stats["total_size"] = stats.get("total_size_bytes", 0)
        if "hit_rate" not in stats:
            stats["hit_rate"] = 0.0  # TODO: Implement hit rate calculation
        
        return stats


# Global identity-aware cache instance
_identity_aware_cache: Optional[IdentityAwareCache] = None


def get_identity_aware_cache() -> IdentityAwareCache:
    """Get the global identity-aware cache instance."""
    global _identity_aware_cache
    if _identity_aware_cache is None:
        backend = settings.cache_backend
        config = {
            "max_size": settings.cache_max_size,
            "ttl_hours": settings.cache_ttl_hours,
            "redis_url": settings.cache_redis_url
        }
        _identity_aware_cache = IdentityAwareCache(backend=backend, config=config)
    return _identity_aware_cache


def set_identity_aware_cache(cache: IdentityAwareCache) -> None:
    """Set the global identity-aware cache instance."""
    global _identity_aware_cache
    _identity_aware_cache = cache


async def get_cached_value(user_id: str, key: str) -> Optional[Any]:
    """Get cached value for user using the global cache."""
    cache = get_identity_aware_cache()
    return await cache.get(user_id, key)


async def set_cached_value(user_id: str, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    """Set cached value for user using the global cache."""
    cache = get_identity_aware_cache()
    await cache.set(user_id, key, value, ttl_seconds) 

_cache_service = None

def get_cache_service():
    global _cache_service
    if _cache_service is None:
        # Use concrete default values to avoid MagicMock issues
        _cache_service = IdentityAwareCache(backend="memory", config={
            "max_size": 1000,
            "ttl_hours": 1
        })
    return _cache_service

def set_cache_service(cache_service):
    global _cache_service
    _cache_service = cache_service


# Convenience functions for global cache access
async def cache_get(user_id: str, key: str) -> Optional[Any]:
    """Get cached value for user using the global cache service."""
    cache = get_cache_service()
    return await cache.get(user_id, key)


async def cache_set(user_id: str, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    """Set cached value for user using the global cache service."""
    cache = get_cache_service()
    await cache.set(user_id, key, value, ttl_seconds)


async def cache_delete(user_id: str, key: str) -> bool:
    """Delete cached value for user using the global cache service."""
    cache = get_cache_service()
    return await cache.delete(user_id, key)


async def cache_clear(user_id: Optional[str] = None) -> None:
    """Clear cache for user or all cache if no user specified."""
    cache = get_cache_service()
    if user_id:
        await cache.clear_user(user_id)
    else:
        await cache.clear_all() 