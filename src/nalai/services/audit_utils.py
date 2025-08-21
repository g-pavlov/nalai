"""
Audit utility functions for API Assistant.

This module contains utility functions for audit logging that can be imported
without causing circular dependencies.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def log_conversation_access_event(
    user_id: str,
    conversation_id: str,
    action: str,
    success: bool = True,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> None:
    """Log a conversation access event using the global audit service."""
    logger.debug(
        f"log_conversation_access_event called with: user_id={user_id}, conversation_id={conversation_id}, action={action}, success={success}"
    )

    # Validate metadata
    if metadata is not None and not isinstance(metadata, dict):
        logger.error(
            f"Metadata is not a dict! Type: {type(metadata)}, Value: {metadata}"
        )
        metadata = {}

    # Lazy import to avoid circular dependency
    from .audit_service import get_audit_service

    audit_service = get_audit_service()

    # Use thread access as the underlying mechanism (conversations are threads)
    await audit_service.log_thread_access(
        user_id=user_id,
        thread_id=conversation_id,
        action=action,
        success=success,
        metadata=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
        request_id=request_id,
    )
