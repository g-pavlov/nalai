"""
Unit tests for enhanced word corpus with NLTK and spaCy integration.

Tests the TokenSimilarityMatcher with comprehensive word coverage
and validates that both NLP libraries and fallback files work correctly.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from nalai.services.cache_service import TokenSimilarityMatcher


class TestEnhancedWordCorpus:
    """Test the enhanced word corpus functionality."""

    @pytest.fixture(scope="class")
    def matcher(self):
        """Shared matcher instance to avoid repeated initialization overhead."""
        return TokenSimilarityMatcher()

    def test_nltk_integration_available(self, matcher):
        """Test that NLTK integration works when available."""
        try:
            # Import NLTK libraries for testing
            import nltk  # noqa: F401
            from nltk.corpus import wordnet  # noqa: F401

            # Verify NLTK data is loaded
            assert len(matcher.verbs) > 10000, (
                f"Expected >10k verbs, got {len(matcher.verbs)}"
            )
            assert len(matcher.nouns) > 80000, (
                f"Expected >80k nouns, got {len(matcher.nouns)}"
            )
            assert len(matcher.adjectives) > 15000, (
                f"Expected >15k adjectives, got {len(matcher.adjectives)}"
            )
            assert len(matcher.antonyms) > 5000, (
                f"Expected >5k antonym pairs, got {len(matcher.antonyms)}"
            )

            # Test that common API words are included
            api_verbs = {
                "create",
                "add",
                "get",
                "list",
                "update",
                "delete",
                "enable",
                "disable",
            }
            api_nouns = {"user", "product", "order", "data", "system", "service"}

            missing_verbs = api_verbs - matcher.verbs
            missing_nouns = api_nouns - matcher.nouns

            assert not missing_verbs, f"Missing API verbs: {missing_verbs}"
            assert not missing_nouns, f"Missing API nouns: {missing_nouns}"

        except ImportError:
            pytest.skip("NLTK not available")

    def test_spacy_integration_available(self, matcher):
        """Test that spaCy integration works when available."""
        try:
            import spacy

            # Test that spaCy can be loaded (if available)
            nlp = spacy.load("en_core_web_sm")
            assert nlp is not None

        except (ImportError, OSError):
            pytest.skip("spaCy not available")

    def test_fallback_files_loading(self, matcher):
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

    @pytest.mark.parametrize(
        "intent1,intent2,expected_min",
        [
            # API operations - should have moderate similarity
            ("create user", "add new user", 0.2),
            ("list products", "show all products", 0.15),
            ("delete order", "remove order", 0.3),
            ("update profile", "modify user profile", 0.25),
            # System operations - should have moderate similarity
            ("start service", "activate service", 0.3),
            ("stop process", "terminate process", 0.3),
            ("enable feature", "activate feature", 0.3),
            ("disable access", "deactivate access", 0.3),
            # Data operations - should have moderate similarity
            ("export data", "download data", 0.25),
            ("import file", "upload file", 0.3),
            ("backup database", "create backup", 0.25),
            ("restore system", "recover system", 0.25),
            # Security operations - should have moderate similarity
            ("authenticate user", "login user", 0.3),
            ("authorize access", "grant permission", 0.0),  # No common words
            ("encrypt data", "secure data", 0.25),
            ("decrypt message", "decode message", 0.3),
        ],
    )
    def test_similarity_with_comprehensive_corpus(
        self, matcher, intent1, intent2, expected_min
    ):
        """Test similarity matching with comprehensive word corpus."""

        similarity = matcher.similarity(intent1, intent2)

        # Similarity should be above minimum threshold
        assert similarity >= expected_min, (
            f"Similarity {similarity:.3f} below expected minimum {expected_min} "
            f"for '{intent1}' vs '{intent2}'"
        )

    @pytest.mark.parametrize(
        "intent1,intent2,setup_type,expected_min,expected_max",
        [
            # Setup 1: NLTK + spaCy (comprehensive corpus)
            ("create user", "add new user", "nltk_spacy", 0.2, 0.8),
            ("list products", "show all products", "nltk_spacy", 0.15, 0.7),
            ("delete order", "remove order", "nltk_spacy", 0.3, 0.9),
            ("update profile", "modify user profile", "nltk_spacy", 0.25, 0.8),
            # Setup 2: NLTK only (WordNet corpus)
            ("create user", "add new user", "nltk_only", 0.15, 0.7),
            ("list products", "show all products", "nltk_only", 0.1, 0.6),
            ("delete order", "remove order", "nltk_only", 0.25, 0.8),
            ("update profile", "modify user profile", "nltk_only", 0.2, 0.7),
            # Setup 3: Fallback only (basic corpus)
            ("create user", "add new user", "fallback_only", 0.1, 0.6),
            ("list products", "show all products", "fallback_only", 0.05, 0.5),
            ("delete order", "remove order", "fallback_only", 0.2, 0.7),
            ("update profile", "modify user profile", "fallback_only", 0.15, 0.6),
        ],
    )
    def test_similarity_with_different_setups(
        self, intent1, intent2, setup_type, expected_min, expected_max
    ):
        """Test similarity matching with different NLP setups and corresponding thresholds."""
        # Mock the setup based on setup_type
        if setup_type == "nltk_spacy":
            # Full setup - use real TokenSimilarityMatcher
            matcher = TokenSimilarityMatcher()
        elif setup_type == "nltk_only":
            # Mock spaCy unavailable
            with patch("nalai.services.cache_service.SPACY_AVAILABLE", False):
                with patch("nalai.services.cache_service.NLTK_AVAILABLE", True):
                    matcher = TokenSimilarityMatcher()
        elif setup_type == "fallback_only":
            # Mock both NLTK and spaCy unavailable
            with patch("nalai.services.cache_service.SPACY_AVAILABLE", False):
                with patch("nalai.services.cache_service.NLTK_AVAILABLE", False):
                    matcher = TokenSimilarityMatcher()
        else:
            pytest.fail(f"Unknown setup type: {setup_type}")

        similarity = matcher.similarity(intent1, intent2)

        # Similarity should be within expected range for the setup
        assert expected_min <= similarity <= expected_max, (
            f"Similarity {similarity:.3f} outside expected range [{expected_min}, {expected_max}] "
            f"for setup '{setup_type}' with '{intent1}' vs '{intent2}'"
        )

    @pytest.mark.parametrize(
        "intent1,intent2",
        [
            # These should have very low similarity due to antonym detection
            ("create user", "delete user"),
            ("enable service", "disable service"),
            ("start process", "stop process"),
            ("authenticate user", "deauthenticate user"),
            ("add product", "remove product"),
            ("grant access", "revoke access"),
            ("lock account", "unlock account"),
            ("encrypt data", "decrypt data"),
            ("compress file", "decompress file"),
            ("archive data", "extract data"),
            ("import data", "export data"),
            ("upgrade system", "downgrade system"),
            ("deploy service", "undeploy service"),
            ("backup database", "restore database"),
            ("sync files", "desync files"),
            ("validate input", "invalidate input"),
            ("cache result", "uncache result"),
            ("refresh token", "expire token"),
            ("renew license", "expire license"),
            ("clean data", "dirty data"),
            ("purge cache", "restore cache"),
            ("flush buffer", "retain buffer"),
            ("clear logs", "fill logs"),
        ],
    )
    def test_antonym_detection(self, matcher, intent1, intent2):
        """Test that antonyms have very low similarity scores."""

        similarity = matcher.similarity(intent1, intent2)

        # Antonyms should have very low similarity (below 0.5)
        assert similarity < 0.5, (
            f"Expected low similarity for antonyms '{intent1}' vs '{intent2}', "
            f"got {similarity:.3f}"
        )

    @pytest.mark.parametrize(
        "intent1,intent2,setup_type,expected_max",
        [
            # Setup 1: NLTK + spaCy (comprehensive corpus) - better antonym detection
            ("create user", "delete user", "nltk_spacy", 0.3),
            ("enable service", "disable service", "nltk_spacy", 0.3),
            ("start process", "stop process", "nltk_spacy", 0.3),
            ("add product", "remove product", "nltk_spacy", 0.3),
            # Setup 2: NLTK only (WordNet corpus) - moderate antonym detection
            ("create user", "delete user", "nltk_only", 0.4),
            ("enable service", "disable service", "nltk_only", 0.4),
            ("start process", "stop process", "nltk_only", 0.4),
            ("add product", "remove product", "nltk_only", 0.4),
            # Setup 3: Fallback only (basic corpus) - limited antonym detection
            ("create user", "delete user", "fallback_only", 0.5),
            ("enable service", "disable service", "fallback_only", 0.5),
            ("start process", "stop process", "fallback_only", 0.5),
            ("add product", "remove product", "fallback_only", 0.5),
        ],
    )
    def test_antonym_detection_with_different_setups(
        self, intent1, intent2, setup_type, expected_max
    ):
        """Test antonym detection with different NLP setups and corresponding thresholds."""
        # Mock the setup based on setup_type
        if setup_type == "nltk_spacy":
            # Full setup - use real TokenSimilarityMatcher
            matcher = TokenSimilarityMatcher()
        elif setup_type == "nltk_only":
            # Mock spaCy unavailable
            with patch("nalai.services.cache_service.SPACY_AVAILABLE", False):
                with patch("nalai.services.cache_service.NLTK_AVAILABLE", True):
                    matcher = TokenSimilarityMatcher()
        elif setup_type == "fallback_only":
            # Mock both NLTK and spaCy unavailable
            with patch("nalai.services.cache_service.SPACY_AVAILABLE", False):
                with patch("nalai.services.cache_service.NLTK_AVAILABLE", False):
                    matcher = TokenSimilarityMatcher()
        else:
            pytest.fail(f"Unknown setup type: {setup_type}")

        similarity = matcher.similarity(intent1, intent2)

        # Antonyms should have similarity below the expected maximum for the setup
        assert similarity <= expected_max, (
            f"Antonym similarity {similarity:.3f} above expected maximum {expected_max} "
            f"for setup '{setup_type}' with '{intent1}' vs '{intent2}'"
        )

    def test_token_weighting(self, matcher):
        """Test that different token types are weighted correctly."""

        # Test verb weighting (weight: 2.0)
        verb_tokens = matcher._tokenize_and_weight("create user")
        assert verb_tokens.get("create", 0) == 2.0

        # Test noun weighting (weight: 1.5)
        noun_tokens = matcher._tokenize_and_weight("user product")
        assert noun_tokens.get("user", 0) == 1.5
        assert noun_tokens.get("product", 0) == 1.5

        # Test adjective weighting (weight: 1.2)
        adj_tokens = matcher._tokenize_and_weight("active user")
        # "active" can be both noun and adjective, so check it's weighted appropriately
        assert adj_tokens.get("active", 0) >= 1.2, (
            f"Expected 'active' to have weight >= 1.2, got {adj_tokens.get('active', 0)}"
        )

        # Test article weighting (weight: 0.5)
        article_tokens = matcher._tokenize_and_weight("the user")
        assert article_tokens.get("the", 0) == 0.5

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

    def test_corpus_statistics(self, matcher):
        """Test that corpus statistics are accurate."""

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

    def test_edge_cases(self, matcher):
        """Test edge cases and error handling."""

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

    def test_performance_characteristics(self, matcher):
        """Test that similarity calculation is fast enough for critical path usage."""
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


class TestFallbackFileLoading:
    """Test fallback file loading functionality."""

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
