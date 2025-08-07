"""
Runtime configuration utilities for API Assistant server.

This module contains functions for managing runtime configuration,
thread IDs, and validation with access control integration.
"""

import logging
import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request

from ..config import BaseRuntimeConfiguration, settings
from ..server.middleware import get_user_context
from ..services.audit_utils import log_thread_access_event
from ..services.thread_access_control import (
    get_thread_access_control,
)
from .models.validation import validate_runtime_config

logger = logging.getLogger("nalai")


def _ensure_config_dict(config: dict | None) -> dict:
    """Convert Pydantic model to dict and ensure config is a dictionary."""
    if config is not None and hasattr(config, "model_dump"):
        config = config.model_dump()
    return config or {}


def _ensure_configurable(config: dict) -> dict:
    """Ensure configurable section exists and is a dictionary."""
    configurable = config.setdefault("configurable", {})
    if configurable is None:
        configurable = {}
        config["configurable"] = configurable
    return configurable


def ensure_thread_id_exists(
    config: dict | None, validate_uuid: bool = False
) -> tuple[dict, str]:
    """
    Ensure thread_id exists in config, generating one if needed.

    Args:
        config: Configuration dictionary or Pydantic model
        validate_uuid: Whether to validate existing thread_id as UUID4

    Returns:
        Tuple of (updated_config, thread_id)
    """
    config = _ensure_config_dict(config)
    configurable = _ensure_configurable(config)

    thread_id = configurable.get("thread_id")

    if thread_id:
        if validate_uuid:
            try:
                uuid.UUID(thread_id, version=4)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid thread_id format. Must be UUID4."
                ) from None
    else:
        thread_id = str(uuid.uuid4())
        configurable["thread_id"] = thread_id

    return config, thread_id


def add_auth_token_to_config(config: dict | None, req: Request) -> dict:
    """Set auth token from request headers."""
    config = _ensure_config_dict(config)
    configurable = _ensure_configurable(config)

    # Check if auth is disabled for development
    if settings.disable_auth:
        logger.warning(
            "AUTH DISABLED: Using development mode - no authorization required"
        )
        configurable["auth_token"] = "dev-token"
        return config

    authorization_header = req.headers.get("Authorization")
    if not authorization_header:
        raise HTTPException(status_code=401, detail="Unauthorized")
    auth_token = authorization_header.replace("Bearer ", "", 1)
    configurable["auth_token"] = auth_token
    return config


def add_user_context_to_config(config: dict | None, req: Request) -> dict:
    """Add user context information to configuration."""
    config = _ensure_config_dict(config)
    configurable = _ensure_configurable(config)

    try:
        user_context = get_user_context(req)
        configurable["user_id"] = user_context.user_id
        configurable["user_email"] = user_context.email
        configurable["org_unit_id"] = user_context.identity.org_unit_id
        configurable["user_roles"] = user_context.identity.roles
        configurable["user_permissions"] = user_context.identity.permissions
    except Exception as e:
        logger.warning(f"Failed to add user context to config: {e}")
        # Set default values if user context is not available
        configurable["user_id"] = "unknown"
        configurable["user_email"] = "unknown@example.com"
        configurable["org_unit_id"] = "unknown"
        configurable["user_roles"] = []
        configurable["user_permissions"] = []

    return config


async def validate_thread_access_and_scope(
    config: dict | None, req: Request
) -> tuple[dict, str]:
    """
    Validate thread access and create user-scoped thread ID.

    This function:
    1. If no thread_id provided: Creates a new thread for the user
    2. If thread_id provided: Validates that the user has access to the thread
    3. Creates a user-scoped thread ID for LangGraph
    4. Logs the access event for audit purposes

    Args:
        config: Configuration dictionary or Pydantic model
        req: FastAPI request object

    Returns:
        Tuple of (updated_config, user_scoped_thread_id)
    """
    # Get user context
    try:
        user_context = get_user_context(req)
        user_id = user_context.user_id
    except Exception as e:
        logger.error(f"Failed to get user context: {e}")
        raise HTTPException(status_code=401, detail="Authentication required") from e

    # Check if thread_id was provided in the original config
    original_config = _ensure_config_dict(config)
    original_configurable = original_config.get("configurable", {})
    thread_id_provided = "thread_id" in original_configurable

    # Ensure thread_id exists (generates new one if not provided)
    config, thread_id = ensure_thread_id_exists(config)

    # Get access control service
    access_control = get_thread_access_control()

    if thread_id_provided:
        # Thread ID was provided by client - validate access to existing thread
        has_access = await access_control.validate_thread_access(user_id, thread_id)

        if not has_access:
            # Log failed access attempt
            await log_thread_access_event(
                user_id=user_id,
                thread_id=thread_id,
                action="access_denied",
                success=False,
                ip_address=user_context.ip_address,
                user_agent=user_context.user_agent,
                session_id=user_context.session_id,
                request_id=user_context.request_id,
            )
            raise HTTPException(status_code=403, detail="Access denied to thread")

        logger.debug(f"User {user_id} granted access to existing thread {thread_id}")

    else:
        # No thread ID provided - create new thread for user
        try:
            # Create the thread in the access control system using our generated thread_id
            await access_control.create_thread(user_id, thread_id)

            logger.debug(f"Created new thread {thread_id} for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to create thread for user {user_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to create thread"
            ) from e

    # Create user-scoped thread ID for LangGraph
    user_scoped_thread_id = await access_control.create_user_scoped_thread_id(
        user_id, thread_id
    )

    # Update config with user-scoped thread ID
    configurable = _ensure_configurable(config)
    configurable["thread_id"] = user_scoped_thread_id

    # Log successful access/creation
    action = "thread_created" if not thread_id_provided else "access_granted"
    await log_thread_access_event(
        user_id=user_id,
        thread_id=thread_id,
        action=action,
        success=True,
        ip_address=user_context.ip_address,
        user_agent=user_context.user_agent,
        session_id=user_context.session_id,
        request_id=user_context.request_id,
    )

    logger.debug(
        f"User {user_id} {'created' if not thread_id_provided else 'granted access to'} thread {thread_id} (scoped: {user_scoped_thread_id})"
    )

    return config, user_scoped_thread_id


def default_modify_runtime_config(config: dict | None, req: Request) -> dict:
    """Default runtime configuration modification function."""
    # Add auth token
    config = add_auth_token_to_config(config, req)

    # Add user context
    config = add_user_context_to_config(config, req)

    return config


def default_validate_runtime_config(config: dict) -> BaseRuntimeConfiguration:
    """Default runtime configuration validation function."""
    return validate_runtime_config(config)


async def default_modify_runtime_config_with_access_control(
    config: dict | None, req: Request
) -> tuple[dict, str]:
    """Default runtime configuration modification with access control."""
    # Add auth token and user context
    config = default_modify_runtime_config(config, req)

    # Validate thread access and create user-scoped thread ID
    config, user_scoped_thread_id = await validate_thread_access_and_scope(config, req)

    return config, user_scoped_thread_id


async def setup_runtime_config_with_access_control(
    config: dict | None,
    req: Request,
    modify_runtime_config: Callable[[dict | None, Request], tuple[dict, str]],
    validate_runtime_config: Callable[[dict], BaseRuntimeConfiguration],
) -> tuple[dict, str]:
    """
    Set up and validate runtime configuration with access control.

    This function handles the complete runtime configuration setup process:
    1. Validates thread access
    2. Creates user-scoped thread ID
    3. Applies runtime configuration modifications
    4. Validates the final configuration

    Args:
        config: Initial configuration dictionary or Pydantic model
        req: FastAPI request object
        modify_runtime_config: Function to modify runtime configuration (returns tuple)
        validate_runtime_config: Function to validate runtime configuration

    Returns:
        Tuple of (final_config, user_scoped_thread_id)
    """
    # Apply runtime configuration modifications with access control
    config, user_scoped_thread_id = await modify_runtime_config(config, req)

    # Validate runtime configuration
    validate_runtime_config(config)

    return config, user_scoped_thread_id
