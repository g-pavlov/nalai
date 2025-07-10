"""
Runtime configuration utilities for API Assistant server.

This module contains functions for managing runtime configuration,
thread IDs, and validation.
"""

import logging
import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request

from ..config import BaseRuntimeConfiguration, settings
from .models.validation import validate_runtime_config

logger = logging.getLogger("api-assistant")


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
    # Convert Pydantic model to dict if needed
    if config is not None and hasattr(config, "model_dump"):
        config = config.model_dump()

    config = config or {}
    configurable = config.setdefault("configurable", {})

    # Ensure configurable is a dictionary, not None
    if configurable is None:
        configurable = {}
        config["configurable"] = configurable

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


def add_thread_id_to_config(config: dict | None, thread_id: str) -> dict:
    """Update config with thread_id."""
    # Convert Pydantic model to dict if needed
    if config is not None and hasattr(config, "model_dump"):
        config = config.model_dump()

    config = config or {}
    configurable = config.setdefault("configurable", {})

    # Ensure configurable is a dictionary, not None
    if configurable is None:
        configurable = {}
        config["configurable"] = configurable

    configurable["thread_id"] = thread_id
    return config


def add_auth_token_to_config(config: dict | None, req: Request) -> dict:
    """Set auth token from request headers."""
    # Convert Pydantic model to dict if needed
    if config is not None and hasattr(config, "model_dump"):
        config = config.model_dump()

    config = config or {}
    configurable = config.setdefault("configurable", {})

    # Ensure configurable is a dictionary, not None
    if configurable is None:
        configurable = {}
        config["configurable"] = configurable

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


def add_user_email_to_config(config: dict | None, req: Request) -> dict:
    """Set user email from request state."""
    # Convert Pydantic model to dict if needed
    if config is not None and hasattr(config, "model_dump"):
        config = config.model_dump()

    config = config or {}
    configurable = config.setdefault("configurable", {})

    # Ensure configurable is a dictionary, not None
    if configurable is None:
        configurable = {}
        config["configurable"] = configurable

    email = getattr(req.state, "user_email", None)
    configurable["user_email"] = email
    return config


def modify_runtime_config(config: dict | None, req: Request) -> dict:
    """Apply runtime configuration modifications."""
    config = add_auth_token_to_config(config, req)
    config = add_user_email_to_config(config, req)
    return config


def validate_runtime_config_strict(config: dict) -> BaseRuntimeConfiguration:
    """
    Strict runtime configuration validator that raises HTTPException on validation errors.

    This is different from the lenient validate_runtime_config in validators.py
    which returns a default configuration on validation failure.

    Args:
        config: Configuration dictionary

    Returns:
        Validated BaseRuntimeConfiguration instance

    Raises:
        HTTPException: If validation fails
    """
    try:
        configurable = config.get("configurable", {})
        return BaseRuntimeConfiguration(**configurable)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid runtime configuration: {str(e)}"
        ) from e


def default_modify_runtime_config(config: dict | None, request: Request) -> dict:
    """
    Default implementation that returns config unchanged.

    This function can be overridden to modify runtime configuration
    based on request context (e.g., authentication, headers, etc.).

    Args:
        config: Configuration dictionary or Pydantic model
        request: FastAPI request object

    Returns:
        Modified configuration dictionary
    """
    # Convert Pydantic model to dict if needed
    if config is not None and hasattr(config, "model_dump"):
        config = config.model_dump()

    return config or {}


def default_validate_runtime_config(config: dict):
    """
    Default runtime configuration validator using Pydantic.

    This is a wrapper around the validate_runtime_config function
    to maintain backward compatibility.

    Args:
        config: Configuration dictionary

    Returns:
        Validated BaseRuntimeConfiguration instance
    """
    return validate_runtime_config(config)


def setup_runtime_config(
    config: dict | None,
    req: Request,
    modify_runtime_config: Callable[[dict | None, Request], dict],
    validate_runtime_config: Callable[[dict], BaseRuntimeConfiguration],
) -> tuple[dict, str]:
    """
    Set up and validate runtime configuration.

    This function handles the complete runtime configuration setup process:
    1. Ensures thread_id exists
    2. Applies runtime configuration modifications
    3. Validates the final configuration

    Args:
        config: Initial configuration dictionary or Pydantic model
        req: FastAPI request object
        modify_runtime_config: Function to modify runtime configuration
        validate_runtime_config: Function to validate runtime configuration

    Returns:
        Tuple of (final_config, thread_id)
    """
    # Ensure thread_id exists
    config, thread_id = ensure_thread_id_exists(config)

    # Apply runtime configuration modifications
    config = modify_runtime_config(config, req)

    # Validate runtime configuration
    validate_runtime_config(config)

    return config, thread_id
