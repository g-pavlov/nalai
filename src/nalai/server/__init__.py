"""
Server module for API Assistant.

This module contains the FastAPI application, middleware,
and route handlers for the API Assistant server.
"""

from .middleware import (
    create_audit_middleware,
    create_auth_middleware,
    create_log_request_middleware,
    create_user_context_middleware,
    get_user_context,
    is_request_processable,
)
from .schemas import MessageInput

__all__ = [
    "MessageInput",
    "create_log_request_middleware",
    "create_user_context_middleware",
    "create_auth_middleware",
    "create_audit_middleware",
    "get_user_context",
    "is_request_processable",
]


def get_app():
    """Get the FastAPI application instance (lazy import to avoid circular imports)."""
    from .app import app

    return app
