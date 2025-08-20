"""
Validation utilities for API Assistant.

This module contains validation functions that are used across multiple modules
to avoid circular imports.
"""

import uuid


def validate_thread_id_format(thread_id: str) -> None:
    """
    Validate thread ID format for security and consistency.

    This function validates that thread IDs follow the expected format
    to prevent injection attacks and ensure data consistency.

    Args:
        thread_id: Thread ID to validate (must be a valid UUID4)

    Raises:
        ValueError: If thread ID format is invalid
    """
    if not thread_id or not isinstance(thread_id, str):
        raise ValueError("thread_id must be a non-empty string")

    # Check for potentially malicious patterns
    if len(thread_id) > 200:  # Reasonable length limit
        raise ValueError("thread_id too long (max 200 characters)")

    # Check if it's a valid UUID4
    try:
        uuid_obj = uuid.UUID(thread_id, version=4)
        if str(uuid_obj) != thread_id:
            raise ValueError("thread_id must be a canonical UUID4 string")
    except ValueError as err:
        raise ValueError("thread_id must be a valid UUID4") from err
