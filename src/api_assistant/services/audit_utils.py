"""
Audit utility functions for API Assistant.

This module contains utility functions for audit logging that can be imported
without causing circular dependencies.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def log_thread_access_event(
    user_id: str,
    thread_id: str,
    action: str,
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None
) -> None:
    """Log a thread access event using the global audit service."""
    logger.debug(f"log_thread_access_event called with: user_id={user_id}, thread_id={thread_id}, action={action}, success={success}, metadata={metadata}, ip_address={ip_address}, user_agent={user_agent}, session_id={session_id}, request_id={request_id}")
    logger.debug(f"Metadata type: {type(metadata)}, value: {metadata}")
    if metadata is not None and not isinstance(metadata, dict):
        logger.error(f"Metadata is not a dict! Type: {type(metadata)}, Value: {metadata}")
        metadata = {}
    
    # Lazy import to avoid circular dependency
    from .audit_service import get_audit_service
    audit_service = get_audit_service()
    await audit_service.log_thread_access(
        user_id=user_id,
        thread_id=thread_id,
        action=action,
        success=success,
        metadata=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
        request_id=request_id
    ) 