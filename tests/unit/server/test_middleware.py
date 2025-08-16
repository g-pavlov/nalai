"""
Unit tests for server middleware.

Tests cover request processing, authentication, audit logging,
and user context middleware with proper error handling.
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

from nalai.server.middleware import (
    create_audit_middleware,
    create_auth_middleware,
    create_log_request_middleware,
    create_user_context_middleware,
    extract_user_context,
    get_user_context,
    is_request_processable,
)
from nalai.services.auth_service import IdentityContext, UserContext


class TestRequestProcessing:
    """Test request processing utilities."""

    @pytest.mark.parametrize(
        "path,excluded_paths,expected",
        [
            ("/api/agent", set(), True),
            ("/api/agent", {"/health"}, True),
            ("/health", {"/health"}, False),
            ("/docs", {"/docs", "/redoc"}, False),
            ("/api/agent", {"/docs", "/redoc"}, True),
            ("/", set(), True),
            ("/", {"/"}, False),
        ],
    )
    def test_is_request_processable(self, path, excluded_paths, expected):
        """Test request processing decision logic."""
        request = MagicMock(spec=Request)
        request.url.path = path

        result = is_request_processable(request, excluded_paths)
        assert result == expected

    def test_is_request_processable_default_excluded(self):
        """Test request processing with default excluded paths."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/agent"

        result = is_request_processable(request)
        assert result


class TestLogRequestMiddleware:
    """Test request logging middleware."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/agent"
        request.client.host = "127.0.0.1"
        request.headers = {}
        request.state = MagicMock()
        # Mock user_context to avoid JSON serialization issues
        request.state.user_context = None
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.status_code = 200
        return response

    @pytest.mark.parametrize(
        "path,excluded_paths,should_log",
        [
            ("/api/agent", set(), True),
            ("/health", {"/health"}, False),
            ("/docs", {"/docs"}, False),
            ("/api/agent", {"/health"}, True),
        ],
    )
    @pytest.mark.asyncio
    async def test_log_request_middleware(
        self, mock_request, mock_response, path, excluded_paths, should_log
    ):
        """Test request logging middleware with various paths."""
        mock_request.url.path = path

        call_next = AsyncMock(return_value=mock_response)
        middleware = create_log_request_middleware(excluded_paths)

        with patch("nalai.server.middleware.logger") as mock_logger:
            result = await middleware(mock_request, call_next)

            assert result == mock_response
            call_next.assert_called_once_with(mock_request)

            if should_log:
                assert mock_logger.info.call_count == 2  # Request and response
            else:
                assert mock_logger.info.call_count == 0

    @pytest.mark.asyncio
    async def test_log_request_middleware_no_client(self, mock_response):
        """Test logging middleware when client is None."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/agent"
        request.client = None
        request.headers = {}
        request.state = MagicMock()
        # Mock user_context to avoid JSON serialization issues
        request.state.user_context = None

        call_next = AsyncMock(return_value=mock_response)
        middleware = create_log_request_middleware()

        with patch("nalai.server.middleware.logger") as mock_logger:
            result = await middleware(request, call_next)

            assert result == mock_response
            # Should still log even without client info
            assert mock_logger.info.call_count == 2


class TestAuthMiddleware:
    """Test authentication middleware."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/agent"
        request.state = MagicMock()
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.status_code = 200
        return response

    @pytest.mark.parametrize(
        "path,excluded_paths,should_auth",
        [
            ("/api/agent", set(), True),
            ("/health", {"/health"}, False),
            ("/docs", {"/docs"}, False),
            ("/api/agent", {"/health"}, True),
        ],
    )
    @pytest.mark.asyncio
    async def test_auth_middleware_success(
        self, mock_request, mock_response, path, excluded_paths, should_auth
    ):
        """Test authentication middleware with successful auth."""
        mock_request.url.path = path

        mock_identity = IdentityContext(
            user_id="test-user-123", email="test@example.com", token_type="access_token"
        )

        call_next = AsyncMock(return_value=mock_response)
        middleware = create_auth_middleware(excluded_paths)

        with patch("nalai.services.auth_service.get_auth_service") as mock_get_auth:
            mock_auth_service = AsyncMock()
            mock_auth_service.authenticate_request.return_value = mock_identity
            mock_get_auth.return_value = mock_auth_service

            with patch("nalai.server.middleware.logger") as mock_logger:
                result = await middleware(mock_request, call_next)

                assert result == mock_response
                call_next.assert_called_once_with(mock_request)

                if should_auth:
                    mock_auth_service.authenticate_request.assert_called_once_with(
                        mock_request
                    )
                    assert mock_request.state.identity == mock_identity
                    mock_logger.debug.assert_called_once()
                else:
                    mock_auth_service.authenticate_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_middleware_failure(self, mock_request, mock_response):
        """Test authentication middleware with auth failure."""
        call_next = AsyncMock(return_value=mock_response)
        middleware = create_auth_middleware()

        with patch("nalai.services.auth_service.get_auth_service") as mock_get_auth:
            mock_auth_service = AsyncMock()
            mock_auth_service.authenticate_request.side_effect = Exception(
                "Auth failed"
            )
            mock_get_auth.return_value = mock_auth_service

            with patch("nalai.server.middleware.logger") as mock_logger:
                with pytest.raises(HTTPException) as exc_info:
                    await middleware(mock_request, call_next)

                assert exc_info.value.status_code == 401
                assert "Authentication required" in str(exc_info.value.detail)
                mock_logger.warning.assert_called_once()


class TestAuditMiddleware:
    """Test audit logging middleware."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/agent"
        request.client.host = "127.0.0.1"
        request.headers = {
            "User-Agent": "test-agent",
            "X-Session-ID": "session-123",
            "X-Request-ID": "request-456",
        }
        request.state = MagicMock()
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.status_code = 200
        return response

    @pytest.mark.parametrize(
        "path,excluded_paths,user_context,should_audit",
        [
            ("/api/agent", set(), None, True),
            ("/health", {"/health"}, None, False),
            ("/api/agent", set(), MagicMock(user_id="test-user"), True),
            ("/docs", {"/docs"}, MagicMock(user_id="test-user"), False),
        ],
    )
    @pytest.mark.asyncio
    async def test_audit_middleware(
        self,
        mock_request,
        mock_response,
        path,
        excluded_paths,
        user_context,
        should_audit,
    ):
        """Test audit middleware with various scenarios."""
        mock_request.url.path = path
        if user_context:
            mock_request.state.user_context = user_context

        call_next = AsyncMock(return_value=mock_response)
        middleware = create_audit_middleware(excluded_paths)

        with patch("nalai.services.audit_service.get_audit_service") as mock_get_audit:
            mock_audit_service = AsyncMock()
            mock_get_audit.return_value = mock_audit_service

            with patch("nalai.server.middleware.logger") as _mock_logger:  # noqa: F841
                result = await middleware(mock_request, call_next)

                assert result == mock_response
                call_next.assert_called_once_with(mock_request)

                if should_audit:
                    assert mock_audit_service.log_request_start.call_count == 1
                    assert mock_audit_service.log_request_complete.call_count == 1
                else:
                    mock_audit_service.log_request_start.assert_not_called()
                    mock_audit_service.log_request_complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_middleware_error_handling(self, mock_request, mock_response):
        """Test audit middleware error handling."""
        call_next = AsyncMock(return_value=mock_response)
        middleware = create_audit_middleware()

        with patch("nalai.services.audit_service.get_audit_service") as mock_get_audit:
            mock_audit_service = AsyncMock()
            mock_audit_service.log_request_start.side_effect = Exception("Audit failed")
            mock_get_audit.return_value = mock_audit_service

            with patch("nalai.server.middleware.logger") as _mock_logger:  # noqa: F841
                result = await middleware(mock_request, call_next)

                # Should still process request even if audit fails
                assert result == mock_response
                _mock_logger.error.assert_called()


class TestUserContextMiddleware:
    """Test user context middleware."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/agent"
        request.client.host = "127.0.0.1"
        request.headers = {
            "X-Session-ID": "session-123",
            "X-Request-ID": "request-456",
            "User-Agent": "test-agent",
        }
        request.state = MagicMock()
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.status_code = 200
        return response

    @pytest.mark.parametrize(
        "path,excluded_paths,has_identity,context_key",
        [
            ("/api/agent", set(), True, "user_context"),
            ("/health", {"/health"}, True, "user_context"),
            ("/api/agent", set(), False, "user_context"),
            ("/api/agent", set(), True, "custom_context"),
        ],
    )
    @pytest.mark.asyncio
    async def test_user_context_middleware(
        self,
        mock_request,
        mock_response,
        path,
        excluded_paths,
        has_identity,
        context_key,
    ):
        """Test user context middleware with various scenarios."""
        mock_request.url.path = path

        call_next = AsyncMock(return_value=mock_response)
        middleware = create_user_context_middleware(excluded_paths, context_key)

        if has_identity:
            mock_identity = IdentityContext(
                user_id="test-user-123",
                email="test@example.com",
                token_type="access_token",
            )
            mock_request.state.identity = mock_identity
        else:
            mock_request.state.identity = None

        with patch("nalai.server.middleware.extract_user_context") as mock_extract:
            mock_user_context = MagicMock(spec=UserContext)
            mock_extract.return_value = mock_user_context

            with patch("nalai.server.middleware.logger") as _mock_logger:  # noqa: F841
                result = await middleware(mock_request, call_next)

                assert result == mock_response
                call_next.assert_called_once_with(mock_request)

                if path not in excluded_paths:
                    if has_identity:
                        # Should create context from identity, not call extract
                        mock_extract.assert_not_called()
                        assert hasattr(mock_request.state, context_key)
                    else:
                        # Should call extract when no identity
                        mock_extract.assert_called_once_with(mock_request)
                        assert hasattr(mock_request.state, context_key)

    @pytest.mark.asyncio
    async def test_user_context_middleware_error_handling(
        self, mock_request, mock_response
    ):
        """Test user context middleware error handling."""
        call_next = AsyncMock(return_value=mock_response)
        middleware = create_user_context_middleware()

        # Simulate error in context extraction
        mock_request.state.identity = None

        with patch("nalai.server.middleware.extract_user_context") as mock_extract:
            mock_extract.side_effect = Exception("Context extraction failed")

            with patch("nalai.server.middleware.logger") as _mock_logger:  # noqa: F841
                result = await middleware(mock_request, call_next)

                # Should still process request even if context extraction fails
                assert result == mock_response
                assert mock_request.state.user_context is None
                _mock_logger.warning.assert_called_once()


class TestUserContextUtilities:
    """Test user context utility functions."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        return request

    @pytest.mark.parametrize(
        "context_key,has_context",
        [
            ("user_context", True),
            ("user_context", False),
            ("custom_context", True),
            ("custom_context", False),
        ],
    )
    def test_get_user_context(self, mock_request, context_key, has_context):
        """Test getting user context from request state."""
        if has_context:
            mock_user_context = MagicMock(spec=UserContext)
            setattr(mock_request.state, context_key, mock_user_context)
            result = get_user_context(mock_request, context_key)
            assert result == mock_user_context
        else:
            if hasattr(mock_request.state, context_key):
                delattr(mock_request.state, context_key)
            with pytest.raises(ValueError, match="User context not found"):
                get_user_context(mock_request, context_key)

    @pytest.mark.asyncio
    async def test_extract_user_context(self, mock_request):
        """Test extracting user context from request."""
        mock_identity = IdentityContext(
            user_id="test-user-123", email="test@example.com", token_type="access_token"
        )

        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {
            "X-Session-ID": "session-123",
            "X-Request-ID": "request-456",
            "User-Agent": "test-agent",
        }

        with patch("nalai.services.auth_service.get_auth_service") as mock_get_auth:
            mock_auth_service = AsyncMock()
            mock_auth_service.authenticate_request.return_value = mock_identity
            mock_get_auth.return_value = mock_auth_service

            result = await extract_user_context(mock_request)

            assert isinstance(result, UserContext)
            assert result.identity == mock_identity
            assert result.session_id == "session-123"
            assert result.request_id == "request-456"
            assert result.ip_address == "127.0.0.1"
            assert result.user_agent == "test-agent"
            assert result.timestamp is not None
