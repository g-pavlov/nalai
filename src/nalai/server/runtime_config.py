"""
Runtime configuration utilities for API Assistant server.

This module contains functions for managing runtime configuration,
conversation IDs, and validation with access control integration.
"""

import logging

from fastapi import HTTPException, Request

from ..config import BaseRuntimeConfiguration, settings
from ..core import create_user_scoped_conversation_id
from ..server.middleware import get_user_context

logger = logging.getLogger("nalai")

# Constants
DEV_AUTH_TOKEN = "dev-token"
UNKNOWN_USER_ID = "unknown"
UNKNOWN_USER_EMAIL = "unknown@example.com"
UNKNOWN_ORG_UNIT = "unknown"


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


def validate_runtime_config(config: dict) -> BaseRuntimeConfiguration:
    """
    Validate runtime configuration using Pydantic.

    Args:
        config: Configuration dictionary

    Returns:
        Validated BaseRuntimeConfiguration instance

    Note:
        This function is designed to be lenient - if validation fails,
        it returns a default configuration rather than raising an exception.
        This allows the application to continue even with invalid config.
    """
    try:
        configurable = config.get("configurable", {})
        return BaseRuntimeConfiguration(**configurable)
    except Exception as e:
        # For default implementation, just return the config as-is
        # This allows the application to continue even with invalid config
        logger.warning(f"Runtime config validation failed, using config as-is: {e}")
        return BaseRuntimeConfiguration()


def add_auth_token_to_config(config: dict | None, req: Request) -> dict:
    """Set auth token from request headers."""
    config = _ensure_config_dict(config)
    configurable = _ensure_configurable(config)

    # Check if auth is disabled for development
    if not settings.auth_enabled:
        logger.warning(
            "AUTH DISABLED: Using development mode - no authorization required"
        )
        configurable["auth_token"] = DEV_AUTH_TOKEN
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

        # If auth is disabled, use dev identity instead of unknown
        if not settings.auth_enabled:
            from ..services.auth_service import get_auth_service

            try:
                auth_service = get_auth_service()
                dev_identity = auth_service._create_dev_identity()
                configurable["user_id"] = dev_identity.user_id
                configurable["user_email"] = dev_identity.email
                configurable["org_unit_id"] = dev_identity.org_unit_id
                configurable["user_roles"] = dev_identity.roles
                configurable["user_permissions"] = dev_identity.permissions
            except Exception as auth_error:
                logger.warning(f"Failed to create dev identity: {auth_error}")
                # Fall back to unknown values
                configurable["user_id"] = UNKNOWN_USER_ID
                configurable["user_email"] = UNKNOWN_USER_EMAIL
                configurable["org_unit_id"] = UNKNOWN_ORG_UNIT
                configurable["user_roles"] = []
                configurable["user_permissions"] = []
        else:
            # Set default values if user context is not available
            configurable["user_id"] = UNKNOWN_USER_ID
            configurable["user_email"] = UNKNOWN_USER_EMAIL
            configurable["org_unit_id"] = UNKNOWN_ORG_UNIT
            configurable["user_roles"] = []
            configurable["user_permissions"] = []

    return config


def add_no_cache_header_to_config(config: dict | None, req: Request) -> dict:
    """Add no-cache setting from request header to configuration."""
    config = _ensure_config_dict(config)
    configurable = _ensure_configurable(config)

    # Check for X-No-Cache header
    no_cache_header = req.headers.get("X-No-Cache", "").lower()
    if no_cache_header in ("true", "1", "yes"):
        configurable["cache_disabled"] = True
        logger.debug("No-cache header detected - disabling cache for this request")
    else:
        configurable["cache_disabled"] = False

    return config


def add_thread_id_to_config(config: dict | None, conversation_id: str) -> dict:
    """Add thread_id to configuration if user_id is available."""
    config = _ensure_config_dict(config)
    configurable = _ensure_configurable(config)

    user_id = configurable.get("user_id")
    if user_id:
        configurable["thread_id"] = create_user_scoped_conversation_id(
            user_id, conversation_id
        )
        logger.debug(f"Added thread_id for conversation: {conversation_id}")
    else:
        logger.warning("Cannot add thread_id: user_id not available in config")

    return config


def create_runtime_config(req: Request, conversation_id: str = None) -> dict:
    """Create agent configuration with runtime modifications."""
    # Start with empty config
    config = {"configurable": {}}

    # Add auth token
    config = add_auth_token_to_config(config, req)

    # Add user context
    config = add_user_context_to_config(config, req)

    # Add thread_id if conversation_id provided
    if conversation_id:
        config = add_thread_id_to_config(config, conversation_id)

    # Add no-cache header setting
    config = add_no_cache_header_to_config(config, req)

    # Validate the final configuration
    validate_runtime_config(config)

    return config
