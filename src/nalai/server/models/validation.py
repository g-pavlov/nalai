"""
Validation utilities for API Assistant server.

This module contains functions for validating input data, requests,
and configuration parameters used by the API endpoints.
"""

import logging

from fastapi import HTTPException
from langchain_core.messages import BaseMessage, HumanMessage

from ...config import BaseRuntimeConfiguration
from .input import MessageInput

logger = logging.getLogger("nalai")


def validate_agent_input(messages: list, max_size: int = 100 * 1024) -> None:
    """
    Validate agent input messages and size.

    Args:
        messages: List of input messages to validate (either API format or LangChain format)
        max_size: Maximum allowed input size in bytes (default: 100KB)

    Raises:
        HTTPException: If validation fails
    """
    if not messages:
        raise HTTPException(status_code=400, detail="Input messages cannot be empty")

    # Check if we have LangChain messages or API messages
    if messages and isinstance(messages[0], BaseMessage):
        # LangChain message format
        validate_langchain_messages(messages)
    else:
        # API message format
        validate_api_messages(messages)

    # Validate input size (reasonable limit to prevent abuse)
    input_str = str(messages)
    if len(input_str) > max_size:
        raise HTTPException(
            status_code=400, detail=f"Input too large (max {max_size // 1000}KB)"
        )


def validate_langchain_messages(messages: list[BaseMessage]) -> None:
    """
    Validate a list of LangChain messages.

    Args:
        messages: List of LangChain messages to validate

    Raises:
        HTTPException: If validation fails
    """
    if not messages:
        raise HTTPException(status_code=400, detail="Input messages cannot be empty")

    # Ensure at least one human message
    human_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
    if not human_messages:
        raise HTTPException(
            status_code=400, detail="At least one human message is required"
        )

    # Validate message content
    for i, msg in enumerate(messages):
        if not msg.content or not str(msg.content).strip():
            raise HTTPException(
                status_code=400, detail=f"Message {i + 1} content cannot be empty"
            )
        if len(str(msg.content)) > 10000:  # 10KB limit per message
            raise HTTPException(
                status_code=400, detail=f"Message {i + 1} content too long (max 10KB)"
            )


def validate_api_messages(messages: list[MessageInput]) -> None:
    """
    Validate a list of API format messages.

    Args:
        messages: List of API format messages to validate

    Raises:
        HTTPException: If validation fails
    """
    if not messages:
        raise HTTPException(status_code=400, detail="Input messages cannot be empty")

    # Ensure at least one human message
    human_messages = [msg for msg in messages if msg.type == "human"]
    if not human_messages:
        raise HTTPException(
            status_code=400, detail="At least one human message is required"
        )

    # Validate message content
    for i, msg in enumerate(messages):
        if not msg.content or not msg.content.strip():
            raise HTTPException(
                status_code=400, detail=f"Message {i + 1} content cannot be empty"
            )
        if len(msg.content) > 10000:  # 10KB limit per message
            raise HTTPException(
                status_code=400, detail=f"Message {i + 1} content too long (max 10KB)"
            )


def validate_tool_interrupt_response_type(response_type: str) -> None:
    """
    Validate tool interrupt response type.

    Args:
        response_type: Response type to validate

    Raises:
        HTTPException: If response type is invalid
    """
    valid_response_types = ["accept", "edit", "response"]
    if response_type not in valid_response_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid response type. Choose from: {', '.join(valid_response_types)}",
        )


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
