"""
Middleware functions for API Assistant server.

This module contains FastAPI middleware for logging, authentication,
and user context management.
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException, Request

from ..server.models.identity import UserContext

logger = logging.getLogger("nalai")


def is_request_processable(request: Request, excluded_paths: set[str] = None) -> bool:
    """Check if request should be processed by middleware."""
    if excluded_paths is None:
        excluded_paths = set()
    return request.url.path not in excluded_paths


def create_log_request_middleware(excluded_paths: set[str] = None):
    """Create middleware that logs request and response details."""

    async def log_request_middleware(request: Request, call_next: Callable):
        start_time = datetime.now()

        if is_request_processable(request, excluded_paths):
            # Log request to console for real-time visibility
            logger.info(
                f"Request: {request.method} {request.url.path} "
                f"from {request.client.host if request.client else 'unknown'}"
            )

            # Log structured access event
            access_logger = logging.getLogger("api_assistant.access")
            user_context = getattr(request.state, "user_context", None)
            user_id = user_context.user_id if user_context else "anonymous"

            access_data = {
                "action": "request_start",
                "method": request.method,
                "path": request.url.path,
                "remote_addr": request.client.host if request.client else None,
                "user_agent": request.headers.get("User-Agent"),
                "user_id": user_id,
                "request_id": request.headers.get("X-Request-ID"),
                "session_id": request.headers.get("X-Session-ID"),
            }
            access_logger.info(json.dumps(access_data))

        response = await call_next(request)

        if is_request_processable(request, excluded_paths):
            duration = (datetime.now() - start_time).total_seconds()

            # Log response to console for real-time visibility
            logger.info(
                f"Response: {response.status_code} for {request.method} {request.url.path}"
            )

            # Log structured access completion
            access_logger = logging.getLogger("api_assistant.access")
            user_context = getattr(request.state, "user_context", None)
            user_id = user_context.user_id if user_context else "anonymous"

            access_data = {
                "action": "request_complete",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "response_time_ms": int(duration * 1000),
                "remote_addr": request.client.host if request.client else None,
                "user_agent": request.headers.get("User-Agent"),
                "user_id": user_id,
                "request_id": request.headers.get("X-Request-ID"),
                "session_id": request.headers.get("X-Session-ID"),
            }
            access_logger.info(json.dumps(access_data))

        return response

    return log_request_middleware


def create_auth_middleware(excluded_paths: set[str] = None):
    """Create middleware that authenticates requests using the auth service."""

    async def auth_middleware(request: Request, call_next: Callable):
        if is_request_processable(request, excluded_paths):
            try:
                from ..services.auth_service import get_auth_service

                auth_service = get_auth_service()
                identity = await auth_service.authenticate_request(request)

                request.state.identity = identity
                logger.debug(f"Authenticated user: {identity.user_id}")

            except Exception as e:
                logger.warning(f"Authentication failed: {e}")
                raise HTTPException(
                    status_code=401, detail="Authentication required"
                ) from e

        return await call_next(request)

    return auth_middleware


def create_audit_middleware(excluded_paths: set[str] = None):
    """Create middleware that logs audit events for all requests."""

    async def audit_middleware(request: Request, call_next: Callable):
        start_time = datetime.now()

        user_context = getattr(request.state, "user_context", None)
        user_id = user_context.user_id if user_context else "anonymous"

        # Log request start
        if is_request_processable(request, excluded_paths):
            try:
                from ..services.audit_service import get_audit_service

                audit_service = get_audit_service()
                await audit_service.log_request_start(
                    user_id=user_id,
                    method=request.method,
                    path=request.url.path,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                    session_id=request.headers.get("X-Session-ID"),
                    request_id=request.headers.get("X-Request-ID"),
                )
            except Exception as e:
                logger.error(f"Failed to log audit event: {e}")

        # Process request
        response = await call_next(request)

        # Log request completion
        if is_request_processable(request, excluded_paths):
            try:
                from ..services.audit_service import get_audit_service

                audit_service = get_audit_service()
                duration = (datetime.now() - start_time).total_seconds()

                await audit_service.log_request_complete(
                    user_id=user_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration=duration,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                    session_id=request.headers.get("X-Session-ID"),
                    request_id=request.headers.get("X-Request-ID"),
                )
            except Exception as e:
                logger.error(f"Failed to log audit completion: {e}")

        return response

    return audit_middleware


def create_user_context_middleware(
    excluded_paths: set[str] = None, context_key: str = "user_context"
):
    """Create middleware that extracts and injects user context."""

    async def add_user_context(request: Request, call_next: Callable):
        if is_request_processable(request, excluded_paths):
            try:
                # Get identity that was already extracted by auth middleware
                identity = getattr(request.state, "identity", None)

                if identity is None:
                    # Fallback: extract user context if identity not available
                    user_context = await extract_user_context(request)
                else:
                    # Create user context from the already authenticated identity
                    user_context = UserContext(
                        identity=identity,
                        session_id=request.headers.get("X-Session-ID"),
                        request_id=request.headers.get("X-Request-ID"),
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("User-Agent"),
                        timestamp=datetime.now(),
                    )

                setattr(request.state, context_key, user_context)
            except Exception as e:
                logger.warning(f"Failed to extract user context: {e}")
                setattr(request.state, context_key, None)

        return await call_next(request)

    return add_user_context


def get_user_context(
    request: Request, context_key: str = "user_context"
) -> UserContext:
    """Get user context from request state."""
    user_context = getattr(request.state, context_key, None)
    if user_context is None:
        raise ValueError("User context not found in request state")
    return user_context


async def extract_user_context(request: Request) -> UserContext:
    """Extract user context from request using authentication service."""
    from ..services.auth_service import get_auth_service

    auth_service = get_auth_service()
    identity = await auth_service.authenticate_request(request)

    return UserContext(
        identity=identity,
        session_id=request.headers.get("X-Session-ID"),
        request_id=request.headers.get("X-Request-ID"),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        timestamp=datetime.now(),
    )
