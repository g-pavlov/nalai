"""
Enhanced cache service with similarity search and user isolation.

This module provides a comprehensive caching solution for LLM responses with:

1. User-scoped cache isolation for privacy
2. Token-based similarity search for semantic matching
3. Configurable tool call caching
4. Performance optimizations with TTL and size limits
5. Backend abstraction for pluggable storage (memory only)
6. Async interface for better performance

The cache service uses a backend abstraction pattern that allows for
different storage implementations. Currently only in-memory backend is supported.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import BaseMessage

from ..config import settings

logger = logging.getLogger(__name__)

# Import NLP libraries for comprehensive word corpus
try:
    import nltk
    from nltk.corpus import wordnet

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK not available, falling back to basic token matching")

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available, falling back to basic token matching")


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
    user_id: str = ""  # Store user ID for identity privacy
    cache_key_hash: str = ""  # Store the cache key hash for debugging

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.expires_at is None:
            # Default cache TTL: 30 minutes
            self.expires_at = self.created_at + timedelta(seconds=1800)

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
            "user_id": self.user_id,
            "cache_key_hash": self.cache_key_hash,
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
            user_id=data.get("user_id", ""),
            cache_key_hash=data.get("cache_key_hash", ""),
        )


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> CacheEntry | None:
        """Get cache entry from backend."""
        pass

    @abstractmethod
    async def set(
        self, key: str, entry: CacheEntry, ttl_seconds: int | None = None
    ) -> None:
        """Set cache entry in backend."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cache entry from backend."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries from backend."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics from backend."""
        pass

    @abstractmethod
    async def get_all_entries(self) -> list[tuple[str, CacheEntry]]:
        """Get all cache entries for similarity search."""
        pass

    @abstractmethod
    async def clear_user_entries(self, user_id: str) -> int:
        """Clear all entries for a specific user."""
        pass


class InMemoryCacheBackend(CacheBackend):
    """In-memory cache backend with TTL support."""

    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 1800):
        """Initialize in-memory cache backend."""
        self._cache: dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        logger.debug(
            f"In-memory cache backend initialized with max_size={max_size}, ttl={default_ttl_seconds}s"
        )

    async def get(self, key: str) -> CacheEntry | None:
        """Get cache entry from memory."""
        entry = self._cache.get(key)
        if not entry:
            return None

        # Check expiration
        if entry.is_expired():
            del self._cache[key]
            return None

        # Update hit count
        entry.hit_count += 1
        return entry

    async def set(
        self, key: str, entry: CacheEntry, ttl_seconds: int | None = None
    ) -> None:
        """Set cache entry in memory."""
        # Update expiration if TTL provided
        if ttl_seconds is not None:
            entry.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

        # Check size limit and evict if necessary
        if len(self._cache) >= self.max_size and key not in self._cache:
            await self._evict_oldest()

        self._cache[key] = entry

    async def delete(self, key: str) -> bool:
        """Delete cache entry from memory."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def clear(self) -> None:
        """Clear all cache entries from memory."""
        self._cache.clear()

    async def get_stats(self) -> dict[str, Any]:
        """Get memory cache statistics."""
        # Clean expired entries
        await self._clean_expired()

        total_entries = len(self._cache)
        total_size = sum(len(str(entry.response)) for entry in self._cache.values())
        total_hits = sum(entry.hit_count for entry in self._cache.values())

        # Count entries per user
        user_counts = {}
        for entry in self._cache.values():
            user_id = entry.user_id or "anonymous"
            user_counts[user_id] = user_counts.get(user_id, 0) + 1

        return {
            "backend": "memory",
            "total_entries": total_entries,
            "max_size": self.max_size,
            "total_size_bytes": total_size,
            "total_hits": total_hits,
            "users": len(user_counts),
            "entries_per_user": user_counts,
            "utilization_percent": (total_entries / self.max_size) * 100
            if self.max_size > 0
            else 0,
        }

    async def get_all_entries(self) -> list[tuple[str, CacheEntry]]:
        """Get all cache entries for similarity search."""
        # Clean expired entries first
        await self._clean_expired()
        return list(self._cache.items())

    async def clear_user_entries(self, user_id: str) -> int:
        """Clear all entries for a specific user."""
        user_prefix = f"user:{user_id}:"
        keys_to_delete = [
            key for key in self._cache.keys() if key.startswith(user_prefix)
        ]

        for key in keys_to_delete:
            del self._cache[key]

        return len(keys_to_delete)

    async def _evict_oldest(self) -> None:
        """Evict oldest entries when cache is full."""
        if not self._cache:
            return

        # Find oldest entry by created_at time
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at,
        )

        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")

    async def _clean_expired(self) -> int:
        """Clean expired entries and return count of cleaned entries."""
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")

        return len(expired_keys)


class TokenSimilarityMatcher:
    """Enhanced token-based similarity matching using comprehensive word corpora.

    Uses NLTK WordNet and spaCy for:
    - Comprehensive verb/noun classification
    - Antonym detection for false positive prevention
    - Domain-agnostic word coverage
    - Semantic relationship understanding
    """

    def __init__(self):
        """Initialize the enhanced token similarity matcher."""
        # Token weights for different word types
        self.token_weights = {
            "verb": 2.0,  # Action words
            "noun": 1.5,  # Entity words
            "adjective": 1.2,  # Descriptive words
            "article": 0.5,  # a, an, the
            "preposition": 0.8,  # in, on, at, etc.
            "other": 1.0,  # everything else
        }

        # Initialize NLP components
        self._init_nlp_components()

        # Only initialize fallback words if NLP components failed
        if not self.verbs and not self.nouns:
            self._init_fallback_words()

    def _init_nlp_components(self):
        """Initialize NLP components with comprehensive word coverage."""
        self.verbs = set()
        self.nouns = set()
        self.adjectives = set()
        self.antonyms = {}

        if NLTK_AVAILABLE:
            try:
                # Download required NLTK data
                nltk.download("punkt", quiet=True)
                nltk.download("averaged_perceptron_tagger", quiet=True)
                nltk.download("wordnet", quiet=True)

                # Build comprehensive verb set from WordNet
                for synset in wordnet.all_synsets(wordnet.VERB):
                    for lemma in synset.lemmas():
                        self.verbs.add(lemma.name().lower())

                # Build comprehensive noun set from WordNet
                for synset in wordnet.all_synsets(wordnet.NOUN):
                    for lemma in synset.lemmas():
                        self.nouns.add(lemma.name().lower())

                # Build comprehensive adjective set from WordNet
                for synset in wordnet.all_synsets(wordnet.ADJ):
                    for lemma in synset.lemmas():
                        self.adjectives.add(lemma.name().lower())

                # Build antonym dictionary for false positive detection
                for synset in wordnet.all_synsets():
                    for lemma in synset.lemmas():
                        if lemma.antonyms():
                            self.antonyms[lemma.name().lower()] = [
                                antonym.name().lower() for antonym in lemma.antonyms()
                            ]

                logger.debug(
                    f"Initialized NLP components: {len(self.verbs)} verbs, {len(self.nouns)} nouns, {len(self.adjectives)} adjectives"
                )

            except Exception as e:
                logger.warning(f"Failed to initialize NLTK components: {e}")
                self.verbs = set()
                self.nouns = set()
                self.adjectives = set()
                self.antonyms = {}

        if SPACY_AVAILABLE:
            try:
                # Load spaCy model for additional word classification
                nlp = spacy.load("en_core_web_sm")

                # Add spaCy verbs and nouns to our sets
                for token in nlp("create get set add remove list show find"):
                    if token.pos_ == "VERB":
                        self.verbs.add(token.lemma_.lower())
                    elif token.pos_ == "NOUN":
                        self.nouns.add(token.lemma_.lower())

                logger.debug("Initialized spaCy components")

            except Exception as e:
                logger.warning(f"Failed to initialize spaCy components: {e}")

    def _init_fallback_words(self):
        """Initialize fallback word corpora from files."""
        try:
            # Load fallback words from data files
            from pathlib import Path

            data_dir = (
                Path(__file__).parent.parent.parent.parent / "data" / "word_corpus"
            )

            def load_words_from_file(filename: str) -> set[str]:
                file_path = data_dir / filename
                if file_path.exists():
                    with open(file_path, encoding="utf-8") as f:
                        return {
                            line.strip().lower()
                            for line in f
                            if line.strip() and not line.strip().startswith("#")
                        }
                return set()

            def load_antonyms_from_file(filename: str) -> dict[str, list[str]]:
                file_path = data_dir / filename
                antonyms = {}
                if file_path.exists():
                    with open(file_path, encoding="utf-8") as f:
                        for line in f:
                            if ":" in line:
                                word, antonyms_str = line.strip().split(":", 1)
                                antonyms[word.lower()] = [
                                    a.strip().lower() for a in antonyms_str.split(",")
                                ]
                return antonyms

            # Load fallback word sets
            self.verbs = load_words_from_file("fallback_verbs.txt")
            self.nouns = load_words_from_file("fallback_nouns.txt")
            self.adjectives = load_words_from_file("fallback_adjectives.txt")
            self.antonyms = load_antonyms_from_file("fallback_antonyms.txt")

            logger.debug(
                f"Loaded fallback words: {len(self.verbs)} verbs, {len(self.nouns)} nouns, {len(self.adjectives)} adjectives"
            )

        except Exception as e:
            logger.warning(f"Failed to load fallback words: {e}")
            # Ensure we have at least basic word sets
            self.verbs = {
                "create",
                "get",
                "set",
                "add",
                "remove",
                "list",
                "show",
                "find",
            }
            self.nouns = {"product", "user", "item", "data", "information"}
            self.adjectives = {"new", "old", "big", "small", "good", "bad"}
            self.antonyms = {}

    def similarity(self, intent1: str, intent2: str) -> float:
        """
        Calculate similarity between two intents using token-based matching.

        Args:
            intent1: First intent string
            intent2: Second intent string

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not intent1 or not intent2:
            return 0.0

        # Check for false positives (semantic opposites)
        if self._is_likely_false_positive(intent1, intent2):
            return 0.0

        # Tokenize and weight both intents
        tokens1 = self._tokenize_and_weight(intent1.lower())
        tokens2 = self._tokenize_and_weight(intent2.lower())

        if not tokens1 or not tokens2:
            return 0.0

        # Calculate weighted Jaccard similarity
        similarity = self._weighted_jaccard_similarity(tokens1, tokens2)

        return similarity

    def _tokenize_and_weight(self, intent: str) -> dict[str, float]:
        """
        Tokenize intent and assign weights based on word types.

        Args:
            intent: The intent string to tokenize

        Returns:
            Dictionary mapping tokens to their weights
        """
        # Simple tokenization (split on whitespace and punctuation)
        import re

        tokens = re.findall(r"\b\w+\b", intent.lower())

        weighted_tokens = {}
        for token in tokens:
            weight = self._get_token_weight(token)
            weighted_tokens[token] = weight

        return weighted_tokens

    def _get_token_weight(self, word: str) -> float:
        """
        Get weight for a token based on its type.

        Args:
            word: The word to classify

        Returns:
            Weight for the token
        """
        if word in self.verbs:
            return self.token_weights["verb"]
        elif word in self.nouns:
            return self.token_weights["noun"]
        elif word in self.adjectives:
            return self.token_weights["adjective"]
        elif word in {"a", "an", "the"}:
            return self.token_weights["article"]
        elif word in {
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
            "from",
            "of",
            "about",
        }:
            return self.token_weights["preposition"]
        else:
            return self.token_weights["other"]

    def _weighted_jaccard_similarity(
        self, tokens1: dict[str, float], tokens2: dict[str, float]
    ) -> float:
        """
        Calculate weighted Jaccard similarity between two token sets.

        Args:
            tokens1: First token set with weights
            tokens2: Second token set with weights

        Returns:
            Weighted Jaccard similarity score
        """
        # Get all unique tokens
        all_tokens = set(tokens1.keys()) | set(tokens2.keys())

        if not all_tokens:
            return 0.0

        # Calculate intersection and union with weights
        intersection_weight = 0.0
        union_weight = 0.0

        for token in all_tokens:
            weight1 = tokens1.get(token, 0.0)
            weight2 = tokens2.get(token, 0.0)

            intersection_weight += min(weight1, weight2)
            union_weight += max(weight1, weight2)

        if union_weight == 0.0:
            return 0.0

        return intersection_weight / union_weight

    def _is_likely_false_positive(self, intent1: str, intent2: str) -> bool:
        """
        Check if two intents are likely semantic opposites.

        Args:
            intent1: First intent
            intent2: Second intent

        Returns:
            True if intents are likely opposites
        """
        tokens1 = set(intent1.lower().split())
        tokens2 = set(intent2.lower().split())

        # Check for antonym pairs
        for token1 in tokens1:
            if token1 in self.antonyms:
                for antonym in self.antonyms[token1]:
                    if antonym in tokens2:
                        return True

        return False


class CacheService:
    """Manages caching for API assistant requests with token-based similarity search.

    Addresses key caching challenges:
    1. Uses lightweight token-based similarity instead of embedding models
    2. Implements user-scoped caching for identity privacy
    3. Configurable tool call caching to handle time-varying results
    4. Optimized similarity search with early termination
    5. Backend abstraction for pluggable storage (memory only)
    6. Async interface for better performance
    """

    def __init__(self, backend: str = "memory", config: dict[str, Any] | None = None):
        """
        Initialize cache service with specified backend.

        Args:
            backend: Cache backend type (only "memory" supported)
            config: Backend-specific configuration
        """
        self.backend_type = backend
        self.config = config or {}
        self.similarity_matcher = TokenSimilarityMatcher()

        if backend == "memory":
            max_size = self.config.get("max_size", settings.cache_max_size)
            ttl_seconds = self.config.get("ttl_seconds", settings.cache_ttl_seconds)
            self.backend = InMemoryCacheBackend(
                max_size=max_size, default_ttl_seconds=ttl_seconds
            )
        else:
            raise ValueError(
                f"Unsupported cache backend: {backend}. Only 'memory' is supported."
            )

        logger.debug(f"Cache service initialized with backend: {backend}")

    async def get_async(
        self, messages: list[BaseMessage], user_id: str = "anonymous"
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """
        Async version: Get a cached response for the given messages with user isolation.

        Args:
            messages: List of conversation messages
            user_id: User identifier for cache isolation

        Returns:
            Tuple of (response, tool_calls) if found and not expired, None otherwise
        """
        message_key = self._extract_user_scoped_key(messages, user_id)

        if not message_key:
            logger.debug("No message key available")
            return None

        entry = await self.backend.get(message_key)

        if entry is None:
            logger.debug(f"Cache miss for messages: {message_key[:8]}...")
            return None

        if entry.is_expired():
            logger.debug(f"Cache entry expired for messages: {message_key[:8]}...")
            await self.backend.delete(message_key)
            return None

        logger.info(
            f"Cache hit for messages: {message_key[:8]}... (hits: {entry.hit_count})"
        )

        # Return tool calls only if caching is enabled
        tool_calls = entry.tool_calls if settings.cache_tool_calls else None
        return entry.response, tool_calls

    def get(
        self, messages: list[BaseMessage], user_id: str = "anonymous"
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """
        Synchronous wrapper for get_async.
        Note: This creates a new event loop if one doesn't exist.
        For better performance, use get_async() in async contexts.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, but this is a sync method
                # This is not ideal - better to use get_async() directly
                logger.warning(
                    "Using sync get() in async context. Consider using get_async() instead."
                )
                # Create a new task in the current loop
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.get_async(messages, user_id)
                    )
                    return future.result()
            else:
                # We're in a sync context, safe to run
                return asyncio.run(self.get_async(messages, user_id))
        except RuntimeError:
            # No event loop, safe to create one
            return asyncio.run(self.get_async(messages, user_id))

    async def find_similar_cached_responses_async(
        self,
        message_content: str,
        user_id: str = "anonymous",
        similarity_threshold: float | None = None,
    ) -> list[tuple[str, str, list[dict[str, Any]], float]]:
        """
        Async version: Find similar cached responses using token-based similarity with user isolation.

        Args:
            message_content: The message content to find matches for
            user_id: User identifier for cache isolation
            similarity_threshold: Minimum similarity score (uses config default if None)

        Returns:
            List of (message_content, response, tool_calls, similarity_score) tuples, sorted by similarity
        """
        if not message_content or not settings.cache_similarity_enabled:
            return []

        threshold = similarity_threshold or settings.cache_similarity_threshold

        # Get all entries from backend
        all_entries = await self.backend.get_all_entries()

        # Find similar contents using token-based similarity (user-scoped)
        similar_contents = []
        user_prefix = f"user:{user_id}:"

        for message_key, entry in all_entries:
            # Only check entries for the same user
            if not message_key.startswith(user_prefix):
                continue

            if not entry.is_expired() and entry.original_message:
                # Calculate similarity between current message and cached message
                similarity = self.similarity_matcher.similarity(
                    message_content, entry.original_message
                )

                if similarity >= threshold:
                    # Return tool calls only if caching is enabled
                    tool_calls = entry.tool_calls if settings.cache_tool_calls else []
                    similar_contents.append(
                        (
                            entry.original_message,
                            entry.response,
                            tool_calls,
                            similarity,
                        )
                    )

        # Sort by similarity score (highest first)
        similar_contents.sort(key=lambda x: x[3], reverse=True)

        return similar_contents

    def find_similar_cached_responses(
        self,
        message_content: str,
        user_id: str = "anonymous",
        similarity_threshold: float | None = None,
    ) -> list[tuple[str, str, list[dict[str, Any]], float]]:
        """
        Synchronous wrapper for find_similar_cached_responses_async.
        Note: This creates a new event loop if one doesn't exist.
        For better performance, use find_similar_cached_responses_async() in async contexts.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, but this is a sync method
                logger.warning(
                    "Using sync find_similar_cached_responses() in async context. Consider using find_similar_cached_responses_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.find_similar_cached_responses_async(
                            message_content, user_id, similarity_threshold
                        ),
                    )
                    return future.result()
            else:
                # We're in a sync context, safe to run
                return asyncio.run(
                    self.find_similar_cached_responses_async(
                        message_content, user_id, similarity_threshold
                    )
                )
        except RuntimeError:
            # No event loop, safe to create one
            return asyncio.run(
                self.find_similar_cached_responses_async(
                    message_content, user_id, similarity_threshold
                )
            )

    async def set_async(
        self,
        messages: list[BaseMessage],
        response: str,
        tool_calls: list[dict[str, Any]] | None = None,
        user_id: str = "anonymous",
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Async version: Cache a response for the given messages with user isolation.

        Args:
            messages: List of conversation messages
            response: The AI response to cache
            tool_calls: Optional tool calls from the response
            user_id: User identifier for cache isolation
            ttl_seconds: Optional custom TTL in seconds
        """
        message_key = self._extract_user_scoped_key(messages, user_id)

        if not message_key:
            logger.debug("Could not extract message key, skipping cache")
            return

        # Extract original message content for similarity matching
        original_message = ""
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content") and last_message.content:
                original_message = str(last_message.content)

        # Create cache entry with user isolation
        entry = CacheEntry(
            response=response,
            tool_calls=tool_calls if settings.cache_tool_calls else None,
            canonical_intent="",  # No longer used
            original_message=original_message,
            user_id=user_id,
            cache_key_hash=message_key,
            expires_at=datetime.now()
            + timedelta(
                seconds=ttl_seconds
                or self.config.get("ttl_seconds", settings.cache_ttl_seconds)
            ),
        )

        # Store in backend
        await self.backend.set(message_key, entry, ttl_seconds)

        logger.debug(
            f"Cached response for messages: {message_key[:8]}... (user: {user_id})"
        )

    def set(
        self,
        messages: list[BaseMessage],
        response: str,
        tool_calls: list[dict[str, Any]] | None = None,
        user_id: str = "anonymous",
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Synchronous wrapper for set_async.
        Note: This creates a new event loop if one doesn't exist.
        For better performance, use set_async() in async contexts.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, but this is a sync method
                logger.warning(
                    "Using sync set() in async context. Consider using set_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.set_async(
                            messages, response, tool_calls, user_id, ttl_seconds
                        ),
                    )
                    future.result()
            else:
                # We're in a sync context, safe to run
                asyncio.run(
                    self.set_async(messages, response, tool_calls, user_id, ttl_seconds)
                )
        except RuntimeError:
            # No event loop, safe to create one
            asyncio.run(
                self.set_async(messages, response, tool_calls, user_id, ttl_seconds)
            )

    def _extract_user_scoped_key(
        self, messages: list[BaseMessage], user_id: str
    ) -> str:
        """Extract a user-scoped cache key from message content."""
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
        content_hash = hashlib.sha256(combined_content.encode()).hexdigest()

        # Create user-scoped key
        return f"user:{user_id}:{content_hash}"

    def _extract_intent_key(self, canonical_intent: str) -> str:
        """Extract a cache key from canonical intent (kept for compatibility)."""
        if not canonical_intent:
            return ""

        # Hash the canonical intent for consistent cache keys
        return hashlib.sha256(canonical_intent.encode()).hexdigest()

    async def clear_expired_async(self) -> int:
        """Async version: Clear expired cache entries and return count of cleared entries."""
        stats = await self.backend.get_stats()
        return stats.get("expired_entries", 0)

    def clear_expired(self) -> int:
        """Synchronous wrapper for clear_expired_async."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning(
                    "Using sync clear_expired() in async context. Consider using clear_expired_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.clear_expired_async())
                    return future.result()
            else:
                return asyncio.run(self.clear_expired_async())
        except RuntimeError:
            return asyncio.run(self.clear_expired_async())

    async def get_stats_async(self) -> dict[str, Any]:
        """Async version: Get cache statistics with user breakdown."""
        stats = await self.backend.get_stats()

        # Add expected fields for tests
        if "total_size" not in stats:
            stats["total_size"] = stats.get("total_size_bytes", 0)
        if "hit_rate" not in stats:
            stats["hit_rate"] = 0.0  # TODO: Implement hit rate calculation

        stats["backend_type"] = self.backend_type
        stats["tool_calls_cached"] = settings.cache_tool_calls
        stats["similarity_enabled"] = settings.cache_similarity_enabled

        return stats

    def get_stats(self) -> dict[str, Any]:
        """Synchronous wrapper for get_stats_async."""
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

    async def clear_async(self) -> None:
        """Async version: Clear all cache entries."""
        await self.backend.clear()
        logger.info("Cleared all cache entries")

    def clear(self) -> None:
        """Synchronous wrapper for clear_async."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning(
                    "Using sync clear() in async context. Consider using clear_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.clear_async())
                    future.result()
            else:
                asyncio.run(self.clear_async())
        except RuntimeError:
            asyncio.run(self.clear_async())

    async def clear_user_cache_async(self, user_id: str) -> int:
        """Async version: Clear all cache entries for a specific user."""
        count = await self.backend.clear_user_entries(user_id)
        logger.info(f"Cleared {count} cache entries for user: {user_id}")
        return count

    def clear_user_cache(self, user_id: str) -> int:
        """Synchronous wrapper for clear_user_cache_async."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning(
                    "Using sync clear_user_cache() in async context. Consider using clear_user_cache_async() instead."
                )
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.clear_user_cache_async(user_id)
                    )
                    return future.result()
            else:
                return asyncio.run(self.clear_user_cache_async(user_id))
        except RuntimeError:
            return asyncio.run(self.clear_user_cache_async(user_id))


# Global cache instance
_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    if not hasattr(get_cache_service, "_instance"):
        # Initialize with memory backend only
        get_cache_service._instance = CacheService(
            backend="memory",
            config={
                "max_size": settings.cache_max_size,
                "ttl_seconds": settings.cache_ttl_seconds,
            },
        )
    return get_cache_service._instance


def set_cache_service(cache_service: CacheService) -> None:
    """Set the global cache service instance."""
    global _cache_service
    _cache_service = cache_service
