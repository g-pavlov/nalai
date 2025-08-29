"""
Validation utilities for API Assistant.

This module contains validation functions that are used across multiple modules
to avoid circular imports.
"""

from .id_generator import validate_domain_id_format


def validate_thread_id_format(thread_id: str) -> None:
    """
    Validate thread ID format for security and consistency.

    This function validates that thread IDs follow the expected format
    to prevent injection attacks and ensure data consistency.

    Args:
        thread_id: Thread ID to validate (must be a valid domain-prefixed format)

    Raises:
        ValueError: If thread ID format is invalid
    """
    if not thread_id or not isinstance(thread_id, str):
        raise ValueError("thread_id must be a non-empty string")

    # Check for potentially malicious patterns
    if len(thread_id) > 200:  # Reasonable length limit
        raise ValueError("thread_id too long (max 200 characters)")

    # Check if it's a valid domain-prefixed ID
    if not validate_domain_id_format(thread_id, "conv"):
        raise ValueError("thread_id must be a valid domain-prefixed format: conv_xxx")
