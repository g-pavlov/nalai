"""
Identity and user context models for access control.

This module contains models for user identity, authentication context,
and access control data structures.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


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


class ThreadOwnership(BaseModel):
    """Thread ownership record for access control."""

    thread_id: str = Field(..., description="Thread identifier")
    user_id: str = Field(..., description="Owner user identifier")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    last_accessed: datetime = Field(
        default_factory=datetime.now, description="Last access timestamp"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class AccessEvent(BaseModel):
    """Access control event for audit logging."""

    user_id: str = Field(..., description="User identifier")
    resource: str = Field(..., description="Resource being accessed")
    action: str = Field(..., description="Action being performed")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Event timestamp",
    )
    success: bool = Field(..., description="Whether access was successful")
    ip_address: str | None = Field(None, description="Client IP address")
    user_agent: str | None = Field(None, description="Client user agent")
    session_id: str | None = Field(None, description="Session identifier")
    request_id: str | None = Field(None, description="Request identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional event metadata"
    )

    def to_audit_entry(self) -> dict[str, Any]:
        """Convert to audit log entry format."""
        return {
            "user_id": self.user_id,
            "resource": self.resource,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "metadata": self.metadata,
        }


class APITokenRequest(BaseModel):
    """Request for API token retrieval."""

    service: str = Field(..., description="Service identifier for token")
    scopes: list[str] = Field(default_factory=list, description="Required scopes")
    audience: str | None = Field(None, description="Token audience")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional request metadata"
    )


class APITokenResponse(BaseModel):
    """Response containing API token."""

    token: str = Field(..., description="API access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_at: datetime | None = Field(None, description="Token expiration time")
    scopes: list[str] = Field(default_factory=list, description="Token scopes")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional token metadata"
    )
