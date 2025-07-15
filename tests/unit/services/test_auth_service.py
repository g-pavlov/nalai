"""
Unit tests for authentication service.

Tests cover OIDC authentication, token validation, identity extraction,
and different authentication modes with generated JWT tokens.
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from api_assistant.server.models.identity import IdentityContext, UserContext
from api_assistant.services.auth_service import (
    AuthService,
    AuthServiceFactory,
    StandardAuthService,
    get_auth_service,
    set_auth_service,
)


class TestAuthService:
    """Test cases for authentication service."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("api_assistant.services.auth_service.settings") as mock_settings:
            mock_settings.disable_auth = False
            mock_settings.auth_validate_tokens = True
            mock_settings.auth_provider = "standard"
            mock_settings.auth_mode = "client_credentials"
            mock_settings.auth_oidc_issuer = "https://test.auth0.com/"
            mock_settings.auth_oidc_audience = "test-audience"
            mock_settings.client_credentials = {
                "service_a": {
                    "client_id": "test-client-id",
                    "client_secret": "test-client-secret",
                }
            }
            yield mock_settings

    @pytest.fixture
    def valid_jwt_token(self):
        """Generate a valid JWT token for testing."""
        payload = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
            "org_unit_id": "test-org",
            "roles": ["developer", "admin"],
            "permissions": ["read", "write"],
            "iss": "https://test.auth0.com/",
            "aud": "test-audience",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        return jwt.encode(payload, "test-secret", algorithm="HS256")

    @pytest.fixture
    def expired_jwt_token(self):
        """Generate an expired JWT token for testing."""
        payload = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
            "org_unit_id": "test-org",
            "roles": ["developer"],
            "permissions": ["read"],
            "iss": "https://test.auth0.com/",
            "aud": "test-audience",
            "iat": datetime.utcnow() - timedelta(hours=2),
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        return jwt.encode(payload, "test-secret", algorithm="HS256")

    @pytest.fixture
    def invalid_jwt_token(self):
        """Generate an invalid JWT token for testing."""
        return "invalid.token.here"

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request object."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        return request

    def test_auth_service_abstract_methods(self):
        """Test that AuthService is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            AuthService({})

    def test_standard_auth_service_initialization(self, mock_settings):
        """Test StandardAuthService initialization."""
        config = {
            "issuer": "https://custom.auth0.com/",
            "audience": "custom-audience",
            "mode": "delegation",
        }

        auth_service = StandardAuthService(config)

        assert auth_service.issuer == "https://custom.auth0.com/"
        assert auth_service.audience == "custom-audience"
        assert auth_service.mode == "delegation"
        assert auth_service.client_credentials == mock_settings.client_credentials

    def test_standard_auth_service_default_initialization(self, mock_settings):
        """Test StandardAuthService initialization with defaults."""
        auth_service = StandardAuthService({})

        assert auth_service.issuer == mock_settings.auth_oidc_issuer
        assert auth_service.audience == mock_settings.auth_oidc_audience
        assert auth_service.mode == mock_settings.auth_mode

    @pytest.mark.asyncio
    async def test_authenticate_request_with_id_token(
        self, mock_settings, valid_jwt_token, mock_request
    ):
        """Test authentication with ID token."""
        mock_request.headers = {"X-Id-Token": valid_jwt_token}

        auth_service = StandardAuthService({})
        identity = await auth_service.authenticate_request(mock_request)

        assert isinstance(identity, IdentityContext)
        assert identity.user_id == "test-user-123"
        assert identity.email == "test@example.com"
        assert identity.given_name == "Test"
        assert identity.family_name == "User"
        assert identity.org_unit_id == "test-org"
        assert identity.roles == ["developer", "admin"]
        assert identity.permissions == ["read", "write"]
        assert identity.token_type == "id_token"
        assert identity.is_authenticated is True

    @pytest.mark.asyncio
    async def test_authenticate_request_with_authorization_header(
        self, mock_settings, valid_jwt_token, mock_request
    ):
        """Test authentication with Authorization header."""
        mock_request.headers = {"Authorization": f"Bearer {valid_jwt_token}"}

        auth_service = StandardAuthService({})
        identity = await auth_service.authenticate_request(mock_request)

        assert isinstance(identity, IdentityContext)
        assert identity.user_id == "test-user-123"
        assert identity.token_type == "access_token"

    @pytest.mark.asyncio
    async def test_authenticate_request_no_token(self, mock_settings, mock_request):
        """Test authentication with no token."""
        auth_service = StandardAuthService({})

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.authenticate_request(mock_request)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_authenticate_request_invalid_token(
        self, mock_settings, invalid_jwt_token, mock_request
    ):
        """Test authentication with invalid token."""
        mock_request.headers = {"Authorization": f"Bearer {invalid_jwt_token}"}

        auth_service = StandardAuthService({})

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.authenticate_request(mock_request)

        assert exc_info.value.status_code == 401
        assert "Invalid token format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_authenticate_request_missing_sub_claim(
        self, mock_settings, mock_request
    ):
        """Test authentication with token missing sub claim."""
        payload = {
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")
        mock_request.headers = {"Authorization": f"Bearer {token}"}

        auth_service = StandardAuthService({})

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.authenticate_request(mock_request)

        assert exc_info.value.status_code == 401
        assert "missing sub claim" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_authenticate_request_development_mode(self, mock_request):
        """Test authentication in development mode."""
        with patch("api_assistant.services.auth_service.settings") as mock_settings:
            mock_settings.disable_auth = True

            auth_service = StandardAuthService({})
            identity = await auth_service.authenticate_request(mock_request)

            assert identity.user_id == "dev-user"
            assert identity.email == "dev@example.com"
            assert identity.given_name == "Development"
            assert identity.family_name == "User"
            assert identity.org_unit_id == "dev-org"
            assert identity.roles == ["developer"]
            assert identity.permissions == ["read", "write"]
            assert identity.token_type == "dev_token"
            assert identity.metadata["dev_mode"] is True

    @pytest.mark.asyncio
    async def test_get_api_token_client_credentials_mode(self, mock_settings):
        """Test getting API token in client credentials mode."""
        auth_service = StandardAuthService({"mode": "client_credentials"})
        identity = IdentityContext(user_id="test-user", token_type="access_token")

        token = await auth_service.get_api_token(identity, "service_a")

        assert token == "cc_token_for_service_a"

    @pytest.mark.asyncio
    async def test_get_api_token_delegation_mode(self, mock_settings):
        """Test getting API token in delegation mode."""
        auth_service = StandardAuthService({"mode": "delegation"})
        identity = IdentityContext(user_id="test-user", token_type="access_token")

        token = await auth_service.get_api_token(identity, "service_a")

        assert token == "delegated_token_for_service_a"

    @pytest.mark.asyncio
    async def test_get_api_token_unsupported_mode(self, mock_settings):
        """Test getting API token with unsupported mode."""
        auth_service = StandardAuthService({"mode": "unsupported"})
        identity = IdentityContext(user_id="test-user", token_type="access_token")

        with pytest.raises(ValueError, match="Unsupported auth mode"):
            await auth_service.get_api_token(identity, "service_a")

    @pytest.mark.asyncio
    async def test_get_api_token_service_not_configured(self, mock_settings):
        """Test getting API token for unconfigured service."""
        auth_service = StandardAuthService({"mode": "client_credentials"})
        identity = IdentityContext(user_id="test-user", token_type="access_token")

        with pytest.raises(ValueError, match="No client credentials configured"):
            await auth_service.get_api_token(identity, "unconfigured_service")

    @pytest.mark.asyncio
    async def test_validate_token_enabled(self, mock_settings, valid_jwt_token):
        """Test token validation when enabled."""
        with patch("api_assistant.services.auth_service.settings") as mock_settings:
            mock_settings.auth_validate_tokens = True

            auth_service = StandardAuthService({})
            result = await auth_service.validate_token(valid_jwt_token)

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_token_disabled(self, mock_settings, invalid_jwt_token):
        """Test token validation when disabled."""
        with patch("api_assistant.services.auth_service.settings") as mock_settings:
            mock_settings.auth_validate_tokens = False

            auth_service = StandardAuthService({})
            result = await auth_service.validate_token(invalid_jwt_token)

            assert result is True  # Should skip validation

    @pytest.mark.asyncio
    async def test_validate_token_expired(self, mock_settings, expired_jwt_token):
        """Test token validation with expired token."""
        with patch("api_assistant.services.auth_service.settings") as mock_settings:
            mock_settings.auth_validate_tokens = True

            auth_service = StandardAuthService({})
            result = await auth_service.validate_token(expired_jwt_token)

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_token_invalid(self, mock_settings, invalid_jwt_token):
        """Test token validation with invalid token."""
        with patch("api_assistant.services.auth_service.settings") as mock_settings:
            mock_settings.auth_validate_tokens = True

            auth_service = StandardAuthService({})
            result = await auth_service.validate_token(invalid_jwt_token)

            assert result is False

    def test_identity_context_properties(self):
        """Test IdentityContext properties."""
        identity = IdentityContext(
            user_id="test-user",
            email="test@example.com",
            given_name="Test",
            family_name="User",
            token_type="access_token",
        )

        assert identity.full_name == "Test User"
        assert identity.is_authenticated is True

        # Test with missing names
        identity.given_name = None
        assert identity.full_name == "User"

        identity.family_name = None
        assert identity.full_name == "test-user"

        # Test token expiration
        identity.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
        assert identity.is_token_expired is False

        identity.token_expires_at = datetime.now(UTC) - timedelta(hours=1)
        assert identity.is_token_expired is True

    def test_auth_service_factory_standard_provider(self, mock_settings):
        """Test AuthServiceFactory with standard provider."""
        auth_service = AuthServiceFactory.create_auth_service("standard", {})
        assert isinstance(auth_service, StandardAuthService)

    def test_auth_service_factory_unsupported_provider(self, mock_settings):
        """Test AuthServiceFactory with unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported auth provider"):
            AuthServiceFactory.create_auth_service("unsupported", {})

    def test_auth_service_factory_default_provider(self, mock_settings):
        """Test AuthServiceFactory with default provider."""
        auth_service = AuthServiceFactory.create_auth_service()
        assert isinstance(auth_service, StandardAuthService)

    def test_get_auth_service_singleton(self, mock_settings):
        """Test get_auth_service returns singleton instance."""
        # Clear any existing instance
        set_auth_service(None)

        service1 = get_auth_service()
        service2 = get_auth_service()

        assert service1 is service2
        assert isinstance(service1, StandardAuthService)

    def test_set_auth_service(self, mock_settings):
        """Test set_auth_service."""
        custom_service = StandardAuthService({"mode": "delegation"})
        set_auth_service(custom_service)

        service = get_auth_service()
        assert service is custom_service

    def test_user_context_properties(self):
        """Test UserContext properties."""
        identity = IdentityContext(
            user_id="test-user", email="test@example.com", token_type="access_token"
        )
        user_context = UserContext(
            identity=identity,
            session_id="test-session",
            request_id="test-request",
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )

        assert user_context.user_id == "test-user"
        assert user_context.email == "test@example.com"
        assert user_context.is_authenticated is True

    @pytest.mark.asyncio
    async def test_token_caching(self, mock_settings):
        """Test token caching in client credentials mode."""
        auth_service = StandardAuthService({"mode": "client_credentials"})
        identity = IdentityContext(user_id="test-user", token_type="access_token")

        # First call should create token
        token1 = await auth_service.get_api_token(identity, "service_a")

        # Second call should return cached token
        token2 = await auth_service.get_api_token(identity, "service_a")

        assert token1 == token2
        assert "cc_token_for_service_a" in token1

    @pytest.mark.asyncio
    async def test_extract_identity_with_string_roles(
        self, mock_settings, mock_request
    ):
        """Test identity extraction with string roles instead of list."""
        payload = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "roles": "developer",  # String instead of list
            "permissions": "read",  # String instead of list
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")
        mock_request.headers = {"Authorization": f"Bearer {token}"}

        auth_service = StandardAuthService({})
        identity = await auth_service.authenticate_request(mock_request)

        assert identity.roles == ["developer"]
        assert identity.permissions == ["read"]

    @pytest.mark.asyncio
    async def test_extract_identity_with_missing_optional_fields(
        self, mock_settings, mock_request
    ):
        """Test identity extraction with missing optional fields."""
        payload = {
            "sub": "test-user-123",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")
        mock_request.headers = {"Authorization": f"Bearer {token}"}

        auth_service = StandardAuthService({})
        identity = await auth_service.authenticate_request(mock_request)

        assert identity.user_id == "test-user-123"
        assert identity.email is None
        assert identity.given_name is None
        assert identity.family_name is None
        assert identity.org_unit_id is None
        assert identity.roles == []
        assert identity.permissions == []
        assert identity.is_authenticated is True
