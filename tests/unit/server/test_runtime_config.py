"""
Unit tests for runtime configuration utilities.

Tests cover thread ID management, configuration modification,
access control integration, and validation functions.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.server.runtime_config import (
    _ensure_config_dict,
    _ensure_configurable,
    add_auth_token_to_config,
    add_user_context_to_config,
    create_runtime_config,
)
from nalai.services.auth_service import IdentityContext, UserContext
from nalai.services.thread_access_control import (
    validate_conversation_access_and_scope,
)
from nalai.utils.validation import validate_thread_id_format


class TestConfigHelpers:
    """Test helper functions for configuration management."""

    @pytest.mark.parametrize(
        "input_config,expected",
        [
            ({"key": "value"}, {"key": "value"}),
            (None, {}),
        ],
    )
    def test_ensure_config_dict(self, input_config, expected):
        """Test _ensure_config_dict with various inputs."""
        result = _ensure_config_dict(input_config)
        assert result == expected

    def test_ensure_config_dict_with_pydantic_model(self):
        """Test _ensure_config_dict with Pydantic model."""
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"key": "value"}

        result = _ensure_config_dict(mock_model)
        assert result == {"key": "value"}
        mock_model.model_dump.assert_called_once()

    @pytest.mark.parametrize(
        "input_config,expected_configurable,expected_result",
        [
            ({"configurable": {"key": "value"}}, {"key": "value"}, {"key": "value"}),
            ({"configurable": None}, {}, {}),
            ({}, {}, {}),
        ],
    )
    def test_ensure_configurable(
        self, input_config, expected_configurable, expected_result
    ):
        """Test _ensure_configurable with various inputs."""
        result = _ensure_configurable(input_config)
        assert result == expected_result
        assert input_config["configurable"] == expected_configurable


class TestAddAuthTokenToConfig:
    """Test authentication token addition to configuration."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = MagicMock(spec=Request)
        request.headers = {}
        return request

    @pytest.mark.parametrize(
        "auth_disabled,headers,expected_token,should_raise",
        [
            (True, {}, "dev-token", False),
            (
                False,
                {"Authorization": "Bearer test-token-123"},
                "test-token-123",
                False,
            ),
            (False, {}, None, True),
            (False, {"Authorization": ""}, None, True),
        ],
    )
    @patch("nalai.server.runtime_config.settings")
    def test_add_auth_token_to_config(
        self,
        mock_settings,
        mock_request,
        auth_disabled,
        headers,
        expected_token,
        should_raise,
    ):
        """Test authentication token addition with various scenarios."""
        mock_settings.auth_enabled = not auth_disabled
        mock_request.headers = headers

        if should_raise:
            with pytest.raises(HTTPException) as exc_info:
                add_auth_token_to_config({}, mock_request)
            assert exc_info.value.status_code == 401
        else:
            result = add_auth_token_to_config({}, mock_request)
            assert result["configurable"]["auth_token"] == expected_token


class TestAddUserContextToConfig:
    """Test user context addition to configuration."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = MagicMock(spec=Request)
        return request

    @pytest.mark.parametrize(
        "user_context_success,expected_values",
        [
            (
                True,
                {
                    "user_id": "test-user-123",
                    "user_email": "test@example.com",
                    "org_unit_id": "test-org",
                    "user_roles": ["user"],
                    "user_permissions": ["read"],
                },
            ),
            (
                False,
                {
                    "user_id": "dev-user",
                    "user_email": "dev@example.com",
                    "org_unit_id": "dev-org",
                    "user_roles": ["developer"],
                    "user_permissions": ["read", "write"],
                },
            ),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    def test_add_user_context_to_config(
        self, mock_get_user_context, mock_request, user_context_success, expected_values
    ):
        """Test user context addition with success/failure scenarios."""
        if user_context_success:
            mock_identity = IdentityContext(
                user_id="test-user-123",
                email="test@example.com",
                org_unit_id="test-org",
                roles=["user"],
                permissions=["read"],
                token_type="access_token",
            )
            mock_user_context = UserContext(
                identity=mock_identity,
                session_id="session-123",
                request_id="request-456",
                ip_address="127.0.0.1",
                user_agent="test-agent",
            )
            mock_get_user_context.return_value = mock_user_context
        else:
            mock_get_user_context.side_effect = Exception("User context not found")

        result = add_user_context_to_config({}, mock_request)

        for key, expected_value in expected_values.items():
            assert result["configurable"][key] == expected_value


class TestValidateThreadAccessAndScope:
    """Test thread access validation and scoping."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = MagicMock(spec=Request)
        return request

    @pytest.fixture
    def mock_user_context(self):
        """Create a mock user context."""
        mock_identity = IdentityContext(
            user_id="test-user-123",
            email="test@example.com",
            org_unit_id="test-org",
            roles=["user"],
            permissions=["read"],
            token_type="access_token",
        )
        return UserContext(
            identity=mock_identity,
            session_id="session-123",
            request_id="request-456",
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )

    @pytest.mark.parametrize(
        "has_thread_id,access_granted,expected_scoped_id,should_raise",
        [
            (
                True,
                True,
                "user:test-user-123:550e8400-e29b-41d4-a716-446655440000",
                False,
            ),
            (True, False, None, True),
            (
                False,
                True,
                None,  # Will be generated dynamically
                False,
            ),
        ],
    )
    @patch("nalai.services.thread_access_control.get_user_context")
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    @patch("nalai.services.audit_utils.log_thread_access_event")
    @pytest.mark.asyncio
    async def test_validate_thread_access_and_scope(
        self,
        mock_log_event,
        mock_get_access_control,
        mock_get_user_context,
        mock_request,
        mock_user_context,
        has_thread_id,
        access_granted,
        expected_scoped_id,
        should_raise,
    ):
        """Test thread access validation with various scenarios."""
        mock_get_user_context.return_value = mock_user_context
        mock_access_control = AsyncMock()
        mock_access_control.validate_thread_access.return_value = access_granted

        # Mock create_thread to raise ValueError when access is denied
        if has_thread_id and not access_granted:
            mock_access_control.create_thread.side_effect = ValueError(
                "Thread belongs to different user"
            )
        else:
            mock_access_control.create_thread.return_value = None

        mock_get_access_control.return_value = mock_access_control

        config = (
            {"configurable": {"thread_id": "550e8400-e29b-41d4-a716-446655440000"}}
            if has_thread_id
            else {}
        )

        if should_raise:
            with pytest.raises(HTTPException) as exc_info:
                await validate_conversation_access_and_scope(config, mock_request)
            assert exc_info.value.status_code == 403
            assert "Access denied to conversation" in str(exc_info.value.detail)
        else:
            (
                result_config,
                user_scoped_thread_id,
            ) = await validate_conversation_access_and_scope(config, mock_request)

            if expected_scoped_id is not None:
                # For cases with specific expected UUID
                assert user_scoped_thread_id == expected_scoped_id
                assert result_config["configurable"]["thread_id"] == expected_scoped_id
            else:
                # For cases where UUID is generated dynamically
                assert user_scoped_thread_id.startswith("user:test-user-123:")
                assert (
                    result_config["configurable"]["thread_id"] == user_scoped_thread_id
                )
                # Verify it's a valid UUID format
                import uuid

                uuid_part = user_scoped_thread_id.split(":", 2)[2]
                uuid.UUID(uuid_part, version=4)  # Should not raise

    @patch("nalai.services.thread_access_control.get_user_context")
    @pytest.mark.asyncio
    async def test_validate_thread_access_no_user_context(
        self, mock_get_user_context, mock_request
    ):
        """Test validation without user context."""
        mock_get_user_context.side_effect = Exception("User context not found")

        with pytest.raises(HTTPException) as exc_info:
            await validate_conversation_access_and_scope({}, mock_request)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)


class TestDefaultFunctions:
    """Test default configuration functions."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer test-token"}
        return request

    @patch("nalai.server.runtime_config.add_auth_token_to_config")
    @patch("nalai.server.runtime_config.add_user_context_to_config")
    @patch("nalai.server.runtime_config.add_no_cache_header_to_config")
    @patch("nalai.server.runtime_config.validate_runtime_config")
    def test_create_runtime_config(
        self,
        mock_validate,
        mock_add_no_cache,
        mock_add_user_context,
        mock_add_auth_token,
        mock_request,
    ):
        """Test runtime configuration creation."""
        mock_add_auth_token.return_value = {
            "configurable": {"auth_token": "test-token"}
        }
        mock_add_user_context.return_value = {"configurable": {"user_id": "test-user"}}
        mock_add_no_cache.return_value = {"configurable": {"cache_disabled": False}}
        mock_validate.return_value = None

        result = create_runtime_config(mock_request)

        mock_add_auth_token.assert_called_once()
        mock_add_user_context.assert_called_once()
        mock_add_no_cache.assert_called_once()
        mock_validate.assert_called_once()
        assert "configurable" in result


class TestThreadIdValidation:
    """Test thread ID validation for external inputs."""

    @pytest.mark.parametrize(
        "thread_id,should_be_valid",
        [
            # Critical path: Valid UUID4 formats
            ("550e8400-e29b-41d4-a716-446655440001", True),
            # Critical path: Invalid formats
            ("", False),
            ("not-a-uuid", False),
        ],
    )
    def test_thread_access_control_validation(self, thread_id, should_be_valid):
        """Test thread access control thread ID validation."""
        if should_be_valid:
            # Should not raise any exception
            validate_thread_id_format(thread_id)
        else:
            # Should raise ValueError
            with pytest.raises(ValueError):
                validate_thread_id_format(thread_id)

    def test_canonical_uuid_requirement(self):
        """Test that UUIDs must be in canonical format."""
        # Non-canonical formats should be rejected
        non_canonical_uuids = [
            "550E8400-E29B-41D4-A716-446655440001",  # Uppercase
            "{550e8400-e29b-41d4-a716-446655440001}",  # With braces
        ]

        for uuid_str in non_canonical_uuids:
            with pytest.raises(ValueError) as exc_info:
                validate_thread_id_format(uuid_str)
            assert "UUID4" in str(exc_info.value)

    def test_thread_id_length_limits(self):
        """Test thread ID length limits for security."""
        # Test maximum length limit
        too_long_thread_id = "a" * 201
        with pytest.raises(ValueError) as exc_info:
            validate_thread_id_format(too_long_thread_id)
        assert "too long" in str(exc_info.value)
