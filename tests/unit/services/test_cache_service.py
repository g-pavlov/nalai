"""
Unit tests for enhanced cache service with similarity search and user isolation.

Tests cover:
- User-scoped cache isolation
- Token-based similarity search
- Configurable tool call caching
- Performance optimizations
- Comprehensive similarity matching
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage

from nalai.services.cache_service import CacheService, TokenSimilarityMatcher


class TestEnhancedCacheService:
    """Test enhanced cache service functionality."""

    def test_user_isolation(self):
        """Test that cache entries are isolated by user."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Create identical messages for different users
        messages = [HumanMessage(content="create a product")]
        response = "Product created successfully"

        # Cache for user1
        cache_service.set(messages, response, user_id="user1")

        # Cache for user2
        cache_service.set(messages, response, user_id="user2")

        # Verify user1 can access their cache
        result1 = cache_service.get(messages, user_id="user1")
        assert result1 is not None
        assert result1[0] == response

        # Verify user2 can access their cache
        result2 = cache_service.get(messages, user_id="user2")
        assert result2 is not None
        assert result2[0] == response

        # Verify user3 cannot access either cache
        result3 = cache_service.get(messages, user_id="user3")
        assert result3 is None

    def test_tool_call_caching_configurable(self):
        """Test that tool call caching is configurable."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        messages = [HumanMessage(content="get user data")]
        response = "User data retrieved"
        tool_calls = [{"name": "get_user", "args": {"user_id": "123"}}]

        # Test with tool calls cached
        with patch("nalai.config.settings.cache_tool_calls", True):
            cache_service.set(messages, response, tool_calls, user_id="user1")
            result = cache_service.get(messages, user_id="user1")
            assert result is not None
            assert result[1] == tool_calls  # Tool calls should be cached

        # Test with tool calls not cached
        with patch("nalai.config.settings.cache_tool_calls", False):
            cache_service.set(messages, response, tool_calls, user_id="user2")
            result = cache_service.get(messages, user_id="user2")
            assert result is not None
            assert result[1] is None  # Tool calls should not be cached

    def test_similarity_search_user_isolation(self):
        """Test that similarity search respects user isolation."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Add similar entries for different users
        cache_service.set(
            [HumanMessage(content="create product")], "Product created", user_id="user1"
        )
        cache_service.set(
            [HumanMessage(content="create product")], "Product created", user_id="user2"
        )

        # Search for user1 with a lower threshold
        similar1 = cache_service.find_similar_cached_responses(
            "create a product", user_id="user1", similarity_threshold=0.7
        )
        assert len(similar1) == 1
        assert similar1[0][0] == "create product"

        # Search for user2 with a lower threshold
        similar2 = cache_service.find_similar_cached_responses(
            "create a product", user_id="user2", similarity_threshold=0.7
        )
        assert len(similar2) == 1
        assert similar2[0][0] == "create product"

        # Search for user3 (should find nothing)
        similar3 = cache_service.find_similar_cached_responses(
            "create a product", user_id="user3", similarity_threshold=0.7
        )
        assert len(similar3) == 0

    def test_similarity_search_disabled(self):
        """Test that similarity search can be disabled."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Add a cache entry
        cache_service.set(
            [HumanMessage(content="create product")], "Product created", user_id="user1"
        )

        # Test with similarity search disabled
        with patch("nalai.config.settings.cache_similarity_enabled", False):
            similar = cache_service.find_similar_cached_responses(
                "create a product", user_id="user1"
            )
            assert len(similar) == 0

    def test_configurable_similarity_threshold(self):
        """Test that similarity threshold is configurable."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Add cache entries
        cache_service.set(
            [HumanMessage(content="create product")], "Product created", user_id="user1"
        )
        cache_service.set(
            [HumanMessage(content="create item")], "Item created", user_id="user1"
        )

        # Test with high threshold (should find only exact matches)
        similar_high = cache_service.find_similar_cached_responses(
            "create product", user_id="user1", similarity_threshold=0.9
        )
        assert len(similar_high) == 1  # Only exact match

        # Test with low threshold (should find more matches)
        similar_low = cache_service.find_similar_cached_responses(
            "create a product", user_id="user1", similarity_threshold=0.3
        )
        assert len(similar_low) >= 1  # Should find similar matches

    def test_cache_stats_with_user_breakdown(self):
        """Test that cache stats include user breakdown."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Add entries for different users
        cache_service.set(
            [HumanMessage(content="create product")], "Product created", user_id="user1"
        )
        cache_service.set(
            [HumanMessage(content="list products")], "Products listed", user_id="user1"
        )
        cache_service.set(
            [HumanMessage(content="get user")], "User retrieved", user_id="user2"
        )

        stats = cache_service.get_stats()

        assert "total_entries" in stats
        assert "users" in stats
        assert "entries_per_user" in stats
        assert "user1" in stats["entries_per_user"]
        assert "user2" in stats["entries_per_user"]

    def test_clear_user_cache(self):
        """Test clearing cache for a specific user."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Add entries for different users
        cache_service.set(
            [HumanMessage(content="create product")], "Product created", user_id="user1"
        )
        cache_service.set(
            [HumanMessage(content="list products")], "Products listed", user_id="user2"
        )

        # Clear user1's cache
        cleared_count = cache_service.clear_user_cache("user1")
        assert cleared_count == 1

        # Verify user1's entry is gone
        result1 = cache_service.get(
            [HumanMessage(content="create product")], user_id="user1"
        )
        assert result1 is None

        # Verify user2's entry is still there
        result2 = cache_service.get(
            [HumanMessage(content="list products")], user_id="user2"
        )
        assert result2 is not None

    def test_cache_entry_with_user_data(self):
        """Test that cache entries store user data correctly."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        messages = [HumanMessage(content="create product")]
        response = "Product created"
        user_id = "test_user"

        cache_service.set(messages, response, user_id=user_id)

        # Verify the entry was stored with user data
        result = cache_service.get(messages, user_id=user_id)
        assert result is not None
        assert result[0] == response

    def test_performance_optimization(self):
        """Test that cache operations are optimized for performance."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 1000, "ttl_seconds": 3600}
        )

        # Add many entries quickly
        for i in range(100):
            messages = [HumanMessage(content=f"create product {i}")]
            cache_service.set(messages, f"Product {i} created", user_id="user1")

        # Verify all entries are accessible
        for i in range(100):
            messages = [HumanMessage(content=f"create product {i}")]
            result = cache_service.get(messages, user_id="user1")
            assert result is not None
            assert result[0] == f"Product {i} created"

    @pytest.mark.parametrize(
        "user_id,cached_messages,search_message,expected_hit",
        [
            # Same user - should hit
            (
                "cache_user",
                ["create product", "list products"],
                "create a product",
                True,
            ),
            ("cache_user", ["get user", "add item"], "get the user", True),
            ("cache_user", ["delete product", "update user"], "delete a product", True),
            # Different user - should miss
            ("user1", ["create product", "list products"], "create a product", False),
            ("user2", ["get user", "add item"], "get the user", False),
            ("user3", ["delete product", "update user"], "delete a product", False),
        ],
    )
    def test_user_isolation_in_similarity_search(
        self, user_id, cached_messages, search_message, expected_hit
    ):
        """Test that similarity search respects user isolation."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Add cached messages for cache_user
        for message in cached_messages:
            cache_service.set(
                [HumanMessage(content=message)],
                f"Response for {message}",
                user_id="cache_user",
            )

        # Search for the specified user with lower threshold to account for actual similarity values
        similar = cache_service.find_similar_cached_responses(
            search_message, user_id=user_id, similarity_threshold=0.7
        )

        if expected_hit:
            assert len(similar) > 0, (
                f"Expected to find similar messages for user {user_id}"
            )
        else:
            assert len(similar) == 0, f"Expected no similar messages for user {user_id}"

    def test_similarity_search_performance_under_load(self):
        """Test that similarity search performs well under load."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 1000, "ttl_seconds": 3600}
        )

        # Add many cache entries
        for i in range(100):
            cache_service.set(
                [HumanMessage(content=f"create product {i}")],
                f"Product {i} created",
                user_id="user1",
            )

        # Add some similar entries
        cache_service.set(
            [HumanMessage(content="create product")], "Product created", user_id="user1"
        )
        cache_service.set(
            [HumanMessage(content="create a product")],
            "Product created",
            user_id="user1",
        )

        # Search for similar messages (should be fast)
        import time

        start_time = time.time()
        similar = cache_service.find_similar_cached_responses(
            "create the product", user_id="user1", similarity_threshold=0.7
        )
        end_time = time.time()

        # Should complete quickly (less than 1 second)
        assert end_time - start_time < 1.0, "Similarity search took too long"

        # Should find the similar entries (with lower threshold)
        assert len(similar) >= 1, "Expected to find at least one similar entry"


class TestTokenSimilarityMatcher:
    """Test token-based similarity matcher."""

    def test_fallback_files_loading(self):
        """Test that fallback files are loaded correctly."""
        # Test that fallback files exist and are loaded
        data_dir = Path(__file__).parent.parent.parent.parent / "data" / "word_corpus"

        assert (data_dir / "fallback_verbs.txt").exists(), "Fallback verbs file missing"
        assert (data_dir / "fallback_nouns.txt").exists(), "Fallback nouns file missing"
        assert (data_dir / "fallback_adjectives.txt").exists(), (
            "Fallback adjectives file missing"
        )
        assert (data_dir / "fallback_antonyms.txt").exists(), (
            "Fallback antonyms file missing"
        )

    def test_token_weighting_logic(self):
        """Test the token weighting logic without depending on corpus content."""
        matcher = TokenSimilarityMatcher()

        # Test the weighting algorithm with known words
        # We'll test the logic by temporarily setting the corpus sets
        original_verbs = matcher.verbs
        original_nouns = matcher.nouns
        original_adjectives = matcher.adjectives

        # Set up a controlled test environment
        matcher.verbs = {"create", "add", "get", "delete"}
        matcher.nouns = {"user", "product", "data"}
        matcher.adjectives = {"active", "new", "old"}

        try:
            # Test verb weighting (weight: 2.0)
            verb_tokens = matcher._tokenize_and_weight("create user")
            assert verb_tokens.get("create", 0) == 2.0, "Verb should have weight 2.0"

            # Test noun weighting (weight: 1.5)
            noun_tokens = matcher._tokenize_and_weight("user product")
            assert noun_tokens.get("user", 0) == 1.5, "Noun should have weight 1.5"
            assert noun_tokens.get("product", 0) == 1.5, "Noun should have weight 1.5"

            # Test adjective weighting (weight: 1.2)
            adj_tokens = matcher._tokenize_and_weight("active user")
            assert adj_tokens.get("active", 0) == 1.2, (
                "Adjective should have weight 1.2"
            )

            # Test article weighting (weight: 0.5)
            article_tokens = matcher._tokenize_and_weight("the user")
            assert article_tokens.get("the", 0) == 0.5, "Article should have weight 0.5"

            # Test preposition weighting (weight: 0.8)
            prep_tokens = matcher._tokenize_and_weight("get from user")
            assert prep_tokens.get("from", 0) == 0.8, (
                "Preposition should have weight 0.8"
            )

            # Test unknown word weighting (weight: 1.0)
            unknown_tokens = matcher._tokenize_and_weight("xyz user")
            assert unknown_tokens.get("xyz", 0) == 1.0, (
                "Unknown word should have weight 1.0"
            )

            # Test case insensitivity
            mixed_case_tokens = matcher._tokenize_and_weight("Create User")
            assert mixed_case_tokens.get("create", 0) == 2.0, (
                "Case should be normalized"
            )

        finally:
            # Restore original corpus
            matcher.verbs = original_verbs
            matcher.nouns = original_nouns
            matcher.adjectives = original_adjectives

    def test_weighted_jaccard_similarity_logic(self):
        """Test the weighted Jaccard similarity algorithm without corpus dependency."""
        matcher = TokenSimilarityMatcher()

        # Test with controlled token sets
        tokens1 = {"create": 2.0, "user": 1.5, "the": 0.5}
        tokens2 = {"create": 2.0, "user": 1.5, "data": 1.5}

        similarity = matcher._weighted_jaccard_similarity(tokens1, tokens2)

        # Should be > 0 since there are common tokens
        assert similarity > 0.0, "Similarity should be positive for overlapping tokens"
        assert similarity <= 1.0, "Similarity should be <= 1.0"

        # Test with identical tokens
        tokens3 = {"create": 2.0, "user": 1.5}
        similarity_identical = matcher._weighted_jaccard_similarity(tokens3, tokens3)
        assert similarity_identical == 1.0, (
            "Identical tokens should have similarity 1.0"
        )

        # Test with no overlap
        tokens4 = {"create": 2.0, "user": 1.5}
        tokens5 = {"delete": 2.0, "data": 1.5}
        similarity_no_overlap = matcher._weighted_jaccard_similarity(tokens4, tokens5)
        assert similarity_no_overlap == 0.0, "No overlap should have similarity 0.0"

        # Test with empty tokens
        empty_similarity = matcher._weighted_jaccard_similarity({}, {})
        assert empty_similarity == 0.0, "Empty tokens should have similarity 0.0"

    def test_fallback_graceful_degradation(self):
        """Test that the system gracefully degrades when NLP libraries are unavailable."""
        with (
            patch("nalai.services.cache_service.NLTK_AVAILABLE", False),
            patch("nalai.services.cache_service.SPACY_AVAILABLE", False),
        ):
            matcher = TokenSimilarityMatcher()

            # Should still have basic functionality
            assert len(matcher.verbs) > 0, "Should have fallback verbs"
            assert len(matcher.nouns) > 0, "Should have fallback nouns"
            assert len(matcher.adjectives) > 0, "Should have fallback adjectives"
            assert len(matcher.antonyms) > 0, "Should have fallback antonyms"

            # Should still be able to calculate similarity
            similarity = matcher.similarity("create user", "add user")
            assert isinstance(similarity, float)
            assert 0.0 <= similarity <= 1.0

    def test_corpus_statistics(self):
        """Test that corpus statistics are accurate."""
        matcher = TokenSimilarityMatcher()

        # Verify corpus has reasonable size
        assert len(matcher.verbs) >= 80, f"Too few verbs: {len(matcher.verbs)}"
        assert len(matcher.nouns) >= 100, f"Too few nouns: {len(matcher.nouns)}"
        assert len(matcher.adjectives) >= 100, (
            f"Too few adjectives: {len(matcher.adjectives)}"
        )
        assert len(matcher.antonyms) >= 100, (
            f"Too few antonym pairs: {len(matcher.antonyms)}"
        )

        # Verify no empty entries
        assert all(word.strip() for word in matcher.verbs), "Empty verb entries found"
        assert all(word.strip() for word in matcher.nouns), "Empty noun entries found"
        assert all(word.strip() for word in matcher.adjectives), (
            "Empty adjective entries found"
        )

    def test_edge_cases(self):
        """Test edge cases and error handling."""
        matcher = TokenSimilarityMatcher()

        # Empty inputs
        assert matcher.similarity("", "") == 0.0
        assert matcher.similarity("", "test") == 0.0
        assert matcher.similarity("test", "") == 0.0

        # Single word inputs
        similarity = matcher.similarity("create", "add")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0

        # Very long inputs
        long_input = (
            "create user with detailed profile information and comprehensive settings"
        )
        similarity = matcher.similarity(long_input, "add new user")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0

    def test_performance_characteristics(self):
        """Test that similarity calculation is fast enough for critical path usage."""
        matcher = TokenSimilarityMatcher()
        import time

        # Test multiple similarity calculations
        test_pairs = [
            ("create user", "add user"),
            ("list products", "show products"),
            ("update profile", "modify profile"),
            ("delete order", "remove order"),
            ("enable service", "activate service"),
            ("disable feature", "deactivate feature"),
            ("start process", "launch process"),
            ("stop service", "terminate service"),
        ]

        start_time = time.time()

        for intent1, intent2 in test_pairs:
            similarity = matcher.similarity(intent1, intent2)
            assert isinstance(similarity, float)

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete 8 similarity calculations in under 100ms
        assert total_time < 0.1, (
            f"Similarity calculation too slow: {total_time:.3f}s for 8 calculations"
        )

    def test_fallback_files_exist(self):
        """Test that all required fallback files exist."""
        data_dir = Path(__file__).parent.parent.parent.parent / "data" / "word_corpus"

        required_files = [
            "fallback_verbs.txt",
            "fallback_nouns.txt",
            "fallback_adjectives.txt",
            "fallback_antonyms.txt",
        ]

        for filename in required_files:
            filepath = data_dir / filename
            assert filepath.exists(), f"Required fallback file missing: {filename}"
            assert filepath.stat().st_size > 0, f"Fallback file is empty: {filename}"

    def test_fallback_file_format(self):
        """Test that fallback files have correct format."""
        data_dir = Path(__file__).parent.parent.parent.parent / "data" / "word_corpus"

        # Test word files (one word per line)
        word_files = [
            "fallback_verbs.txt",
            "fallback_nouns.txt",
            "fallback_adjectives.txt",
        ]
        for filename in word_files:
            filepath = data_dir / filename
            with open(filepath, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Should be a single word
                        assert " " not in line, (
                            f"Line {line_num} in {filename} contains spaces: '{line}'"
                        )
                        assert line.islower(), (
                            f"Line {line_num} in {filename} not lowercase: '{line}'"
                        )

        # Test antonym file (word:antonym1,antonym2 format)
        antonym_file = data_dir / "fallback_antonyms.txt"
        with open(antonym_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#"):
                    assert ":" in line, (
                        f"Line {line_num} missing colon separator: '{line}'"
                    )
                    word, antonyms = line.split(":", 1)
                    assert antonyms, f"Line {line_num} has no antonyms: '{line}'"
                    assert "," in antonyms, (
                        f"Line {line_num} has no comma-separated antonyms: '{line}'"
                    )

    def test_fallback_file_content(self):
        """Test that fallback files contain expected content."""
        data_dir = Path(__file__).parent.parent.parent.parent / "data" / "word_corpus"

        # Test that key API words are present
        expected_verbs = {
            "create",
            "add",
            "get",
            "list",
            "update",
            "delete",
            "enable",
            "disable",
        }
        expected_nouns = {
            "user",
            "product",
            "order",
            "data",
            "system",
            "service",
            "api",
        }
        expected_adjectives = {
            "active",
            "enabled",
            "valid",
            "secure",
            "public",
            "private",
        }

        # Check verbs
        with open(data_dir / "fallback_verbs.txt", encoding="utf-8") as f:
            verbs = {
                line.strip().lower()
                for line in f
                if line.strip() and not line.startswith("#")
            }
            missing_verbs = expected_verbs - verbs
            assert not missing_verbs, f"Missing expected verbs: {missing_verbs}"

        # Check nouns
        with open(data_dir / "fallback_nouns.txt", encoding="utf-8") as f:
            nouns = {
                line.strip().lower()
                for line in f
                if line.strip() and not line.startswith("#")
            }
            missing_nouns = expected_nouns - nouns
            assert not missing_nouns, f"Missing expected nouns: {missing_nouns}"

        # Check adjectives
        with open(data_dir / "fallback_adjectives.txt", encoding="utf-8") as f:
            adjectives = {
                line.strip().lower()
                for line in f
                if line.strip() and not line.startswith("#")
            }
            missing_adjectives = expected_adjectives - adjectives
            assert not missing_adjectives, (
                f"Missing expected adjectives: {missing_adjectives}"
            )

        # Check antonyms
        with open(data_dir / "fallback_antonyms.txt", encoding="utf-8") as f:
            antonyms_content = f.read()
            expected_antonym_pairs = ["create:delete", "enable:disable", "add:remove"]
            for pair in expected_antonym_pairs:
                assert pair in antonyms_content, f"Missing antonym pair: {pair}"

    def test_similarity_basic(self):
        """Test basic similarity calculation."""
        matcher = TokenSimilarityMatcher()

        # Debug: Check what corpus is loaded
        print(
            f"Corpus loaded: {len(matcher.verbs)} verbs, {len(matcher.nouns)} nouns, {len(matcher.adjectives)} adjectives"
        )

        similarity = matcher.similarity("create product", "create product")
        assert similarity == 1.0, f"Exact match should be 1.0, got {similarity}"

        similarity = matcher.similarity("create product", "create a product")
        assert similarity >= 0.6, f"Similarity should be >= 0.6, got {similarity}"

    def test_similarity_with_articles(self):
        """Test similarity with articles (a, an, the)."""
        matcher = TokenSimilarityMatcher()

        similarity1 = matcher.similarity("create product", "create a product")
        similarity2 = matcher.similarity("create product", "create the product")

        assert similarity1 > 0.6
        assert similarity2 > 0.6

    def test_false_positive_detection(self):
        """Test that semantic opposites are detected."""
        matcher = TokenSimilarityMatcher()

        # These should return low similarity due to antonym detection
        similarity = matcher.similarity("create product", "delete product")
        assert similarity <= 0.3, (
            f"Antonyms should have low similarity, got {similarity}"
        )

    def test_performance_optimization(self):
        """Test that similarity calculation is optimized."""
        matcher = TokenSimilarityMatcher()

        import time

        start_time = time.time()

        # Calculate many similarities quickly
        for i in range(100):
            matcher.similarity(f"create product {i}", f"create item {i}")

        end_time = time.time()

        # Should complete quickly
        assert end_time - start_time < 1.0

    def test_similarity_threshold_behavior_corpus_aware(self):
        """Test that similarity threshold correctly filters results based on actual corpus."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Add test messages
        test_messages = [
            "create product",
            "create a product",
            "create item",
            "list products",
            "show products",
            "get user",
            "fetch user",
        ]

        for message in test_messages:
            cache_service.set(
                [HumanMessage(content=message)],
                f"Response for {message}",
                user_id="user1",
            )

        # Test with different thresholds
        search_message = "create a product"

        # High threshold (0.9) - should find only exact or very close matches
        similar_high = cache_service.find_similar_cached_responses(
            search_message, user_id="user1", similarity_threshold=0.9
        )
        assert len(similar_high) >= 1, (
            "Should find at least exact match with high threshold"
        )

        # Medium threshold (0.7) - should find more matches
        similar_medium = cache_service.find_similar_cached_responses(
            search_message, user_id="user1", similarity_threshold=0.7
        )
        assert len(similar_medium) >= len(similar_high), (
            "Medium threshold should find more matches"
        )

        # Low threshold (0.3) - should find many matches
        similar_low = cache_service.find_similar_cached_responses(
            search_message, user_id="user1", similarity_threshold=0.3
        )
        assert len(similar_low) >= len(similar_medium), (
            "Low threshold should find more matches"
        )

    def test_antonym_detection_corpus_aware(self):
        """Test that antonym detection works correctly with the actual corpus."""
        cache_service = CacheService(
            backend="memory", config={"max_size": 10, "ttl_seconds": 3600}
        )

        # Test antonym pairs - should return 0.0 similarity
        antonym_pairs = [
            ("create product", "delete product"),
            ("add user", "remove user"),
            ("enable service", "disable service"),
            ("start process", "stop process"),
            ("activate feature", "deactivate feature"),
        ]

        for positive, negative in antonym_pairs:
            # Add the positive action
            cache_service.set(
                [HumanMessage(content=positive)],
                f"Response for {positive}",
                user_id="user1",
            )

            # Search for the negative action
            similar = cache_service.find_similar_cached_responses(
                negative,
                user_id="user1",
                similarity_threshold=0.0,  # Include all matches
            )

            # Should either find no matches or matches with very low similarity
            if len(similar) > 0:
                similarity_score = similar[0][3]
                assert similarity_score <= 0.3, (
                    f"Antonym pair '{positive}' vs '{negative}' should have low similarity, got {similarity_score}"
                )
