"""
PII Masking Utilities for API Assistant.

This module provides utilities for masking Personally Identifiable Information (PII)
in logs and audit trails to ensure compliance with privacy regulations.
"""

import logging
import re
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)


def mask_pii(value: Any, pii_type: str) -> str:
    """
    Mask PII values for logging and audit trails.

    Args:
        value: The value to mask
        pii_type: Type of PII (email, name, ip_address, etc.)

    Returns:
        Masked value that preserves format but obscures sensitive data
    """
    # Handle None and non-string values
    if value is None:
        return "***"

    # Convert to string for processing
    value_str = str(value)

    # For email type, handle special values that should not be masked
    if pii_type == "email" and (
        not value_str or value_str == "unknown" or value_str == "anonymous"
    ):
        return value_str

    # Check if PII masking is globally disabled
    if not settings.audit_mask_pii:
        return value_str

    try:
        if pii_type == "email":
            # For email type, only call mask_email if it looks like an email
            if "@" in value_str:
                return mask_email(value_str)
            else:
                return "***"
        elif pii_type == "name":
            return mask_name(value_str)
        elif pii_type == "ip_address":
            return mask_ip_address(value_str)
        elif pii_type == "phone":
            return mask_phone(value_str)
        elif pii_type == "user_id":
            return mask_user_id(value_str)
        else:
            # For unknown PII types, apply generic masking
            return mask_generic(value_str)
    except Exception as e:
        logger.warning(f"Failed to mask PII of type {pii_type}: {e}")
        return "***"


def mask_email(email: str) -> str:
    """
    Mask email addresses while preserving domain for debugging.

    Args:
        email: Email address to mask

    Returns:
        Masked email address (e.g., "jo***@example.com")
    """
    if not settings.audit_mask_emails:
        return email

    # Handle special values that should not be masked
    if not email or email == "unknown" or email == "anonymous":
        return email

    if "@" not in email:
        return "***@***"

    try:
        username, domain = email.split("@", 1)
        if len(username) <= 2:
            masked_username = "***"
        else:
            masked_username = f"{username[:2]}***"

        return f"{masked_username}@{domain}"
    except Exception:
        return "***@***"


def mask_name(name: str) -> str:
    """
    Mask personal names while preserving initials.

    Args:
        name: Name to mask

    Returns:
        Masked name (e.g., "J*** S***" for "John Smith")
    """
    if not settings.audit_mask_names:
        return name

    if not name or len(name.strip()) == 0:
        return "***"

    try:
        # Handle full names with spaces
        if " " in name:
            parts = name.split()
            masked_parts = []
            for part in parts:
                if len(part) <= 1:
                    masked_parts.append("***")
                else:
                    masked_parts.append(f"{part[0]}***")
            return " ".join(masked_parts)
        else:
            # Single name
            if len(name) <= 2:
                return "***"
            else:
                return f"{name[0]}***"
    except Exception:
        return "***"


def mask_ip_address(ip_address: str) -> str:
    """
    Mask IP addresses while preserving network information.

    Args:
        ip_address: IP address to mask

    Returns:
        Masked IP address (e.g., "192.168.1.***" for "192.168.1.100")
    """
    if not settings.audit_mask_ip_addresses:
        return ip_address

    if not ip_address:
        return "***"

    try:
        # IPv4 address
        if "." in ip_address:
            parts = ip_address.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.***"

        # IPv6 address (simplified masking)
        if ":" in ip_address:
            return "****:****:****:****:****:****:****:****"

        return "***"
    except Exception:
        return "***"


def mask_phone(phone: str) -> str:
    """
    Mask phone numbers while preserving country code.

    Args:
        phone: Phone number to mask

    Returns:
        Masked phone number (e.g., "+1-555-***-1234")
    """
    if not phone:
        return "***"

    try:
        # Remove all non-digit characters for processing
        digits = re.sub(r"\D", "", phone)

        if len(digits) <= 4:
            return "***"
        elif len(digits) <= 7:
            return f"{digits[:3]}-***"
        else:
            # For longer numbers, preserve area code and last 4 digits
            # Format: XXX-XXX-***-XXXX
            # Handle the case where we have exactly 10 digits (US format)
            if len(digits) == 10:
                return f"{digits[:3]}-{digits[3:6]}-***-{digits[-4:]}"
            elif len(digits) == 11:
                # Handle 11-digit numbers (country code + 10 digits)
                # Format: XXX-XXX-***-XXXX (ignore country code)
                return f"{digits[1:4]}-{digits[4:7]}-***-{digits[-4:]}"
            else:
                # For other lengths, preserve first 3, middle 3, and last 4
                return f"{digits[:3]}-{digits[3:6]}-***-{digits[-4:]}"
    except Exception:
        return "***"


def mask_user_id(user_id: str) -> str:
    """
    Mask user IDs while preserving some structure for debugging.

    Args:
        user_id: User ID to mask

    Returns:
        Masked user ID (e.g., "user-***-123" for "user-abc-123")
    """
    if not user_id or len(user_id) <= 3:
        return "***"

    try:
        # If user_id contains hyphens or underscores, preserve structure
        if "-" in user_id:
            parts = user_id.split("-")
            if len(parts) >= 2:
                return f"{parts[0]}-***-{parts[-1]}"
        elif "_" in user_id:
            parts = user_id.split("_")
            if len(parts) >= 2:
                return f"{parts[0]}_***_{parts[-1]}"

        # Generic masking for other formats
        if len(user_id) <= 6:
            return f"{user_id[:2]}***{user_id[-2:]}"
        else:
            return f"{user_id[:2]}***{user_id[-2:]}"
    except Exception:
        return "***"


def mask_generic(value: str) -> str:
    """
    Apply generic masking to unknown PII types.

    Args:
        value: Value to mask

    Returns:
        Masked value
    """
    if not value or len(value) <= 2:
        return "***"

    try:
        if len(value) <= 4:
            return f"{value[0]}***"
        else:
            return f"{value[:2]}***{value[-1:]}"
    except Exception:
        return "***"


def mask_dict_pii(
    data: dict[str, Any], pii_fields: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Mask PII fields in a dictionary.

    Args:
        data: Dictionary containing potentially sensitive data
        pii_fields: Mapping of field names to PII types (e.g., {"email": "email", "name": "name"})

    Returns:
        Dictionary with PII fields masked
    """
    if not data:
        return data

    # Default PII field mappings
    default_pii_fields = {
        "email": "email",
        "user_email": "email",
        "given_name": "name",
        "family_name": "name",
        "full_name": "name",
        "name": "name",
        "ip_address": "ip_address",
        "ip": "ip_address",
        "phone": "phone",
        "phone_number": "phone",
        "user_id": "user_id",
        "userid": "user_id",
    }

    pii_fields = pii_fields or default_pii_fields
    masked_data = data.copy()

    for field_name, field_value in masked_data.items():
        if field_name in pii_fields and isinstance(field_value, str):
            pii_type = pii_fields[field_name]
            masked_data[field_name] = mask_pii(field_value, pii_type)

    return masked_data


def mask_audit_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Mask PII in audit metadata.

    Args:
        metadata: Audit metadata dictionary

    Returns:
        Metadata with PII fields masked
    """
    if not metadata:
        return metadata

    # Define PII fields commonly found in audit metadata
    pii_fields = {
        "email": "email",
        "user_email": "email",
        "given_name": "name",
        "family_name": "name",
        "full_name": "name",
        "name": "name",
        "ip_address": "ip_address",
        "ip": "ip_address",
        "phone": "phone",
        "phone_number": "phone",
        "user_id": "user_id",
        "userid": "user_id",
    }

    return mask_dict_pii(metadata, pii_fields)


def is_pii_field(field_name: str) -> bool:
    """
    Check if a field name likely contains PII.

    Args:
        field_name: Field name to check

    Returns:
        True if field likely contains PII
    """
    pii_indicators = [
        "email",
        "name",
        "phone",
        "address",
        "ssn",
        "passport",
        "license",
        "credit_card",
        "card_number",
        "account",
        "social",
        "birth",
        "age",
        "gender",
        "race",
        "ethnicity",
        "religion",
        "political",
        "biometric",
    ]

    field_lower = field_name.lower()
    return any(indicator in field_lower for indicator in pii_indicators)
