"""
Cache service for API Assistant.

This module provides intelligent caching for API assistant requests,
including token-based similarity search to reduce LLM calls for common requests.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached response entry."""

    response: str
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime = None
    expires_at: datetime = None
    hit_count: int = 0
    canonical_intent: str = ""  # Store the canonical intent for similarity matching
    original_message: str = (
        ""  # Store the original message content for similarity matching
    )

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.expires_at is None:
            # Default cache TTL: 1 hour
            self.expires_at = self.created_at + timedelta(hours=1)

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response": self.response,
            "tool_calls": self.tool_calls,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "hit_count": self.hit_count,
            "canonical_intent": self.canonical_intent,
            "original_message": self.original_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            response=data["response"],
            tool_calls=data.get("tool_calls"),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            hit_count=data.get("hit_count", 0),
            canonical_intent=data.get("canonical_intent", ""),
            original_message=data.get("original_message", ""),
        )


class TokenSimilarityMatcher:
    """Fast token-based similarity matching for canonical intents."""

    def __init__(self):
        """Initialize the token similarity matcher."""
        # Token weights for different word types
        self.token_weights = {
            "verb": 2.0,  # create, list, get, delete, add, show
            "noun": 1.5,  # product, user, order, data
            "article": 0.5,  # a, an, the
            "other": 1.0,  # everything else
        }

        # Common verbs and nouns for classification
        self.verbs = {
            "create",
            "add",
            "make",
            "generate",
            "build",
            "new",
            "list",
            "get",
            "show",
            "display",
            "find",
            "search",
            "update",
            "modify",
            "edit",
            "change",
            "delete",
            "remove",
            "destroy",
            "drop",
            "enable",
            "disable",
            "activate",
            "deactivate",
        }

        self.nouns = {
            "product",
            "user",
            "order",
            "item",
            "data",
            "info",
            "list",
            "details",
            "schema",
            "structure",
            "config",
            "settings",
            "profile",
            "account",
            "system",
        }

    def similarity(self, intent1: str, intent2: str) -> float:
        """
        Calculate token-based similarity between two canonical intents.

        Args:
            intent1: First canonical intent
            intent2: Second canonical intent

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not intent1 or not intent2:
            return 0.0

        # Check for false positives (semantic opposites)
        if self._is_likely_false_positive(intent1, intent2):
            return 0.0

        # Get weighted token sets
        tokens1 = self._tokenize_and_weight(intent1)
        tokens2 = self._tokenize_and_weight(intent2)

        return self._weighted_jaccard_similarity(tokens1, tokens2)

    def _tokenize_and_weight(self, intent: str) -> dict[str, float]:
        """Tokenize intent and assign weights to tokens."""
        words = intent.lower().split()
        weighted_tokens = {}

        for word in words:
            weight = self._get_token_weight(word)
            weighted_tokens[word] = weight

        return weighted_tokens

    def _get_token_weight(self, word: str) -> float:
        """Get weight for a token based on its type."""
        if word in self.verbs:
            return self.token_weights["verb"]
        elif word in self.nouns:
            return self.token_weights["noun"]
        elif word in {"a", "an", "the"}:
            return self.token_weights["article"]
        else:
            return self.token_weights["other"]

    def _weighted_jaccard_similarity(
        self, tokens1: dict[str, float], tokens2: dict[str, float]
    ) -> float:
        """Calculate weighted Jaccard similarity between token sets."""
        if not tokens1 or not tokens2:
            return 0.0

        # Calculate weighted intersection and union
        intersection_weight = 0.0
        union_weight = 0.0

        all_tokens = set(tokens1.keys()) | set(tokens2.keys())

        for token in all_tokens:
            weight1 = tokens1.get(token, 0.0)
            weight2 = tokens2.get(token, 0.0)

            intersection_weight += min(weight1, weight2)
            union_weight += max(weight1, weight2)

        return intersection_weight / union_weight if union_weight > 0 else 0.0

    def _is_likely_false_positive(self, intent1: str, intent2: str) -> bool:
        """Check if two intents are likely semantic opposites."""
        opposites = [
            ("create", "delete"),
            ("add", "remove"),
            ("get", "delete"),
            ("list", "delete"),
            ("show", "hide"),
            ("enable", "disable"),
            ("activate", "deactivate"),
            ("new", "delete"),
            ("make", "destroy"),
        ]

        words1 = set(intent1.lower().split())
        words2 = set(intent2.lower().split())

        for opp1, opp2 in opposites:
            if (opp1 in words1 and opp2 in words2) or (
                opp2 in words1 and opp1 in words2
            ):
                return True

        return False


class CacheService:
    """Manages caching for API assistant requests with token-based similarity search."""

    def __init__(self, max_size: int = 1000, default_ttl_hours: int = 1):
        """
        Initialize the cache service.

        Args:
            max_size: Maximum number of cache entries
            default_ttl_hours: Default time-to-live for cache entries in hours
        """
        self._cache: dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl_hours = default_ttl_hours
        self.similarity_matcher = TokenSimilarityMatcher()

        logger.debug(
            f"Cache service initialized with max_size={max_size}, ttl={default_ttl_hours}h"
        )

    def get(
        self, messages: list[BaseMessage]
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """
        Get a cached response for the given messages.

        Args:
            messages: List of conversation messages

        Returns:
            Tuple of (response, tool_calls) if found and not expired, None otherwise
        """
        message_key = self._extract_message_key(messages)

        if not message_key:
            logger.debug("No message key available")
            return None

        entry = self._cache.get(message_key)

        if entry is None:
            logger.debug(f"Cache miss for messages: {message_key[:8]}...")
            return None

        if entry.is_expired():
            logger.debug(f"Cache entry expired for messages: {message_key[:8]}...")
            del self._cache[message_key]
            return None

        # Increment hit count
        entry.hit_count += 1
        logger.info(
            f"Cache hit for messages: {message_key[:8]}... (hits: {entry.hit_count})"
        )

        return entry.response, entry.tool_calls

    def find_similar_cached_responses(
        self, message_content: str, similarity_threshold: float = 0.8
    ) -> list[tuple[str, str, list[dict[str, Any]], float]]:
        """
        Find similar cached responses using token-based similarity.

        Args:
            message_content: The message content to find matches for
            similarity_threshold: Minimum similarity score

        Returns:
            List of (message_content, response, tool_calls, similarity_score) tuples, sorted by similarity
        """
        if not message_content:
            return []

        # Find similar contents using token-based similarity
        similar_contents = []

        for _message_key, entry in self._cache.items():
            if not entry.is_expired() and entry.original_message:
                # Calculate similarity between current message and cached message
                similarity = self.similarity_matcher.similarity(
                    message_content, entry.original_message
                )

                if similarity >= similarity_threshold:
                    similar_contents.append(
                        (
                            entry.original_message,
                            entry.response,
                            entry.tool_calls or [],
                            similarity,
                        )
                    )

        # Sort by similarity score (highest first)
        similar_contents.sort(key=lambda x: x[3], reverse=True)

        return similar_contents

    def set(
        self,
        messages: list[BaseMessage],
        response: str,
        tool_calls: list[dict[str, Any]] | None = None,
        ttl_hours: int | None = None,
    ) -> None:
        """
        Cache a response for the given messages.

        Args:
            messages: List of conversation messages
            response: The AI response to cache
            tool_calls: Optional tool calls from the response
            ttl_hours: Optional custom TTL in hours
        """
        message_key = self._extract_message_key(messages)

        if not message_key:
            logger.debug("Could not extract message key, skipping cache")
            return

        # Extract original message content for similarity matching
        original_message = ""
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content") and last_message.content:
                original_message = str(last_message.content)

        # Create cache entry
        entry = CacheEntry(
            response=response,
            tool_calls=tool_calls,
            canonical_intent="",  # No longer used
            original_message=original_message,
            expires_at=datetime.now()
            + timedelta(hours=ttl_hours or self.default_ttl_hours),
        )

        # Check cache size and evict if necessary
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        self._cache[message_key] = entry
        logger.debug(f"Cached response for messages: {message_key[:8]}...")

    def _extract_message_key(self, messages: list[BaseMessage]) -> str:
        """Extract a cache key from message content."""
        if not messages:
            return ""

        # Create a string representation of all message contents
        message_contents = []
        for message in messages:
            if hasattr(message, "content") and message.content:
                message_contents.append(str(message.content))

        if not message_contents:
            return ""

        # Join all message contents and hash for consistent cache keys
        combined_content = "|".join(message_contents)
        return hashlib.sha256(combined_content.encode()).hexdigest()

    def _extract_intent_key(self, canonical_intent: str) -> str:
        """Extract a cache key from canonical intent (kept for compatibility)."""
        if not canonical_intent:
            return ""

        # Hash the canonical intent for consistent cache keys
        return hashlib.sha256(canonical_intent.encode()).hexdigest()

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key[:8]}...")

    def clear_expired(self) -> int:
        """Clear expired cache entries and return count of cleared entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())
        total_hits = sum(entry.hit_count for entry in self._cache.values())

        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "total_hits": total_hits,
            "max_size": self.max_size,
        }

    def clear(self) -> None:
        """Clear all cache entries."""
        cleared_count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared all {cleared_count} cache entries")


# Global cache instance
_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    global _cache_service
    if _cache_service is None:
        from ..config import settings

        _cache_service = CacheService(
            max_size=settings.cache_max_size, default_ttl_hours=settings.cache_ttl_hours
        )
    return _cache_service


def set_cache_service(cache_service: CacheService) -> None:
    """Set the global cache service instance."""
    global _cache_service
    _cache_service = cache_service
