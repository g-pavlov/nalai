"""Tests for ID generator utilities."""

from src.nalai.utils.id_generator import (
    generate_conversation_id,
    generate_domain_id,
    validate_domain_id_format,
)


class TestIDGenerator:
    """Test ID generation and validation."""

    def test_generate_conversation_id(self):
        """Test conversation ID generation."""
        conv_id = generate_conversation_id()

        # Should start with conv_
        assert conv_id.startswith("conv_")

        # Should be 27 characters total (conv_ + 22 chars = 27)
        assert len(conv_id) == 27

        # Should be valid format
        assert validate_domain_id_format(conv_id, "conv")

    def test_generate_domain_id(self):
        """Test domain ID generation with different domains."""
        domains = ["conv", "run", "msg", "tool", "resp", "task", "stream"]

        for domain in domains:
            domain_id = generate_domain_id(domain)

            # Should start with correct prefix
            assert domain_id.startswith(f"{domain}_")

            # Should be domain_ + 20-22 characters total (base62 encoding can vary)
            base62_part = domain_id.split("_", 1)[1]
            assert 20 <= len(base62_part) <= 22  # Base62 part should be 20-22 chars

            # Should be valid format
            assert validate_domain_id_format(domain_id, domain)

    def test_validate_domain_id_format_valid(self):
        """Test validation of valid domain IDs."""
        valid_ids = [
            "conv_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9",
            "run_abc123def456ghi789jkm2n3p4q5r6s7t8u9",
            "msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ",
            "tool_abcdefghijkmnopqrstuvwxyz123456789",
            "resp_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9",
        ]

        for id_str in valid_ids:
            assert validate_domain_id_format(id_str)

            # Test with specific domain
            domain = id_str.split("_")[0]
            assert validate_domain_id_format(id_str, domain)

    def test_validate_domain_id_format_invalid(self):
        """Test validation of invalid domain IDs."""
        invalid_ids = [
            "",  # Empty
            "conv",  # No underscore
            "conv_",  # No base62 part
            "conv_123",  # Too short
            "conv_123456789012345678901234567890",  # Too long
            "conv_1234567890O",  # Contains O (confusing character)
            "conv_1234567890l",  # Contains l (confusing character)
            "conv_12345678900",  # Contains 0 (confusing character)
            "conv_1234567890I",  # Contains I (confusing character)
        ]

        for id_str in invalid_ids:
            assert not validate_domain_id_format(id_str)

    def test_validate_domain_id_format_wrong_domain(self):
        """Test validation with wrong domain prefix."""
        id_str = "conv_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"

        # Should be valid for conv domain
        assert validate_domain_id_format(id_str, "conv")

        # Should be invalid for other domains
        assert not validate_domain_id_format(id_str, "run")
        assert not validate_domain_id_format(id_str, "msg")

    def test_id_uniqueness(self):
        """Test that generated IDs are unique."""
        ids = set()

        # Generate 1000 IDs and check for uniqueness
        for _ in range(1000):
            conv_id = generate_conversation_id()
            assert conv_id not in ids
            ids.add(conv_id)

    def test_id_length_consistency(self):
        """Test that IDs have consistent length."""
        conv_ids = [generate_conversation_id() for _ in range(100)]

        # Should be either 25, 26, or 27 characters (base62 encoding can vary)
        lengths = [len(conv_id) for conv_id in conv_ids]
        unique_lengths = set(lengths)
        assert len(unique_lengths) <= 3  # At most 3 different lengths
        assert all(
            length in [25, 26, 27] for length in unique_lengths
        )  # Only 25, 26, or 27 chars

        # All should be valid format
        for conv_id in conv_ids:
            assert validate_domain_id_format(conv_id, "conv")
