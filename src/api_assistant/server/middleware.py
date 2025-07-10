"""
Middleware functions for API Assistant server.

This module contains FastAPI middleware for logging, authentication,
and user context management.

Usage Examples:

# Define excluded paths based on your actual routes
EXCLUDED_PATHS = create_middleware_config(
    additional_excluded_paths={"/metrics", "/status"}
)

# Register middleware with explicit excluded paths
app.add_middleware(create_log_request_middleware(excluded_paths=EXCLUDED_PATHS))
app.add_middleware(create_user_context_middleware(excluded_paths=EXCLUDED_PATHS))
"""

import json
import logging
from collections.abc import Callable

import jwt
from fastapi import Request
from jwt.exceptions import InvalidTokenError

from ..config import settings

logger = logging.getLogger("api-assistant")


def is_request_processable(request: Request, excluded_paths: set[str] = None) -> bool:
    if excluded_paths is None:
        excluded_paths = set()

    return request.url.path not in excluded_paths


def create_log_request_middleware(
    excluded_paths: set[str] = None,
    log_methods: set[str] = None,
    include_body: bool = True,
):
    if log_methods is None:
        log_methods = {"POST", "PUT", "PATCH"}

    async def log_request(request: Request, call_next: Callable):
        if is_request_processable(request, excluded_paths):
            user_info = await extract_user_info_from_token(request)
            email = user_info.get("email") if user_info else None
            request.state.user_email = email
            request_body = "No body logged"
            if include_body and request.method in log_methods:
                try:
                    request_body = await request.json()
                except json.JSONDecodeError:
                    request_body = "Invalid JSON body"
            logger.debug(
                f"User with email: {email} called request: '{request.method} {request.url.path}' with body: {request_body}"
            )
        return await call_next(request)

    return log_request


def create_user_context_middleware(
    excluded_paths: set[str] = None, context_key: str = "user_context"
):
    async def add_user_context(request: Request, call_next: Callable):
        if is_request_processable(request, excluded_paths):
            user_context = await extract_user_info_from_token(request)
            setattr(request.state, context_key, user_context or {})
        return await call_next(request)

    return add_user_context


async def extract_user_info_from_token(request: Request):
    if settings.disable_auth:
        return {
            "sub": "dev-user",
            "email": "dev@example.com",
            "given_name": "Development",
            "family_name": "User",
        }

    # Try ID token first
    id_token = request.headers.get("X-Id-Token")
    if id_token:
        try:
            payload = jwt.decode(id_token, options={"verify_signature": False})
            return extract_standard_claims(payload)
        except InvalidTokenError:
            logger.warning("Invalid ID token format")

    # Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        access_token = auth_header.replace("Bearer ", "", 1)
        try:
            payload = jwt.decode(access_token, options={"verify_signature": False})
            return extract_standard_claims(payload)
        except InvalidTokenError:
            logger.warning("Invalid access token format")

    # No valid token found
    return {}


def extract_standard_claims(token_payload: dict) -> dict:
    return {
        "sub": token_payload.get("sub"),
        "email": token_payload.get("email"),
        "given_name": token_payload.get("given_name"),
        "family_name": token_payload.get("family_name"),
    }
