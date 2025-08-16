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

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from ..config import settings
from ..server.middleware import get_user_context
from ..utils.validation import validate_thread_id_format
from .audit_utils import log_thread_access_event

logger = logging.getLogger(__name__)


class ThreadOwnership(BaseModel):
    """Thread ownership record for access control."""

    thread_id: str = Field(..., description="Thread identifier")
    user_id: str = Field(..., description="Owner user identifier")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    last_accessed: datetime = Field(
        default_factory=datetime.now, description="Last access timestamp"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


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
        validate_thread_id_format(thread_id)
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
            validate_thread_id_format(thread_id)

        await self.backend.create_thread(user_id, thread_id, metadata)
        return thread_id

    async def list_user_threads(self, user_id: str) -> list[ThreadOwnership]:
        """List all threads owned by a user."""
        return await self.backend.list_user_threads(user_id)

    async def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """Delete a thread (only if user owns it)."""
        # Validate thread_id format before processing
        validate_thread_id_format(thread_id)
        return await self.backend.delete_thread(user_id, thread_id)

    async def create_user_scoped_thread_id(self, user_id: str, thread_id: str) -> str:
        """Create user-scoped thread ID for LangGraph."""
        # Validate thread_id format before processing
        validate_thread_id_format(thread_id)
        return f"user:{user_id}:{thread_id}"

    async def extract_base_thread_id(self, user_scoped_thread_id: str) -> str:
        """Extract base thread ID from user-scoped thread ID."""
        # Validate thread_id format before processing
        validate_thread_id_format(user_scoped_thread_id)

        if user_scoped_thread_id.startswith("user:"):
            parts = user_scoped_thread_id.split(":", 2)
            if len(parts) >= 3:
                return parts[2]
        return user_scoped_thread_id

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


async def validate_conversation_access_and_scope(
    config: dict | None, req: Request
) -> tuple[dict, str]:
    """
    Validate conversation access and create user-scoped conversation ID.

    This function:
    1. If no conversation_id provided: Creates a new conversation for the user
    2. If conversation_id provided: Validates that the user has access to the conversation
    3. Creates a user-scoped conversation ID for LangGraph
    4. Logs the access event for audit purposes

    Args:
        config: Configuration dictionary or Pydantic model
        req: FastAPI request object

    Returns:
        Tuple of (updated_config, user_scoped_conversation_id)
    """
    # Get user context
    try:
        user_context = get_user_context(req)
        user_id = user_context.user_id
    except Exception as e:
        logger.error(f"Failed to get user context: {e}")
        raise HTTPException(status_code=401, detail="Authentication required") from e

    # Check if conversation_id was provided in the original config
    original_config = _ensure_config_dict(config)
    original_configurable = original_config.get("configurable", {})
    conversation_id_provided = (
        "thread_id" in original_configurable
    )  # Keep using thread_id in data

    # Ensure conversation_id exists (generates new one if not provided)
    config = _ensure_config_dict(config)
    configurable = _ensure_configurable(config)

    conversation_id = configurable.get("thread_id")  # Keep using thread_id in data
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        configurable["thread_id"] = conversation_id  # Keep using thread_id in data

    # Get access control service
    access_control = get_thread_access_control()

    if conversation_id_provided:
        # Conversation ID was provided by client - validate access to existing conversation
        has_access = await access_control.validate_thread_access(
            user_id, conversation_id
        )

        if not has_access:
            # Try to create the conversation if it doesn't exist
            try:
                await access_control.create_thread(user_id, conversation_id)
                logger.debug(
                    f"Created missing conversation {conversation_id} for user {user_id}"
                )
                has_access = True
            except ValueError:
                # Conversation exists but belongs to different user
                logger.warning(
                    f"Conversation {conversation_id} exists but belongs to different user"
                )
                # Log failed access attempt
                await log_thread_access_event(
                    user_id=user_id,
                    thread_id=conversation_id,
                    action="access_denied",
                    success=False,
                    ip_address=user_context.ip_address,
                    user_agent=user_context.user_agent,
                    session_id=user_context.session_id,
                    request_id=user_context.request_id,
                )
                raise HTTPException(
                    status_code=403, detail="Access denied to conversation"
                ) from None

        if has_access:
            logger.debug(
                f"User {user_id} granted access to existing conversation {conversation_id}"
            )

    else:
        # No conversation ID provided - create new conversation for user
        try:
            # Create the conversation in the access control system using our generated conversation_id
            await access_control.create_thread(user_id, conversation_id)

            logger.debug(
                f"Created new conversation {conversation_id} for user {user_id}"
            )

        except Exception as e:
            logger.error(f"Failed to create conversation for user {user_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to create conversation"
            ) from e

    # Create user-scoped conversation ID for LangGraph (only if not already scoped)
    if conversation_id.startswith("user:"):
        # Conversation ID is already user-scoped, validate it belongs to this user
        parts = conversation_id.split(":", 2)
        if len(parts) >= 3 and parts[1] == user_id:
            user_scoped_conversation_id = conversation_id
        else:
            raise HTTPException(status_code=403, detail="Access denied to conversation")
    else:
        # Conversation ID is not scoped, create user-scoped version
        user_scoped_conversation_id = await access_control.create_user_scoped_thread_id(
            user_id, conversation_id
        )

    # Update config with user-scoped conversation ID
    configurable = _ensure_configurable(config)
    configurable["thread_id"] = (
        user_scoped_conversation_id  # Keep using thread_id in data
    )

    # Log successful access/creation
    action = (
        "conversation_created" if not conversation_id_provided else "access_granted"
    )
    await log_thread_access_event(
        user_id=user_id,
        thread_id=conversation_id,
        action=action,
        success=True,
        ip_address=user_context.ip_address,
        user_agent=user_context.user_agent,
        session_id=user_context.session_id,
        request_id=user_context.request_id,
    )

    logger.debug(
        f"User {user_id} {'created' if not conversation_id_provided else 'granted access to'} conversation {conversation_id} (scoped: {user_scoped_conversation_id})"
    )

    return config, user_scoped_conversation_id


def _ensure_config_dict(config: dict | None) -> dict:
    """Convert Pydantic model to dict and ensure config is a dictionary."""
    if config is not None and hasattr(config, "model_dump"):
        config = config.model_dump()
    return config or {}


def _ensure_configurable(config: dict) -> dict:
    """Ensure configurable section exists and is a dictionary."""
    configurable = config.setdefault("configurable", {})
    if configurable is None:
        configurable = {}
        config["configurable"] = configurable
    return configurable
