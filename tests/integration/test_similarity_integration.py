"""
Integration tests for similarity matching with actual NLP corpora.

These tests verify the end-to-end behavior of similarity matching
with real NLTK/spaCy corpora, which is deterministic but library-dependent.
"""

from pathlib import Path

import pytest
import yaml

from nalai.services.cache_service import TokenSimilarityMatcher


def detect_corpus_type(matcher):
    """Detect which corpus is loaded based on word counts."""
    verb_count = len(matcher.verbs)
    noun_count = len(matcher.nouns)

    if verb_count > 10000 and noun_count > 80000:
        return "nltk"
    elif verb_count > 1000 and noun_count > 1000:
        return "comprehensive"
    else:
        return "fallback"


def load_similarity_test_cases():
    """Load similarity test cases from YAML file."""
    test_data_file = (
        Path(__file__).parent.parent
        / "unit"
        / "test_data"
        / "similarity_test_cases.yaml"
    )
    with open(test_data_file) as f:
        data = yaml.safe_load(f)
    return data["test_cases"]


class TestSimilarityIntegration:
    """Integration tests for similarity matching with actual corpora."""

    @pytest.mark.slow
    @pytest.mark.parametrize("test_case", load_similarity_test_cases())
    def test_similarity_comprehensive_corpus_specific(self, test_case):
        """Test comprehensive similarity matching with corpus-specific expected values."""
        matcher = TokenSimilarityMatcher()
        actual_corpus = detect_corpus_type(matcher)

        intent1 = test_case["intent1"]
        intent2 = test_case["intent2"]

        # Get expected range for actual corpus
        min_key = f"{actual_corpus}_min_similarity"
        max_key = f"{actual_corpus}_max_similarity"

        if min_key in test_case and max_key in test_case:
            min_expected = test_case[min_key]
            max_expected = test_case[max_key]
            similarity = matcher.similarity(intent1, intent2)
            assert min_expected <= similarity <= max_expected, (
                f"Corpus {actual_corpus}: '{intent1}' vs '{intent2}' "
                f"expected [{min_expected}, {max_expected}], got {similarity}"
            )
        else:
            pytest.skip(f"No expected values for corpus {actual_corpus}")

    @pytest.mark.slow
    @pytest.mark.parametrize("test_case", load_similarity_test_cases())
    def test_similarity_threshold_behavior_corpus_specific(self, test_case):
        """Test similarity threshold behavior with corpus-specific values."""
        matcher = TokenSimilarityMatcher()
        actual_corpus = detect_corpus_type(matcher)

        intent1 = test_case["intent1"]
        intent2 = test_case["intent2"]

        # Get expected range for actual corpus
        min_key = f"{actual_corpus}_min_similarity"
        max_key = f"{actual_corpus}_max_similarity"

        if min_key in test_case and max_key in test_case:
            max_expected = test_case[max_key]
            similarity = matcher.similarity(intent1, intent2)

            # Test threshold behavior
            if max_expected >= 0.8:
                assert similarity >= 0.8, (
                    "High similarity should match with 0.8 threshold"
                )
            elif max_expected >= 0.6:
                assert similarity >= 0.6, (
                    "Medium similarity should match with 0.6 threshold"
                )
            elif max_expected >= 0.4:
                assert similarity >= 0.4, (
                    "Low similarity should match with 0.4 threshold"
                )
            else:
                assert similarity < 0.4, (
                    "Very low similarity should not match with 0.4 threshold"
                )
        else:
            pytest.skip(f"No expected values for corpus {actual_corpus}")

    @pytest.mark.slow
    @pytest.mark.parametrize("test_case", load_similarity_test_cases())
    def test_antonym_detection_corpus_specific(self, test_case):
        """Test antonym detection with corpus-specific values."""
        matcher = TokenSimilarityMatcher()
        actual_corpus = detect_corpus_type(matcher)

        intent1 = test_case["intent1"]
        intent2 = test_case["intent2"]

        # Get expected range for actual corpus
        min_key = f"{actual_corpus}_min_similarity"
        max_key = f"{actual_corpus}_max_similarity"

        if min_key in test_case and max_key in test_case:
            similarity = matcher.similarity(intent1, intent2)

            # Test antonym behavior (low similarity for antonyms)
            if "delete" in intent2 and "create" in intent1:
                assert similarity <= 0.3, (
                    f"Antonyms should have low similarity, got {similarity}"
                )
            elif "remove" in intent2 and "add" in intent1:
                assert similarity <= 0.3, (
                    f"Antonyms should have low similarity, got {similarity}"
                )
        else:
            pytest.skip(f"No expected values for corpus {actual_corpus}")

    def test_real_world_similarity_scenarios(self):
        """Test similarity with real-world API scenarios."""
        matcher = TokenSimilarityMatcher()

        # API operation variations
        scenarios = [
            # Create operations
            ("create user", "add new user", 0.6),
            ("create product", "add product", 0.6),
            ("create order", "make order", 0.5),
            # Read operations
            ("get user", "fetch user", 0.5),
            ("list products", "show products", 0.5),
            ("retrieve data", "get data", 0.5),
            # Update operations
            ("update user", "modify user", 0.5),
            ("edit product", "change product", 0.5),
            ("modify order", "update order", 0.5),
            # Delete operations
            ("delete user", "remove user", 0.5),
            ("delete product", "remove product", 0.5),
            ("cancel order", "delete order", 0.4),
        ]

        for intent1, intent2, min_expected in scenarios:
            similarity = matcher.similarity(intent1, intent2)
            assert similarity >= min_expected, (
                f"'{intent1}' vs '{intent2}' expected >= {min_expected}, got {similarity}"
            )

    def test_corpus_consistency(self):
        """Test that similarity scores are consistent within the same corpus."""
        matcher = TokenSimilarityMatcher()

        # Test that the same inputs always give the same output
        test_pairs = [
            ("create product", "create a product"),
            ("get user", "fetch user"),
            ("delete order", "remove order"),
        ]

        for intent1, intent2 in test_pairs:
            # Run multiple times to ensure consistency
            similarities = []
            for _ in range(5):
                similarity = matcher.similarity(intent1, intent2)
                similarities.append(similarity)

            # All runs should give the same result
            assert len(set(similarities)) == 1, (
                f"Inconsistent similarity for '{intent1}' vs '{intent2}': {similarities}"
            )

    def test_corpus_performance_under_load(self):
        """Test corpus performance under realistic load."""
        matcher = TokenSimilarityMatcher()

        import time

        start_time = time.time()

        # Simulate realistic API operation variations
        operations = [
            "create user",
            "add user",
            "make user",
            "get user",
            "fetch user",
            "retrieve user",
            "update user",
            "modify user",
            "edit user",
            "delete user",
            "remove user",
            "drop user",
        ]

        # Calculate similarities for all pairs
        total_calculations = 0
        for i, op1 in enumerate(operations):
            for op2 in operations[i + 1 :]:
                matcher.similarity(op1, op2)
                total_calculations += 1

        end_time = time.time()
        elapsed = end_time - start_time

        # Should handle realistic load efficiently
        assert elapsed < 5.0, (
            f"Corpus similarity calculation took {elapsed}s for {total_calculations} calculations"
        )
        assert total_calculations > 0, "Should perform calculations"
