"""
Thread access control service for API Assistant.

This module provides thread ownership validation and management,
ensuring users can only access their own threads.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..config import settings
from ..server.models.identity import ThreadOwnership

logger = logging.getLogger(__name__)


class ThreadAccessControlBackend(ABC):
    """Abstract base class for thread access control backends."""

    @abstractmethod
    async def validate_thread_access(self, user_id: str, thread_id: str) -> bool:
        """Validate that user owns the thread."""
        pass

    @abstractmethod
    async def create_thread(
        self, user_id: str, thread_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Record thread ownership."""
        pass

    @abstractmethod
    async def list_user_threads(self, user_id: str) -> list[ThreadOwnership]:
        """List all threads owned by a user."""
        pass

    @abstractmethod
    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """Delete thread ownership record."""
        pass

    @abstractmethod
    async def update_thread_access(self, user_id: str, thread_id: str) -> None:
        """Update last access timestamp for thread."""
        pass


class InMemoryThreadAccessControl(ThreadAccessControlBackend):
    """In-memory thread access control backend."""

    def __init__(self):
        """Initialize in-memory backend."""
        self._thread_ownership: dict[str, ThreadOwnership] = {}
        logger.debug("In-memory thread access control initialized")

    async def validate_thread_access(self, user_id: str, thread_id: str) -> bool:
        """Validate that user owns the thread."""
        ownership = self._thread_ownership.get(thread_id)
        if not ownership:
            logger.warning(f"Thread {thread_id} not found")
            return False

        is_owner = ownership.user_id == user_id
        if is_owner:
            # Update last access timestamp
            await self.update_thread_access(user_id, thread_id)
            logger.debug(f"User {user_id} validated access to thread {thread_id}")
        else:
            logger.warning(
                f"User {user_id} denied access to thread {thread_id} (owner: {ownership.user_id})"
            )

        return is_owner

    async def create_thread(
        self, user_id: str, thread_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Record thread ownership."""
        if thread_id in self._thread_ownership:
            existing_owner = self._thread_ownership[thread_id].user_id
            if existing_owner != user_id:
                raise ValueError(
                    f"Thread {thread_id} already owned by user {existing_owner}"
                )
            logger.debug(f"Thread {thread_id} already exists for user {user_id}")
            return

        ownership = ThreadOwnership(
            thread_id=thread_id, user_id=user_id, metadata=metadata or {}
        )
        self._thread_ownership[thread_id] = ownership
        logger.info(f"Created thread {thread_id} for user {user_id}")

    async def list_user_threads(self, user_id: str) -> list[ThreadOwnership]:
        """List all threads owned by a user."""
        user_threads = [
            ownership
            for ownership in self._thread_ownership.values()
            if ownership.user_id == user_id
        ]
        logger.debug(f"Found {len(user_threads)} threads for user {user_id}")
        return user_threads

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """Delete thread ownership record."""
        ownership = self._thread_ownership.get(thread_id)
        if not ownership:
            logger.warning(f"Thread {thread_id} not found for deletion")
            return False

        if ownership.user_id != user_id:
            logger.warning(
                f"User {user_id} cannot delete thread {thread_id} (owner: {ownership.user_id})"
            )
            return False

        del self._thread_ownership[thread_id]
        logger.info(f"Deleted thread {thread_id} for user {user_id}")
        return True

    async def update_thread_access(self, user_id: str, thread_id: str) -> None:
        """Update last access timestamp for thread."""
        ownership = self._thread_ownership.get(thread_id)
        if ownership and ownership.user_id == user_id:
            ownership.last_accessed = datetime.now()


class RedisThreadAccessControl(ThreadAccessControlBackend):
    """Redis-based thread access control backend."""

    def __init__(self, redis_url: str):
        """Initialize Redis backend."""
        self.redis_url = redis_url
        # TODO: Implement Redis backend
        # This would use Redis to store thread ownership with proper TTL
        # and atomic operations for thread management
        logger.info(f"Redis thread access control initialized with URL: {redis_url}")

    async def validate_thread_access(self, user_id: str, thread_id: str) -> bool:
        """Validate that user owns the thread."""
        raise NotImplementedError("Redis backend not implemented")

    async def create_thread(
        self, user_id: str, thread_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Record thread ownership."""
        raise NotImplementedError("Redis backend not implemented")

    async def list_user_threads(self, user_id: str) -> list[ThreadOwnership]:
        """List all threads owned by a user."""
        raise NotImplementedError("Redis backend not implemented")

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """Delete thread ownership record."""
        raise NotImplementedError("Redis backend not implemented")

    async def update_thread_access(self, user_id: str, thread_id: str) -> None:
        """Update last access timestamp for thread."""
        raise NotImplementedError("Redis backend not implemented")


class ThreadAccessControl:
    """Thread access control service with backend abstraction."""

    def __init__(self, backend: str = "memory", config: dict[str, Any] | None = None):
        """Initialize thread access control service."""
        self.backend_type = backend
        self.config = config or {}

        if backend == "memory":
            self.backend = InMemoryThreadAccessControl()
        elif backend == "redis":
            # redis_url = self.config.get("redis_url", settings.cache_redis_url)  # Unused
            raise NotImplementedError("Redis backend not implemented")
        else:
            raise ValueError(f"Unsupported thread access control backend: {backend}")

        logger.debug(f"Thread access control initialized with backend: {backend}")

    async def validate_thread_access(self, user_id: str, thread_id: str) -> bool:
        """Validate that user owns the thread."""
        # Validate thread_id format before processing
        self._validate_thread_id_format(thread_id)
        return await self.backend.validate_thread_access(user_id, thread_id)

    async def create_thread(
        self,
        user_id: str,
        thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new thread for the user."""
        if not thread_id:
            thread_id = str(uuid.uuid4())
        else:
            # Validate thread_id format if provided
            self._validate_thread_id_format(thread_id)

        await self.backend.create_thread(user_id, thread_id, metadata)
        return thread_id

    async def list_user_threads(self, user_id: str) -> list[ThreadOwnership]:
        """List all threads owned by a user."""
        return await self.backend.list_user_threads(user_id)

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """Delete a thread (only if user owns it)."""
        # Validate thread_id format before processing
        self._validate_thread_id_format(thread_id)
        return await self.backend.delete_thread(user_id, thread_id)

    async def create_user_scoped_thread_id(self, user_id: str, thread_id: str) -> str:
        """Create user-scoped thread ID for LangGraph."""
        # Validate thread_id format before processing
        self._validate_thread_id_format(thread_id)
        return f"user:{user_id}:{thread_id}"

    async def extract_base_thread_id(self, user_scoped_thread_id: str) -> str:
        """Extract base thread ID from user-scoped thread ID."""
        # Validate thread_id format before processing
        self._validate_thread_id_format(user_scoped_thread_id)

        if user_scoped_thread_id.startswith("user:"):
            parts = user_scoped_thread_id.split(":", 2)
            if len(parts) >= 3:
                return parts[2]
        return user_scoped_thread_id

    def _validate_thread_id_format(self, thread_id: str) -> None:
        """
        Validate thread ID format for security and consistency.

        This method validates that thread IDs follow the expected format
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

    async def get_thread_ownership(self, thread_id: str) -> ThreadOwnership | None:
        """Get thread ownership information."""
        # This would need to be implemented in the backend
        # For now, we'll use a simple approach with the in-memory backend
        if isinstance(self.backend, InMemoryThreadAccessControl):
            return self.backend._thread_ownership.get(thread_id)
        return None


# Global thread access control instance
_thread_access_control: ThreadAccessControl | None = None


def get_thread_access_control() -> ThreadAccessControl:
    """Get the global thread access control instance."""
    global _thread_access_control
    if _thread_access_control is None:
        backend = getattr(settings, "chat_thread_access_control_backend", "memory")
        _thread_access_control = ThreadAccessControl(backend=backend)
    return _thread_access_control


def set_thread_access_control(access_control: ThreadAccessControl) -> None:
    """Set the global thread access control instance."""
    global _thread_access_control
    _thread_access_control = access_control


async def validate_thread_access(user_id: str, thread_id: str) -> bool:
    """Validate thread access for a user."""
    access_control = get_thread_access_control()
    return await access_control.validate_thread_access(user_id, thread_id)


async def create_user_scoped_thread_id(user_id: str, thread_id: str) -> str:
    """Create user-scoped thread ID for LangGraph."""
    access_control = get_thread_access_control()
    return await access_control.create_user_scoped_thread_id(user_id, thread_id)
