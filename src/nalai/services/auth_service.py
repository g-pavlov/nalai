"""
Authentication service for API Assistant.

This module provides authentication and authorization services,
including OIDC integration and token management.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from ..config import settings

logger = logging.getLogger(__name__)


class IdentityContext(BaseModel):
    """User identity context extracted from authentication tokens."""

    user_id: str = Field(..., description="Unique user identifier (sub claim)")
    email: str | None = Field(None, description="User email address")
    given_name: str | None = Field(None, description="User's given name")
    family_name: str | None = Field(None, description="User's family name")
    org_unit_id: str | None = Field(None, description="Organization unit identifier")
    roles: list[str] = Field(default_factory=list, description="User roles")
    permissions: list[str] = Field(default_factory=list, description="User permissions")
    token_type: str = Field(..., description="Type of token (access_token, id_token)")
    token_expires_at: datetime | None = Field(None, description="Token expiration time")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional identity metadata"
    )

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.given_name and self.family_name:
            return f"{self.given_name} {self.family_name}"
        elif self.given_name:
            return self.given_name
        elif self.family_name:
            return self.family_name
        else:
            return self.user_id

    @property
    def is_authenticated(self) -> bool:
        """Check if user is properly authenticated."""
        return bool(self.user_id and self.user_id != "anonymous")

    @property
    def is_token_expired(self) -> bool:
        """Check if the authentication token has expired."""
        if not self.token_expires_at:
            return False
        # Use timezone-aware now() to compare with token_expires_at
        return datetime.now(self.token_expires_at.tzinfo) > self.token_expires_at


class UserContext(BaseModel):
    """User context for request processing."""

    identity: IdentityContext = Field(..., description="User identity context")
    session_id: str | None = Field(None, description="Session identifier")
    request_id: str | None = Field(None, description="Request identifier for tracing")
    ip_address: str | None = Field(None, description="Client IP address")
    user_agent: str | None = Field(None, description="Client user agent")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Request timestamp"
    )

    @property
    def user_id(self) -> str:
        """Get user ID from identity context."""
        return self.identity.user_id

    @property
    def email(self) -> str | None:
        """Get user email from identity context."""
        return self.identity.email

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self.identity.is_authenticated


class APITokenResponse(BaseModel):
    """Response containing API token."""

    token: str = Field(..., description="API access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime | None = Field(None, description="Token expiration time")
    scopes: list[str] = Field(default_factory=list, description="Token scopes")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional token metadata"
    )


class AuthService(ABC):
    """Abstract base class for authentication services."""

    def __init__(self, config: dict[str, Any]):
        """Initialize authentication service with configuration."""
        self.config = config
        self._token_cache: dict[str, APITokenResponse] = {}

    @abstractmethod
    async def authenticate_request(self, request: Request) -> IdentityContext:
        """Authenticate a request and extract user identity."""
        pass

    @abstractmethod
    async def get_api_token(self, context: IdentityContext, service: str) -> str:
        """Get API token for the specified service."""
        pass

    async def validate_token(self, token: str) -> bool:
        """Optional token validation - can be disabled for externalized auth."""
        if not settings.auth_validate_tokens:
            logger.debug("Token validation disabled - skipping validation")
            return True  # Skip validation
        return await self._validate_token_impl(token)

    @abstractmethod
    async def _validate_token_impl(self, token: str) -> bool:
        """Implementation of token validation."""
        pass


class StandardAuthService(AuthService):
    """Standard OIDC authentication service implementation."""

    def __init__(self, config: dict[str, Any]):
        """Initialize standard auth service."""
        super().__init__(config)
        self.issuer = config.get("issuer", settings.auth_oidc_issuer)
        self.audience = config.get("audience", settings.auth_oidc_audience)
        self.client_credentials = config.get(
            "client_credentials", settings.auth_client_credentials
        )
        self.mode = config.get("mode", settings.auth_mode)

        logger.debug(f"Standard auth service initialized with mode: {self.mode}")

    async def authenticate_request(self, request: Request) -> IdentityContext:
        """Authenticate request and extract user identity."""
        if not settings.auth_enabled:
            return self._create_dev_identity()

        # Try ID token first
        id_token = request.headers.get("X-Id-Token")
        if id_token:
            return await self._extract_identity_from_token(id_token, "id_token")

        # Try Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.replace("Bearer ", "", 1)
            return await self._extract_identity_from_token(access_token, "access_token")

        # No valid token found
        raise HTTPException(status_code=401, detail="Authentication required")

    async def get_api_token(self, context: IdentityContext, service: str) -> str:
        """Get API token for the specified service."""
        if self.mode == "delegation":
            return await self._get_delegated_token(context, service)
        elif self.mode == "client_credentials":
            return await self._get_client_credentials_token(service)
        else:
            raise ValueError(f"Unsupported auth mode: {self.mode}")

    async def _extract_identity_from_token(
        self, token: str, token_type: str
    ) -> IdentityContext:
        """Extract identity information from JWT token."""
        try:
            # Decode token without verification if validation is disabled
            if not settings.auth_validate_tokens:
                payload = jwt.decode(token, options={"verify_signature": False})
            else:
                # TODO: Implement proper JWT validation with issuer verification
                payload = jwt.decode(token, options={"verify_signature": False})

            # Extract standard claims
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=401, detail="Invalid token: missing sub claim"
                )

            # Extract expiration
            exp = payload.get("exp")
            token_expires_at = None
            if exp:
                token_expires_at = datetime.fromtimestamp(exp)

            # Extract roles and permissions
            roles = payload.get("roles", [])
            if isinstance(roles, str):
                roles = [roles]

            permissions = payload.get("permissions", [])
            if isinstance(permissions, str):
                permissions = [permissions]

            return IdentityContext(
                user_id=user_id,
                email=payload.get("email"),
                given_name=payload.get("given_name"),
                family_name=payload.get("family_name"),
                org_unit_id=payload.get("org_unit_id"),
                roles=roles,
                permissions=permissions,
                token_type=token_type,
                token_expires_at=token_expires_at,
                metadata={
                    "issuer": payload.get("iss"),
                    "audience": payload.get("aud"),
                    "issued_at": payload.get("iat"),
                },
            )

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token format: {e}")
            raise HTTPException(status_code=401, detail="Invalid token format") from e
        except HTTPException:
            # Re-raise HTTP exceptions as-is to preserve specific error messages
            raise
        except Exception as e:
            logger.error(f"Error extracting identity from token: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed") from e

    async def _get_delegated_token(self, context: IdentityContext, service: str) -> str:
        """Get delegated token using user's credentials."""
        # In delegation mode, we would use the user's token to get service tokens
        # This is a simplified implementation - in practice, you'd implement
        # token exchange or delegation logic here
        logger.debug(f"Getting delegated token for service: {service}")

        # For now, return a placeholder token
        # TODO: Implement proper token delegation logic
        return f"delegated_token_for_{service}"

    async def _get_client_credentials_token(self, service: str) -> str:
        """Get client credentials token for the specified service."""
        if service not in self.client_credentials:
            raise ValueError(f"No client credentials configured for service: {service}")

        # Check cache first
        cache_key = f"cc_token_{service}"
        if cache_key in self._token_cache:
            cached_token = self._token_cache[cache_key]
            if not cached_token.expires_at or cached_token.expires_at > datetime.now():
                return cached_token.token

        # TODO: Implement proper OAuth2 client credentials flow
        # For now, return a placeholder token
        logger.debug(f"Getting client credentials token for service: {service}")

        # Create mock token response
        token_response = APITokenResponse(
            token=f"cc_token_for_{service}",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
            scopes=["api:read", "api:write"],
        )

        # Cache the token
        self._token_cache[cache_key] = token_response

        return token_response.token

    async def _validate_token_impl(self, token: str) -> bool:
        """Implementation of token validation."""
        try:
            # TODO: Implement proper JWT validation with issuer verification
            # For now, just check if token can be decoded
            payload = jwt.decode(token, options={"verify_signature": False})

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                logger.warning("Token has expired")
                return False

            return True

        except jwt.InvalidTokenError:
            logger.warning("Token validation failed: invalid token")
            return False
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False

    def _create_dev_identity(self) -> IdentityContext:
        """Create development identity when auth is disabled."""
        return IdentityContext(
            user_id="dev-user",
            email="dev@example.com",
            given_name="Development",
            family_name="User",
            org_unit_id="dev-org",
            roles=["developer"],
            permissions=["read", "write"],
            token_type="dev_token",
            metadata={"dev_mode": True},
        )


class AuthServiceFactory:
    """Factory for creating authentication services."""

    @staticmethod
    def create_auth_service(
        provider: str = None, config: dict[str, Any] = None
    ) -> AuthService:
        """Create authentication service based on provider."""
        if not provider:
            provider = settings.auth_provider

        if not config:
            config = {}

        if provider == "standard":
            return StandardAuthService(config)
        elif provider == "auth0":
            # TODO: Implement Auth0-specific service
            return StandardAuthService(config)
        elif provider == "keycloak":
            # TODO: Implement Keycloak-specific service
            return StandardAuthService(config)
        else:
            raise ValueError(f"Unsupported auth provider: {provider}")


# Global auth service instance
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get the global authentication service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthServiceFactory.create_auth_service()
    return _auth_service


def set_auth_service(auth_service: AuthService) -> None:
    """Set the global authentication service instance."""
    global _auth_service
    _auth_service = auth_service
