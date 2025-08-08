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
import yaml
from fastapi import HTTPException

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.server.models.identity import IdentityContext, UserContext
from nalai.services.auth_service import (
    AuthService,
    AuthServiceFactory,
    StandardAuthService,
    get_auth_service,
    set_auth_service,
)


@pytest.fixture
def test_data():
    """Load test data from YAML file."""
    test_data_path = os.path.join(
        os.path.dirname(__file__), "..", "test_data", "auth_service_test_cases.yaml"
    )
    with open(test_data_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("nalai.services.auth_service.settings") as mock_settings:
        mock_settings.auth_enabled = True
        mock_settings.auth_validate_tokens = True
        mock_settings.auth_provider = "standard"
        mock_settings.auth_mode = "client_credentials"
        mock_settings.auth_oidc_issuer = "https://test.auth0.com/"
        mock_settings.auth_oidc_audience = "test-audience"
        mock_settings.auth_client_credentials = {
            "service_a": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
            }
        }
        yield mock_settings


class TestAuthService:
    """Test cases for authentication service."""

    def test_auth_service_abstract_methods(self):
        """Test that AuthService is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            AuthService({})

    @pytest.mark.parametrize(
        "test_case", ["standard_initialization", "default_initialization"]
    )
    def test_auth_service_initialization(self, test_case, test_data, mock_settings):
        """Test StandardAuthService initialization."""
        case_data = next(
            c
            for c in test_data["auth_service_initialization"]
            if c["name"] == test_case
        )

        config = case_data["input"]["config"]
        auth_service = StandardAuthService(config)

        expected = case_data["expected"]
        assert auth_service.issuer == expected["issuer"]
        assert auth_service.audience == expected["audience"]
        assert auth_service.mode == expected["mode"]

    @pytest.mark.parametrize(
        "test_case",
        [
            "id_token_authentication",
            "authorization_header_authentication",
            "no_token_authentication",
            "invalid_token_authentication",
            "missing_sub_claim",
            "development_mode",
        ],
    )
    @pytest.mark.asyncio
    async def test_authentication_scenarios(self, test_case, test_data, mock_settings):
        """Test various authentication scenarios."""
        case_data = next(
            c for c in test_data["authentication_scenarios"] if c["name"] == test_case
        )

        # Setup request mock
        request = MagicMock()
        request.headers = case_data["input"]["headers"].copy()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Setup settings based on test case
        if case_data["name"] == "development_mode":
            mock_settings.auth_enabled = case_data["input"]["auth_enabled"]

        # Generate token if needed
        if "token_payload" in case_data["input"]:
            payload = case_data["input"]["token_payload"].copy()

            # Handle time-based fields
            if payload.get("iat") == "now":
                payload["iat"] = datetime.now(UTC)
            if payload.get("exp") == "now+1h":
                payload["exp"] = datetime.now(UTC) + timedelta(hours=1)
            elif payload.get("exp") == "now-1h":
                payload["exp"] = datetime.now(UTC) - timedelta(hours=1)

            token = jwt.encode(payload, "test-secret", algorithm="HS256")

            # Replace token placeholders in headers
            for header_name, header_value in request.headers.items():
                if header_value == "valid_jwt_token":
                    request.headers[header_name] = token
                elif header_value == "Bearer valid_jwt_token":
                    request.headers[header_name] = f"Bearer {token}"

        # Execute authentication
        auth_service = StandardAuthService({})

        if case_data["expected"]["should_raise"]:
            with pytest.raises(HTTPException) as exc_info:
                await auth_service.authenticate_request(request)

            assert exc_info.value.status_code == case_data["expected"]["status_code"]
            assert case_data["expected"]["detail_contains"] in str(
                exc_info.value.detail
            )
        else:
            identity = await auth_service.authenticate_request(request)

            # Verify identity properties
            expected = case_data["expected"]
            assert identity.user_id == expected["user_id"]
            if "email" in expected:
                assert identity.email == expected["email"]
            if "given_name" in expected:
                assert identity.given_name == expected["given_name"]
            if "family_name" in expected:
                assert identity.family_name == expected["family_name"]
            if "org_unit_id" in expected:
                assert identity.org_unit_id == expected["org_unit_id"]
            if "roles" in expected:
                assert identity.roles == expected["roles"]
            if "permissions" in expected:
                assert identity.permissions == expected["permissions"]
            if "token_type" in expected:
                assert identity.token_type == expected["token_type"]
            if "is_authenticated" in expected:
                assert identity.is_authenticated == expected["is_authenticated"]
            if "metadata" in expected:
                for key, value in expected["metadata"].items():
                    assert identity.metadata[key] == value

    @pytest.mark.parametrize(
        "test_case",
        [
            "client_credentials_mode",
            "delegation_mode",
            "unsupported_mode",
            "service_not_configured",
        ],
    )
    @pytest.mark.asyncio
    async def test_api_token_scenarios(self, test_case, test_data, mock_settings):
        """Test API token scenarios."""
        case_data = next(
            c for c in test_data["api_token_scenarios"] if c["name"] == test_case
        )

        # Create auth service with specified mode
        auth_service = StandardAuthService({"mode": case_data["input"]["mode"]})

        # Create identity context
        identity_data = case_data["input"]["identity"]
        identity = IdentityContext(
            user_id=identity_data["user_id"],
            token_type=identity_data["token_type"],
        )

        # Execute API token request
        if case_data["expected"]["should_raise"]:
            with pytest.raises(ValueError) as exc_info:
                await auth_service.get_api_token(
                    identity, case_data["input"]["service"]
                )

            assert case_data["expected"]["message_contains"] in str(exc_info.value)
        else:
            token = await auth_service.get_api_token(
                identity, case_data["input"]["service"]
            )
            assert token == case_data["expected"]["token"]

    @pytest.mark.parametrize(
        "test_case",
        [
            "valid_token_enabled",
            "invalid_token_disabled",
            "expired_token",
            "invalid_token_enabled",
        ],
    )
    @pytest.mark.asyncio
    async def test_token_validation_scenarios(
        self, test_case, test_data, mock_settings
    ):
        """Test token validation scenarios."""
        case_data = next(
            c for c in test_data["token_validation_scenarios"] if c["name"] == test_case
        )

        # Setup settings
        mock_settings.auth_validate_tokens = case_data["input"]["validate_tokens"]

        # Generate token if needed
        if "token_payload" in case_data["input"]:
            payload = case_data["input"]["token_payload"].copy()

            # Handle time-based fields
            if payload.get("exp") == "now+1h":
                payload["exp"] = datetime.now(UTC) + timedelta(hours=1)
            elif payload.get("exp") == "now-1h":
                payload["exp"] = datetime.now(UTC) - timedelta(hours=1)

            token = jwt.encode(payload, "test-secret", algorithm="HS256")
        else:
            token = case_data["input"]["token"]

        # Execute token validation
        auth_service = StandardAuthService({})
        result = await auth_service.validate_token(token)

        assert result == case_data["expected"]["result"]

    @pytest.mark.parametrize(
        "test_case",
        [
            "complete_identity",
            "missing_given_name",
            "missing_family_name",
            "missing_names",
            "expired_token",
        ],
    )
    def test_identity_context_scenarios(self, test_case, test_data):
        """Test IdentityContext properties."""
        case_data = next(
            c for c in test_data["identity_context_scenarios"] if c["name"] == test_case
        )

        # Create identity context
        input_data = case_data["input"]
        identity = IdentityContext(
            user_id=input_data["user_id"],
            email=input_data.get("email"),
            given_name=input_data.get("given_name"),
            family_name=input_data.get("family_name"),
            token_type=input_data["token_type"],
        )

        # Set token expiration if specified
        if "token_expires_at" in input_data:
            if input_data["token_expires_at"] == "now+1h":
                identity.token_expires_at = datetime.now(UTC) + timedelta(hours=1)
            elif input_data["token_expires_at"] == "now-1h":
                identity.token_expires_at = datetime.now(UTC) - timedelta(hours=1)

        # Verify expected properties
        expected = case_data["expected"]
        if "full_name" in expected:
            assert identity.full_name == expected["full_name"]
        if "is_authenticated" in expected:
            assert identity.is_authenticated == expected["is_authenticated"]
        if "is_token_expired" in expected:
            assert identity.is_token_expired == expected["is_token_expired"]

    @pytest.mark.parametrize("test_case", ["string_roles", "missing_optional_fields"])
    @pytest.mark.asyncio
    async def test_string_roles_scenarios(self, test_case, test_data, mock_settings):
        """Test identity extraction with string roles and missing fields."""
        case_data = next(
            c for c in test_data["string_roles_scenarios"] if c["name"] == test_case
        )

        # Setup request mock
        request = MagicMock()
        request.headers = case_data["input"]["headers"]
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        # Generate token
        payload = case_data["input"]["token_payload"].copy()
        if payload.get("exp") == "now+1h":
            payload["exp"] = datetime.now(UTC) + timedelta(hours=1)

        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        # Replace token placeholder
        for header_name, header_value in request.headers.items():
            if header_value == "Bearer valid_jwt_token":
                request.headers[header_name] = f"Bearer {token}"

        # Execute authentication
        auth_service = StandardAuthService({})

        if case_data["expected"]["should_raise"]:
            with pytest.raises(HTTPException):
                await auth_service.authenticate_request(request)
        else:
            identity = await auth_service.authenticate_request(request)

            # Verify expected properties
            expected = case_data["expected"]
            if "user_id" in expected:
                assert identity.user_id == expected["user_id"]
            if "email" in expected:
                assert identity.email == expected["email"]
            if "given_name" in expected:
                assert identity.given_name == expected["given_name"]
            if "family_name" in expected:
                assert identity.family_name == expected["family_name"]
            if "org_unit_id" in expected:
                assert identity.org_unit_id == expected["org_unit_id"]
            if "roles" in expected:
                assert identity.roles == expected["roles"]
            if "permissions" in expected:
                assert identity.permissions == expected["permissions"]
            if "is_authenticated" in expected:
                assert identity.is_authenticated == expected["is_authenticated"]

    @pytest.mark.parametrize(
        "test_case", ["standard_provider", "unsupported_provider", "default_provider"]
    )
    def test_factory_scenarios(self, test_case, test_data, mock_settings):
        """Test AuthServiceFactory scenarios."""
        case_data = next(
            c for c in test_data["factory_scenarios"] if c["name"] == test_case
        )

        input_data = case_data["input"]
        provider = input_data["provider"]
        config = input_data["config"]

        if case_data["expected"]["should_raise"]:
            with pytest.raises(ValueError) as exc_info:
                AuthServiceFactory.create_auth_service(provider, config)

            assert case_data["expected"]["message_contains"] in str(exc_info.value)
        else:
            auth_service = AuthServiceFactory.create_auth_service(provider, config)
            assert isinstance(auth_service, StandardAuthService)

    @pytest.mark.asyncio
    async def test_caching_scenarios(self, test_data, mock_settings):
        """Test token caching scenarios."""
        case_data = next(
            c for c in test_data["caching_scenarios"] if c["name"] == "token_caching"
        )

        # Create auth service
        auth_service = StandardAuthService({"mode": case_data["input"]["mode"]})

        # Create identity context
        identity_data = case_data["input"]["identity"]
        identity = IdentityContext(
            user_id=identity_data["user_id"],
            token_type=identity_data["token_type"],
        )

        # Make multiple calls
        calls = case_data["input"]["calls"]
        tokens = []
        for _ in range(calls):
            token = await auth_service.get_api_token(
                identity, case_data["input"]["service"]
            )
            tokens.append(token)

        # Verify results
        expected = case_data["expected"]
        assert tokens[0] == expected["first_token"]
        assert tokens[1] == expected["second_token"]
        assert tokens[0] == tokens[1]  # Tokens should be equal due to caching

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
