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

from nalai.server.models.identity import IdentityContext, UserContext
from nalai.server.runtime_config import (
    _ensure_config_dict,
    _ensure_configurable,
    add_auth_token_to_config,
    add_user_context_to_config,
    default_modify_runtime_config,
    default_modify_runtime_config_with_access_control,
    default_validate_runtime_config,
    ensure_thread_id_exists,
    setup_runtime_config_with_access_control,
    validate_thread_access_and_scope,
)


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


class TestEnsureThreadIdExists:
    """Test thread ID existence and generation."""

    @pytest.mark.parametrize(
        "input_config,expected_thread_id_exists",
        [
            ({"configurable": {"thread_id": "existing-thread-123"}}, True),
            ({"configurable": {}}, False),
            (None, False),
        ],
    )
    def test_ensure_thread_id_exists(self, input_config, expected_thread_id_exists):
        """Test thread ID existence and generation."""
        result_config, thread_id = ensure_thread_id_exists(input_config)

        if expected_thread_id_exists:
            assert thread_id == "existing-thread-123"
            assert result_config["configurable"]["thread_id"] == "existing-thread-123"
        else:
            assert thread_id is not None
            assert len(thread_id) > 0
            assert result_config["configurable"]["thread_id"] == thread_id

    @pytest.mark.parametrize(
        "thread_id,should_raise",
        [
            ("123e4567-e89b-12d3-a456-426614174000", False),
            ("invalid-uuid", True),
        ],
    )
    def test_ensure_thread_id_exists_validate_uuid(self, thread_id, should_raise):
        """Test UUID validation."""
        config = {"configurable": {"thread_id": thread_id}}

        if should_raise:
            with pytest.raises(HTTPException) as exc_info:
                ensure_thread_id_exists(config, validate_uuid=True)
            assert exc_info.value.status_code == 400
            assert "Invalid thread_id format" in str(exc_info.value.detail)
        else:
            result_config, result_thread_id = ensure_thread_id_exists(
                config, validate_uuid=True
            )
            assert result_thread_id == thread_id


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
                    "user_id": "unknown",
                    "user_email": "unknown@example.com",
                    "org_unit_id": "unknown",
                    "user_roles": [],
                    "user_permissions": [],
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
            (True, True, "user:test-user-123:thread-456", False),
            (True, False, None, True),
            (False, True, "user:test-user-123:new-thread-789", False),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.server.runtime_config.get_thread_access_control")
    @patch("nalai.server.runtime_config.log_thread_access_event")
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
        mock_access_control.create_user_scoped_thread_id.return_value = (
            expected_scoped_id
        )
        mock_access_control.create_thread.return_value = None
        mock_get_access_control.return_value = mock_access_control

        config = {"configurable": {"thread_id": "thread-456"}} if has_thread_id else {}

        if should_raise:
            with pytest.raises(HTTPException) as exc_info:
                await validate_thread_access_and_scope(config, mock_request)
            assert exc_info.value.status_code == 403
            assert "Access denied to thread" in str(exc_info.value.detail)
        else:
            (
                result_config,
                user_scoped_thread_id,
            ) = await validate_thread_access_and_scope(config, mock_request)
            assert user_scoped_thread_id == expected_scoped_id
            assert result_config["configurable"]["thread_id"] == expected_scoped_id

    @patch("nalai.server.runtime_config.get_user_context")
    @pytest.mark.asyncio
    async def test_validate_thread_access_no_user_context(
        self, mock_get_user_context, mock_request
    ):
        """Test validation without user context."""
        mock_get_user_context.side_effect = Exception("User context not found")

        with pytest.raises(HTTPException) as exc_info:
            await validate_thread_access_and_scope({}, mock_request)

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
    def test_default_modify_runtime_config(
        self, mock_add_user_context, mock_add_auth_token, mock_request
    ):
        """Test default runtime configuration modification."""
        mock_add_auth_token.return_value = {
            "configurable": {"auth_token": "test-token"}
        }
        mock_add_user_context.return_value = {"configurable": {"user_id": "test-user"}}

        default_modify_runtime_config({}, mock_request)

        mock_add_auth_token.assert_called_once_with({}, mock_request)
        mock_add_user_context.assert_called_once()

    @patch("nalai.server.runtime_config.validate_runtime_config")
    def test_default_validate_runtime_config(self, mock_validate):
        """Test default runtime configuration validation."""
        mock_validate.return_value = MagicMock()
        config = {"configurable": {"key": "value"}}

        result = default_validate_runtime_config(config)

        mock_validate.assert_called_once_with(config)
        assert result == mock_validate.return_value

    @patch("nalai.server.runtime_config.default_modify_runtime_config")
    @patch("nalai.server.runtime_config.validate_thread_access_and_scope")
    @pytest.mark.asyncio
    async def test_default_modify_runtime_config_with_access_control(
        self, mock_validate_access, mock_modify_config, mock_request
    ):
        """Test default runtime configuration with access control."""
        mock_modify_config.return_value = {"configurable": {"key": "value"}}
        mock_validate_access.return_value = (
            {"configurable": {"thread_id": "scoped-id"}},
            "scoped-id",
        )

        (
            result_config,
            thread_id,
        ) = await default_modify_runtime_config_with_access_control({}, mock_request)

        mock_modify_config.assert_called_once_with({}, mock_request)
        mock_validate_access.assert_called_once()
        assert thread_id == "scoped-id"

    @patch("nalai.server.runtime_config.validate_runtime_config")
    @pytest.mark.asyncio
    async def test_setup_runtime_config_with_access_control(self, mock_validate):
        """Test setup runtime configuration with access control."""
        mock_validate.return_value = MagicMock()

        async def mock_modify_config(config, req):
            return {"configurable": {"thread_id": "scoped-id"}}, "scoped-id"

        result_config, thread_id = await setup_runtime_config_with_access_control(
            {}, MagicMock(), mock_modify_config, mock_validate
        )

        mock_validate.assert_called_once()
        assert thread_id == "scoped-id"
