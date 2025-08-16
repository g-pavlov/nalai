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
        thread_id: Thread ID to validate

    Raises:
        ValueError: If thread ID format is invalid
    """
    if not thread_id or not isinstance(thread_id, str):
        raise ValueError("thread_id must be a non-empty string")

    # Check for potentially malicious patterns
    if len(thread_id) > 200:  # Reasonable length limit
        raise ValueError("thread_id too long (max 200 characters)")

    # Check if it's a user-scoped thread ID (format: user:{user_id}:{uuid})
    if ":" in thread_id:
        parts = thread_id.split(":")
        if len(parts) != 3:
            raise ValueError(
                "Invalid user-scoped thread_id format. Expected: user:{user_id}:{uuid}"
            )

        if parts[0] != "user":
            raise ValueError(
                "Invalid user-scoped thread_id format. Must start with 'user:'"
            )

        # Validate user_id part (should be non-empty and not contain colons)
        user_id = parts[1]
        if not user_id or ":" in user_id:
            raise ValueError("Invalid user_id in thread_id format")

        # Validate UUID part
        try:
            uuid.UUID(parts[2], version=4)
        except ValueError as err:
            raise ValueError("Invalid UUID in user-scoped thread_id") from err

        return

    # Check if it's a plain UUID4
    try:
        uuid_obj = uuid.UUID(thread_id, version=4)
        if str(uuid_obj) != thread_id:
            raise ValueError("thread_id must be a canonical UUID4 string")
    except ValueError as err:
        raise ValueError(
            "thread_id must be a valid UUID4 or user-scoped thread ID (user:{user_id}:{uuid})"
        ) from err
