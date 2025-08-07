"""
Unit tests for PII masking utilities.

Tests cover email masking, name masking, IP address masking,
and other PII protection functions.
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.utils.pii_masking import (
    is_pii_field,
    mask_audit_metadata,
    mask_dict_pii,
    mask_email,
    mask_generic,
    mask_ip_address,
    mask_name,
    mask_phone,
    mask_pii,
    mask_user_id,
)


class TestPIIMasking:
    """Test cases for PII masking functions."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("nalai.utils.pii_masking.settings") as mock_settings:
            mock_settings.audit_mask_pii = True
            mock_settings.audit_mask_emails = True
            mock_settings.audit_mask_names = True
            mock_settings.audit_mask_ip_addresses = False
            yield mock_settings

    @pytest.mark.parametrize(
        "email,expected",
        [
            ("john.doe@example.com", "jo***@example.com"),
            ("jd@example.com", "***@example.com"),
            ("invalid-email", "***@***"),
            ("", ""),
            ("unknown", "unknown"),
            ("anonymous", "anonymous"),
        ],
    )
    def test_mask_email(self, mock_settings, email, expected):
        """Test email masking with various inputs."""
        result = mask_email(email)
        assert result == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("John", "J***"),
            ("John Smith", "J*** S***"),
            ("Jo", "***"),
            ("", "***"),
        ],
    )
    def test_mask_name(self, mock_settings, name, expected):
        """Test name masking with various inputs."""
        result = mask_name(name)
        assert result == expected

    @pytest.mark.parametrize(
        "ip_address,expected",
        [
            ("192.168.1.100", "192.168.1.***"),
            ("2001:db8::1", "****:****:****:****:****:****:****:****"),
        ],
    )
    def test_mask_ip_address_enabled(self, mock_settings, ip_address, expected):
        """Test IP address masking when enabled."""
        mock_settings.audit_mask_ip_addresses = True
        result = mask_ip_address(ip_address)
        assert result == expected

    @pytest.mark.parametrize(
        "ip_address",
        [
            "192.168.1.100",
            "2001:db8::1",
        ],
    )
    def test_mask_ip_address_disabled(self, mock_settings, ip_address):
        """Test IP address masking when disabled."""
        result = mask_ip_address(ip_address)
        assert result == ip_address

    @pytest.mark.parametrize(
        "phone,expected",
        [
            ("+1-555-123-4567", "555-123-***-4567"),
            ("555-1234", "555-***"),
            ("1234", "***"),
        ],
    )
    def test_mask_phone(self, mock_settings, phone, expected):
        """Test phone number masking."""
        result = mask_phone(phone)
        assert result == expected

    @pytest.mark.parametrize(
        "user_id,expected",
        [
            ("user-abc-123", "user-***-123"),
            ("user_abc_123", "user_***_123"),
            ("user123", "us***23"),
            ("abc", "***"),
        ],
    )
    def test_mask_user_id(self, mock_settings, user_id, expected):
        """Test user ID masking."""
        result = mask_user_id(user_id)
        assert result == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("testvalue", "te***e"),
            ("abc", "a***"),
            ("ab", "***"),
        ],
    )
    def test_mask_generic(self, mock_settings, value, expected):
        """Test generic masking."""
        result = mask_generic(value)
        assert result == expected

    @pytest.mark.parametrize(
        "value,pii_type,expected",
        [
            ("john.doe@example.com", "email", "jo***@example.com"),
            ("John Smith", "name", "J*** S***"),
            ("testvalue", "unknown", "te***e"),
            ("", "email", ""),
            ("unknown", "email", "unknown"),
            ("anonymous", "email", "anonymous"),
            (None, "email", "***"),
            (123, "email", "***"),
            ({"complex": "object"}, "email", "***"),
        ],
    )
    def test_mask_pii(self, mock_settings, value, pii_type, expected):
        """Test mask_pii with various types and values."""
        result = mask_pii(value, pii_type)
        assert result == expected

    @pytest.mark.parametrize(
        "pii_type,expected",
        [
            ("email", "jo***@example.com"),
            ("name", "J*** S***"),
            ("unknown", "te***e"),
        ],
    )
    def test_mask_pii_disabled(self, mock_settings, pii_type, expected):
        """Test mask_pii when globally disabled."""
        mock_settings.audit_mask_pii = False
        result = mask_pii(
            "john.doe@example.com"
            if pii_type == "email"
            else "John Smith"
            if pii_type == "name"
            else "testvalue",
            pii_type,
        )
        expected_unmasked = (
            "john.doe@example.com"
            if pii_type == "email"
            else "John Smith"
            if pii_type == "name"
            else "testvalue"
        )
        assert result == expected_unmasked

    @pytest.mark.parametrize(
        "data,pii_fields,expected_emails,expected_names",
        [
            (
                {
                    "email": "john.doe@example.com",
                    "name": "John Smith",
                    "user_id": "user-123",
                    "other_field": "not_pii",
                },
                None,
                "jo***@example.com",
                "J*** S***",
            ),
            (
                {"custom_email": "john.doe@example.com", "custom_name": "John Smith"},
                {"custom_email": "email", "custom_name": "name"},
                "jo***@example.com",
                "J*** S***",
            ),
        ],
    )
    def test_mask_dict_pii(
        self, mock_settings, data, pii_fields, expected_emails, expected_names
    ):
        """Test dictionary PII masking."""
        result = mask_dict_pii(data, pii_fields)

        if pii_fields:
            assert result["custom_email"] == expected_emails
            assert result["custom_name"] == expected_names
        else:
            assert result["email"] == expected_emails
            assert result["name"] == expected_names
            assert result["user_id"] == "user-***-123"
            assert result["other_field"] == "not_pii"

    @pytest.mark.parametrize(
        "metadata,expected_email,expected_given,expected_family",
        [
            (
                {
                    "user_email": "john.doe@example.com",
                    "given_name": "John",
                    "family_name": "Smith",
                    "ip_address": "192.168.1.100",
                    "session_id": "session-123",
                },
                "jo***@example.com",
                "J***",
                "S***",
            ),
        ],
    )
    def test_mask_audit_metadata(
        self, mock_settings, metadata, expected_email, expected_given, expected_family
    ):
        """Test audit metadata masking."""
        result = mask_audit_metadata(metadata)
        assert result["user_email"] == expected_email
        assert result["given_name"] == expected_given
        assert result["family_name"] == expected_family
        assert result["ip_address"] == "192.168.1.100"  # IP masking disabled by default
        assert result["session_id"] == "session-123"  # Not PII

    @pytest.mark.parametrize(
        "field_name,is_pii",
        [
            ("email", True),
            ("user_email", True),
            ("given_name", True),
            ("phone_number", True),
            ("credit_card", True),
            ("social_security", True),
            ("user_id", False),
            ("session_id", False),
            ("request_id", False),
            ("thread_id", False),
            ("status", False),
            ("timestamp", False),
        ],
    )
    def test_is_pii_field(self, field_name, is_pii):
        """Test PII field detection."""
        assert is_pii_field(field_name) is is_pii


class TestPIIMaskingIntegration:
    """Integration tests for PII masking."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for integration testing."""
        with patch("nalai.utils.pii_masking.settings") as mock_settings:
            mock_settings.audit_mask_pii = True
            mock_settings.audit_mask_emails = True
            mock_settings.audit_mask_names = True
            mock_settings.audit_mask_ip_addresses = True
            yield mock_settings

    @pytest.mark.parametrize(
        "audit_metadata,expected_masked",
        [
            (
                {
                    "user_email": "john.doe@company.com",
                    "given_name": "John",
                    "family_name": "Doe",
                    "ip_address": "192.168.1.100",
                    "phone": "+1-555-123-4567",
                    "user_id": "user-abc-123",
                    "session_id": "session-456",
                    "request_id": "req-789",
                },
                {
                    "user_email": "jo***@company.com",
                    "given_name": "J***",
                    "family_name": "D***",
                    "ip_address": "192.168.1.***",
                    "phone": "555-123-***-4567",
                    "user_id": "user-***-123",
                    "session_id": "session-456",
                    "request_id": "req-789",
                },
            ),
        ],
    )
    def test_complete_pii_masking_workflow(
        self, mock_settings, audit_metadata, expected_masked
    ):
        """Test complete PII masking workflow."""
        masked_metadata = mask_audit_metadata(audit_metadata)

        for key, expected_value in expected_masked.items():
            assert masked_metadata[key] == expected_value

    @pytest.mark.parametrize(
        "masking_config,test_value,pii_type,expected",
        [
            (
                {"audit_mask_pii": True, "audit_mask_emails": True},
                "john.doe@example.com",
                "email",
                "jo***@example.com",
            ),
            (
                {"audit_mask_pii": True, "audit_mask_names": True},
                "John Smith",
                "name",
                "J*** S***",
            ),
            (
                {"audit_mask_pii": True, "audit_mask_ip_addresses": True},
                "192.168.1.100",
                "ip_address",
                "192.168.1.***",
            ),
            (
                {"audit_mask_pii": True, "audit_mask_emails": False},
                "john.doe@example.com",
                "email",
                "john.doe@example.com",
            ),
            (
                {"audit_mask_pii": True, "audit_mask_names": False},
                "John Smith",
                "name",
                "John Smith",
            ),
            (
                {"audit_mask_pii": True, "audit_mask_ip_addresses": False},
                "192.168.1.100",
                "ip_address",
                "192.168.1.100",
            ),
            (
                {"audit_mask_pii": False},
                "john.doe@example.com",
                "email",
                "john.doe@example.com",
            ),
            ({"audit_mask_pii": False}, "John Smith", "name", "John Smith"),
            ({"audit_mask_pii": False}, "192.168.1.100", "ip_address", "192.168.1.100"),
        ],
    )
    def test_pii_masking_configuration_control(
        self, mock_settings, masking_config, test_value, pii_type, expected
    ):
        """Test that PII masking respects configuration settings."""
        # Apply configuration
        for key, value in masking_config.items():
            setattr(mock_settings, key, value)

        result = mask_pii(test_value, pii_type)
        assert result == expected
