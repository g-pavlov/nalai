"""
ID generation utilities for domain-prefixed base62 IDs.

This module provides utilities for generating compact, readable IDs
with domain prefixes and reduced entropy for better UX.
"""

from typing import Literal

# Base62 alphabet (no 0, O, I, l to avoid confusion)
BASE62_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE62_BASE = len(BASE62_ALPHABET)

# Supported domain prefixes
DomainPrefix = Literal["conv", "run", "msg", "tool", "call", "task", "stream"]


def _int_to_base62(num: int, min_length: int = 0) -> str:
    """Convert integer to base62 string with minimum length padding."""
    if num == 0:
        return "1" * max(1, min_length)

    result = ""
    while num > 0:
        num, remainder = divmod(num, BASE62_BASE)
        result = BASE62_ALPHABET[remainder] + result

    # Pad to minimum length
    if len(result) < min_length:
        result = "1" * (min_length - len(result)) + result

    return result


def generate_domain_id(domain: DomainPrefix) -> str:
    """
    Generate a domain-prefixed ID using full UUID v4 entropy.

    Args:
        domain: Domain prefix (e.g., "conv", "run", "msg")

    Returns:
        Domain-prefixed ID (e.g., "conv_2b1c3d4e5f6g7h8")

    Example:
        >>> generate_domain_id("conv")
        'conv_2b1c3d4e5f6g7h8'
    """
    # Generate UUID v4 (128 bits of entropy)
    import uuid

    uuid_obj = uuid.uuid4()

    # Convert to integer
    num = uuid_obj.int

    # Convert to base62
    base62_part = _int_to_base62(num)

    return f"{domain}_{base62_part}"


def generate_conversation_id() -> str:
    """Generate a conversation ID with default entropy."""
    return generate_domain_id("conv")


def generate_run_id() -> str:
    """Generate a run ID with default entropy."""
    return generate_domain_id("run")


def generate_message_id() -> str:
    """Generate a message ID with default entropy."""
    return generate_domain_id("msg")


def generate_tool_call_id() -> str:
    """Generate a tool call ID with default entropy."""
    return generate_domain_id("tool")


def generate_stream_id() -> str:
    """Generate a stream ID with default entropy."""
    return generate_domain_id("stream")


def validate_domain_id_format(
    id_str: str, expected_domain: DomainPrefix | None = None
) -> bool:
    """
    Validate that an ID follows the domain-prefixed format.

    Args:
        id_str: ID string to validate
        expected_domain: Expected domain prefix (optional)

    Returns:
        True if valid, False otherwise
    """
    if not id_str or not isinstance(id_str, str):
        return False

    # Check for domain prefix format
    if "_" not in id_str:
        return False

    domain, base62_part = id_str.split("_", 1)

    # Validate domain prefix
    if expected_domain and domain != expected_domain:
        return False

    # Validate base62 part (only valid characters)
    if not base62_part:
        return False

    # For tool call IDs, be more lenient with character validation
    # since LangGraph/LangChain may generate IDs with different alphabets
    if expected_domain == "call" or expected_domain == "tool":
        # Accept any alphanumeric characters for tool call IDs
        if not base62_part.isalnum():
            return False
    else:
        # For other domains, use strict base62 validation
        if len(base62_part) < 20:  # Minimum reasonable length for UUID v4 base62
            return False

        for char in base62_part:
            if char not in BASE62_ALPHABET:
                return False

    return True
