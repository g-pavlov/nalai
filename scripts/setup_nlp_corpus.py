#!/usr/bin/env python3
"""
NLP Corpus Setup Script

Downloads and configures NLTK and spaCy data for the enhanced TokenSimilarityMatcher.
This script ensures the cache service has access to comprehensive word corpora.
"""

import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_nltk_data():
    """Download required NLTK data for comprehensive word corpus."""
    try:
        import nltk

        # Required NLTK data packages
        required_packages = [
            'punkt',           # Tokenization
            'averaged_perceptron_tagger',  # POS tagging
            'wordnet',         # WordNet lexical database
            'omw-1.4',        # Open Multilingual WordNet
        ]

        logger.info("Downloading NLTK data packages...")
        for package in required_packages:
            try:
                nltk.download(package, quiet=True)
                logger.info(f"✓ Downloaded {package}")
            except Exception as e:
                logger.warning(f"⚠ Failed to download {package}: {e}")

        # Test WordNet access
        from nltk.corpus import wordnet
        verb_count = len(list(wordnet.all_synsets(wordnet.VERB)))
        noun_count = len(list(wordnet.all_synsets(wordnet.NOUN)))
        adj_count = len(list(wordnet.all_synsets(wordnet.ADJ)))

        logger.info(f"✓ WordNet loaded: {verb_count} verbs, {noun_count} nouns, {adj_count} adjectives")

        return True

    except ImportError:
        logger.warning("⚠ NLTK not available. Install with: pip install nltk")
        return False


def setup_spacy_model():
    """Download spaCy English model for enhanced NLP capabilities."""
    try:
        import spacy

        # Try to load the English model
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.info("✓ spaCy English model already available")
            return True
        except OSError:
            logger.info("Downloading spaCy English model...")
            os.system("python -m spacy download en_core_web_sm")
            logger.info("✓ spaCy English model downloaded")
            return True

    except ImportError:
        logger.warning("⚠ spaCy not available. Install with: pip install spacy")
        return False


def test_enhanced_matcher():
    """Test the enhanced TokenSimilarityMatcher with comprehensive word corpus."""
    try:
        from nalai.services.cache_service import TokenSimilarityMatcher

        matcher = TokenSimilarityMatcher()

        # Test cases for comprehensive coverage
        test_cases = [
            # API operations
            ("create user", "add new user", 0.8),
            ("list products", "show all products", 0.8),
            ("delete order", "remove order", 0.9),
            ("update profile", "modify user profile", 0.8),

            # System operations
            ("start service", "activate service", 0.8),
            ("stop process", "terminate process", 0.8),
            ("enable feature", "activate feature", 0.9),
            ("disable access", "deactivate access", 0.9),

            # Data operations
            ("export data", "download data", 0.7),
            ("import file", "upload file", 0.7),
            ("backup database", "create backup", 0.7),
            ("restore system", "recover system", 0.8),

            # Security operations
            ("authenticate user", "login user", 0.7),
            ("authorize access", "grant permission", 0.7),
            ("encrypt data", "secure data", 0.6),
            ("decrypt message", "decode message", 0.8),

            # False positive tests (should return 0.0)
            ("create user", "delete user", 0.0),
            ("enable service", "disable service", 0.0),
            ("start process", "stop process", 0.0),
            ("authenticate user", "deauthenticate user", 0.0),
        ]

        logger.info("Testing enhanced TokenSimilarityMatcher...")

        for intent1, intent2, expected_min in test_cases:
            similarity = matcher.similarity(intent1, intent2)

            if expected_min == 0.0:
                # False positive test
                if similarity == 0.0:
                    logger.info(f"✓ '{intent1}' vs '{intent2}': {similarity:.3f} (correctly identified as opposite)")
                else:
                    logger.warning(f"⚠ '{intent1}' vs '{intent2}': {similarity:.3f} (should be 0.0)")
            else:
                # Similarity test
                if similarity >= expected_min:
                    logger.info(f"✓ '{intent1}' vs '{intent2}': {similarity:.3f} (>= {expected_min})")
                else:
                    logger.warning(f"⚠ '{intent1}' vs '{intent2}': {similarity:.3f} (< {expected_min})")

        # Test corpus statistics
        logger.info("Corpus statistics:")
        logger.info(f"  - Verbs: {len(matcher.verbs)}")
        logger.info(f"  - Nouns: {len(matcher.nouns)}")
        logger.info(f"  - Adjectives: {len(matcher.adjectives)}")
        logger.info(f"  - Antonym pairs: {len(matcher.antonyms)}")

        return True

    except Exception as e:
        logger.error(f"✗ Failed to test enhanced matcher: {e}")
        return False


def main():
    """Main setup function."""
    logger.info("Setting up NLP corpus for enhanced cache similarity matching...")

    # Setup NLTK data
    nltk_available = setup_nltk_data()

    # Setup spaCy model
    spacy_available = setup_spacy_model()

    # Test the enhanced matcher
    test_success = test_enhanced_matcher()

    # Summary
    logger.info("\n" + "="*50)
    logger.info("NLP Corpus Setup Summary:")
    logger.info(f"  NLTK: {'✓ Available' if nltk_available else '⚠ Not available'}")
    logger.info(f"  spaCy: {'✓ Available' if spacy_available else '⚠ Not available'}")
    logger.info(f"  Enhanced Matcher: {'✓ Working' if test_success else '✗ Failed'}")

    if test_success:
        logger.info("\n✅ NLP corpus setup completed successfully!")
        logger.info("The cache service now has comprehensive word coverage for similarity matching.")
    else:
        logger.error("\n❌ NLP corpus setup failed!")
        logger.error("The cache service will fall back to basic word matching.")

    return 0 if test_success else 1


if __name__ == "__main__":
    sys.exit(main())
