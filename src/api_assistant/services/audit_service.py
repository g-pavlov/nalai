"""
Audit service for API Assistant.

This module provides access event logging with identity-resource-action-time
granularity for compliance and monitoring.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..config import settings
from ..server.models.identity import AccessEvent
from ..utils.pii_masking import mask_audit_metadata, mask_pii

logger = logging.getLogger(__name__)


class AuditBackend(ABC):
    """Abstract base class for audit backends."""

    @abstractmethod
    async def log_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        metadata: dict[str, Any] | None = None,
        success: bool = True,
    ) -> None:
        """Log an access event with individual parameters."""
        pass

    @abstractmethod
    async def get_events(
        self,
        user_id: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[AccessEvent]:
        """Retrieve access events with optional filtering."""
        pass

    @abstractmethod
    async def get_user_events(
        self, user_id: str, limit: int = 100
    ) -> list[AccessEvent]:
        """Get events for a specific user."""
        pass


class InMemoryAuditBackend(AuditBackend):
    """In-memory audit backend for development and testing."""

    def __init__(self, max_entries: int = 10000):
        """Initialize in-memory audit backend."""
        self._audit_log: list[AccessEvent] = []
        self.max_entries = max_entries
        logger.debug(
            f"In-memory audit backend initialized with max_entries={max_entries}"
        )

    async def log_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        metadata: dict[str, Any] | None = None,
        success: bool = True,
    ) -> None:
        """Log an access event with individual parameters."""
        logger.debug(
            f"Creating AccessEvent with user_id={user_id}, resource={resource}, action={action}, success={success}, metadata={metadata}"
        )
        logger.debug(f"Metadata type: {type(metadata)}, value: {metadata}")
        if metadata is not None and not isinstance(metadata, dict):
            logger.error(
                f"Metadata is not a dict! Type: {type(metadata)}, Value: {metadata}"
            )
            metadata = {}

        # Mask PII in metadata before storing
        masked_metadata = mask_audit_metadata(metadata) if metadata else {}

        event = AccessEvent(
            user_id=user_id,
            resource=resource,
            action=action,
            success=success,
            metadata=masked_metadata,
        )
        self._audit_log.append(event)

        # Maintain max entries limit
        if len(self._audit_log) > self.max_entries:
            # Remove oldest entries
            excess = len(self._audit_log) - self.max_entries
            self._audit_log = self._audit_log[excess:]
            logger.debug(f"Removed {excess} old audit entries to maintain limit")

        # Log to dedicated audit stream with structured data
        audit_logger = logging.getLogger("api_assistant.audit")
        audit_data = {
            "action": action,
            "user_id": user_id,
            "resource": resource,
            "success": success,
            "metadata": masked_metadata,
        }
        audit_logger.info(json.dumps(audit_data))

        logger.debug(f"Logged access event: {user_id} -> {resource} -> {action}")

    async def get_events(
        self,
        user_id: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[AccessEvent]:
        """Retrieve access events with optional filtering."""
        events = self._audit_log.copy()

        # Apply filters
        if user_id:
            events = [e for e in events if e.user_id == user_id]

        if resource:
            events = [e for e in events if e.resource == resource]

        if action:
            events = [e for e in events if e.action == action]

        # Handle time filters with backward compatibility
        if start_time or after:
            filter_time = start_time or after
            events = [e for e in events if e.timestamp >= filter_time]

        if end_time or before:
            filter_time = end_time or before
            events = [e for e in events if e.timestamp <= filter_time]

        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def get_user_events(
        self, user_id: str, limit: int = 100
    ) -> list[AccessEvent]:
        """Get events for a specific user."""
        return await self.get_events(user_id=user_id, limit=limit)


class ExternalAuditBackend(AuditBackend):
    """External audit service backend."""

    def __init__(self, service_url: str):
        """Initialize external audit backend."""
        self.service_url = service_url
        # TODO: Implement HTTP client for external audit service
        logger.info(f"External audit backend initialized with URL: {service_url}")

    async def log_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        metadata: dict[str, Any] | None = None,
        success: bool = True,
    ) -> None:
        """Log an access event to external service with individual parameters."""
        # Mask PII in metadata before sending to external service
        masked_metadata = mask_audit_metadata(metadata) if metadata else {}

        event = AccessEvent(
            user_id=user_id,
            resource=resource,
            action=action,
            success=success,
            metadata=masked_metadata,
        )
        # TODO: Implement HTTP POST to external audit service
        logger.debug(f"Would log to external service: {event.to_audit_entry()}")

    async def get_events(
        self,
        user_id: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[AccessEvent]:
        """Retrieve access events from external service."""
        raise NotImplementedError("External audit backend not implemented")

    async def get_user_events(
        self, user_id: str, limit: int = 100
    ) -> list[AccessEvent]:
        """Get events for a specific user from external service."""
        raise NotImplementedError("External audit backend not implemented")


class AuditService:
    """Audit service with backend abstraction."""

    def __init__(self, backend: str = "memory", config: dict[str, Any] | None = None):
        """Initialize audit service."""
        self.backend_type = backend
        self.config = config or {}

        if backend == "memory":
            max_entries = self.config.get("max_entries", settings.audit_max_entries)
            self.backend = InMemoryAuditBackend(max_entries=max_entries)
        elif backend == "external":
            service_url = self.config.get("service_url", settings.audit_external_url)
            if not service_url:
                raise ValueError("External audit service URL not configured")
            raise NotImplementedError("External audit backend not implemented")
        else:
            raise ValueError(f"Unsupported audit backend: {backend}")

        logger.debug(f"Audit service initialized with backend: {backend}")

    async def log_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        metadata: dict[str, Any] | None = None,
        success: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log an access event with identity-resource-action-time granularity."""
        # Add additional metadata if provided
        full_metadata = metadata or {}
        if ip_address:
            # Mask IP address if configured
            masked_ip = (
                mask_pii(ip_address, "ip_address")
                if settings.audit_mask_ip_addresses
                else ip_address
            )
            full_metadata["ip_address"] = masked_ip
        if user_agent:
            full_metadata["user_agent"] = user_agent
        if session_id:
            full_metadata["session_id"] = session_id
        if request_id:
            full_metadata["request_id"] = request_id

        await self.backend.log_access(
            user_id, resource, action, full_metadata, success=success
        )

    async def log_thread_access(
        self,
        user_id: str,
        thread_id: str,
        action: str,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log thread access event."""
        # Log to dedicated audit stream with structured data
        audit_logger = logging.getLogger("api_assistant.audit")
        audit_data = {
            "action": action,
            "user_id": user_id,
            "thread_id": thread_id,
            "success": success,
            "metadata": metadata or {},
        }
        audit_logger.info(json.dumps(audit_data))

        resource = f"thread:{thread_id}"
        await self.log_access(
            user_id,
            resource,
            action,
            metadata,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
        )

    async def log_api_access(
        self,
        user_id: str,
        api_endpoint: str,
        action: str,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log API endpoint access event."""
        resource = f"api:{api_endpoint}"
        await self.log_access(
            user_id,
            resource,
            action,
            metadata,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
        )

    async def log_request_start(
        self,
        user_id: str,
        method: str,
        path: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log the start of an HTTP request."""
        # Log to dedicated audit stream with structured data
        audit_logger = logging.getLogger("api_assistant.audit")
        audit_data = {
            "action": "request_start",
            "user_id": user_id,
            "method": method,
            "path": path,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
            "request_id": request_id,
        }
        audit_logger.info(json.dumps(audit_data))

        resource = f"http:{method}:{path}"
        metadata = {"request_type": "start", "timestamp": datetime.now().isoformat()}
        await self.log_access(
            user_id,
            resource,
            "request_start",
            metadata,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
        )

    async def log_request_complete(
        self,
        user_id: str,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log the completion of an HTTP request."""
        # Log to dedicated audit stream with structured data
        audit_logger = logging.getLogger("api_assistant.audit")
        audit_data = {
            "action": "request_complete",
            "user_id": user_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": int(duration * 1000),
            "success": 200 <= status_code < 400,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": session_id,
            "request_id": request_id,
        }
        audit_logger.info(json.dumps(audit_data))

        resource = f"http:{method}:{path}"
        success = 200 <= status_code < 400
        metadata = {
            "request_type": "complete",
            "status_code": status_code,
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat(),
        }
        await self.log_access(
            user_id,
            resource,
            "request_complete",
            metadata,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
        )

    async def get_events(
        self,
        user_id: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[AccessEvent]:
        """Retrieve access events with optional filtering."""
        return await self.backend.get_events(
            user_id=user_id,
            resource=resource,
            action=action,
            start_time=start_time,
            end_time=end_time,
            before=before,
            after=after,
            limit=limit,
        )

    async def get_user_events(
        self, user_id: str, limit: int = 100
    ) -> list[AccessEvent]:
        """Get events for a specific user."""
        return await self.backend.get_user_events(user_id, limit)

    async def get_thread_events(
        self, thread_id: str, limit: int = 100
    ) -> list[AccessEvent]:
        """Get events for a specific thread."""
        resource = f"thread:{thread_id}"
        return await self.get_events(resource=resource, limit=limit)


# Global audit service instance
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Get the global audit service instance."""
    global _audit_service
    if _audit_service is None:
        # Use concrete default values to avoid MagicMock issues
        config = {"max_entries": 10000, "service_url": None}
        _audit_service = AuditService(backend="memory", config=config)
    return _audit_service


def set_audit_service(audit_service: AuditService) -> None:
    """Set the global audit service instance."""
    global _audit_service
    _audit_service = audit_service


async def log_access_event(
    user_id: str,
    resource: str,
    action: str,
    metadata: dict[str, Any] | None = None,
    success: bool = True,
    **kwargs,
) -> None:
    """Log an access event using the global audit service."""
    audit_service = get_audit_service()
    await audit_service.log_access(
        user_id, resource, action, metadata, success=success, **kwargs
    )
