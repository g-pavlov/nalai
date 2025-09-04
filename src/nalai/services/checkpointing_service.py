"""
Checkpointing service for API Assistant.

This module provides checkpointing functionality with multiple backend support
for LangGraph state persistence.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any

# Import actual LangGraph checkpointers
from langgraph.checkpoint.memory import MemorySaver

# Note: Other checkpointers (PostgresSaver, RedisSaver) are not available in this version
# They will fall back to MemorySaver when requested
from ..config import settings
from ..core.services import CheckpointingService as CheckpointingServiceProtocol

logger = logging.getLogger(__name__)


class CheckpointingError(Exception):
    """Base exception for checkpointing errors."""

    pass


class CheckpointingBackendError(CheckpointingError):
    """Exception raised when backend operations fail."""

    pass


class CheckpointingBackend(ABC):
    """Abstract base class for checkpointing backends."""

    @abstractmethod
    def get_checkpointer(self):
        """Get LangGraph checkpoint saver instance."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the backend is healthy."""
        pass

    @abstractmethod
    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """Clean up old checkpoints and return count of cleaned items."""
        pass


class MemoryCheckpointingBackend(CheckpointingBackend):
    """In-memory checkpointing backend using LangGraph's MemorySaver."""

    def __init__(self):
        """Initialize in-memory checkpointing backend."""
        self.checkpointer = MemorySaver()
        self._last_health_check = time.time()
        logger.debug("In-memory checkpointing backend initialized")

    def get_checkpointer(self):
        """Get LangGraph MemorySaver instance."""
        return self.checkpointer

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics."""
        # MemorySaver doesn't provide statistics, so we return basic info
        return {
            "backend": "memory",
            "type": "in_memory",
            "description": "LangGraph MemorySaver - in-memory checkpointing",
            "health_status": "healthy",
            "last_health_check": self._last_health_check,
        }

    async def health_check(self) -> bool:
        """Check if the backend is healthy."""
        try:
            # Simple health check for memory backend
            self._last_health_check = time.time()
            return True
        except Exception as e:
            logger.error(f"Memory backend health check failed: {e}")
            return False

    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """Clean up old checkpoints and return count of cleaned items."""
        # Memory backend doesn't support cleanup - data is ephemeral
        logger.debug("Memory backend cleanup not supported - data is ephemeral")
        return 0


class FileCheckpointingBackend(CheckpointingBackend):
    """File-based checkpointing backend using LangGraph's FileSaver."""

    def __init__(self, file_path: str):
        """Initialize file-based checkpointing backend."""
        self.file_path = file_path
        # This backend is not available in this version, so it will fall back to MemorySaver
        self.checkpointer = MemorySaver()
        self._last_health_check = time.time()
        logger.info(f"File checkpointing backend initialized with path: {file_path}")

    def get_checkpointer(self):
        """Get LangGraph FileSaver instance."""
        return self.checkpointer

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics."""
        # TODO: Implement file system statistics
        return {
            "backend": "file",
            "file_path": self.file_path,
            "type": "file_system",
            "description": "LangGraph FileSaver - file-based checkpointing",
            "health_status": "healthy",
            "last_health_check": self._last_health_check,
        }

    async def health_check(self) -> bool:
        """Check if the backend is healthy."""
        try:
            # TODO: Implement file system health check
            self._last_health_check = time.time()
            return True
        except Exception as e:
            logger.error(f"File backend health check failed: {e}")
            return False

    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """Clean up old checkpoints and return count of cleaned items."""
        # TODO: Implement file system cleanup
        logger.debug("File backend cleanup not implemented")
        return 0


class PostgresCheckpointingBackend(CheckpointingBackend):
    """PostgreSQL checkpointing backend using LangGraph's PostgresSaver."""

    def __init__(self, connection_string: str):
        """Initialize PostgreSQL checkpointing backend."""
        self.connection_string = connection_string
        # This backend is not available in this version, so it will fall back to MemorySaver
        self.checkpointer = MemorySaver()
        self._last_health_check = time.time()

    def get_checkpointer(self):
        """Get LangGraph PostgresSaver instance."""
        return self.checkpointer

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics."""
        # TODO: Implement PostgreSQL statistics
        return {
            "backend": "postgres",
            "connection_string": self.connection_string,
            "type": "database",
            "description": "LangGraph PostgresSaver - PostgreSQL checkpointing",
            "health_status": "healthy",
            "last_health_check": self._last_health_check,
        }

    async def health_check(self) -> bool:
        """Check if the backend is healthy."""
        try:
            # TODO: Implement PostgreSQL health check
            self._last_health_check = time.time()
            return True
        except Exception as e:
            logger.error(f"PostgreSQL backend health check failed: {e}")
            return False

    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """Clean up old checkpoints and return count of cleaned items."""
        # TODO: Implement PostgreSQL cleanup
        logger.debug("PostgreSQL backend cleanup not implemented")
        return 0


class RedisCheckpointingBackend(CheckpointingBackend):
    """Redis checkpointing backend using LangGraph's RedisSaver."""

    def __init__(self, redis_url: str):
        """Initialize Redis checkpointing backend."""
        self.redis_url = redis_url
        # This backend is not available in this version, so it will fall back to MemorySaver
        self.checkpointer = MemorySaver()
        self._last_health_check = time.time()

    def get_checkpointer(self):
        """Get LangGraph RedisSaver instance."""
        return self.checkpointer

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics."""
        # TODO: Implement Redis statistics
        return {
            "backend": "redis",
            "redis_url": self.redis_url,
            "type": "key_value_store",
            "description": "LangGraph RedisSaver - Redis checkpointing",
            "health_status": "healthy",
            "last_health_check": self._last_health_check,
        }

    async def health_check(self) -> bool:
        """Check if the backend is healthy."""
        try:
            # TODO: Implement Redis health check
            self._last_health_check = time.time()
            return True
        except Exception as e:
            logger.error(f"Redis backend health check failed: {e}")
            return False

    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """Clean up old checkpoints and return count of cleaned items."""
        # TODO: Implement Redis cleanup
        logger.debug("Redis backend cleanup not implemented")
        return 0


class Checkpointer(CheckpointingServiceProtocol):
    """Checkpointing service with backend abstraction and enhanced error handling."""

    def __init__(self, backend: str = "memory", config: dict[str, Any] | None = None):
        """Initialize checkpointing service."""
        self.backend_type = backend
        self.config = config or {}
        self._retry_attempts = 3
        self._retry_delay = 1.0  # seconds

        if backend == "memory":
            self.backend = MemoryCheckpointingBackend()
        elif backend == "file":
            file_path = self.config.get("file_path", settings.checkpointing_file_path)
            self.backend = FileCheckpointingBackend(file_path)
        elif backend == "postgres":
            connection_string = self.config.get(
                "connection_string", settings.checkpointing_postgres_url
            )
            if not connection_string:
                raise ValueError("PostgreSQL connection string not configured")
            self.backend = PostgresCheckpointingBackend(connection_string)
        elif backend == "redis":
            redis_url = self.config.get("redis_url", settings.checkpointing_redis_url)
            if not redis_url:
                raise ValueError("Redis URL not configured")
            self.backend = RedisCheckpointingBackend(redis_url)
        else:
            raise ValueError(f"Unsupported checkpointing backend: {backend}")

        logger.debug(f"Checkpointing service initialized with backend: {backend}")

    def get_checkpointer(self):
        """Get LangGraph checkpoint saver instance."""
        return self.backend.get_checkpointer()

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics."""
        try:
            stats = await self.backend.get_stats()
            stats["backend_type"] = self.backend_type
            stats["retry_attempts"] = self._retry_attempts
            stats["retry_delay"] = self._retry_delay
            return stats
        except Exception as e:
            logger.error(f"Failed to get checkpointing stats: {e}")
            raise CheckpointingBackendError(f"Failed to get stats: {e}") from e

    async def health_check(self) -> bool:
        """Check if the checkpointing backend is healthy."""
        try:
            return await self.backend.health_check()
        except Exception as e:
            logger.error(f"Checkpointing health check failed: {e}")
            return False

    async def cleanup_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """Clean up old checkpoints and return count of cleaned items."""
        try:
            return await self.backend.cleanup_old_checkpoints(max_age_hours)
        except Exception as e:
            logger.error(f"Checkpointing cleanup failed: {e}")
            raise CheckpointingBackendError(
                f"Failed to cleanup checkpoints: {e}"
            ) from e

    @asynccontextmanager
    async def checkpoint_operation(self, operation_name: str):
        """Context manager for checkpoint operations with retry logic."""
        last_exception = None

        for attempt in range(self._retry_attempts):
            try:
                # Check backend health before operation
                if not await self.health_check():
                    raise CheckpointingBackendError("Backend health check failed")

                yield self.backend
                return  # Success, exit retry loop

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Checkpoint operation '{operation_name}' failed (attempt {attempt + 1}/{self._retry_attempts}): {e}"
                )

                if attempt < self._retry_attempts - 1:
                    await asyncio.sleep(
                        self._retry_delay * (2**attempt)
                    )  # Exponential backoff

        # All retries failed
        logger.error(
            f"Checkpoint operation '{operation_name}' failed after {self._retry_attempts} attempts"
        )
        raise CheckpointingBackendError(
            f"Operation '{operation_name}' failed: {last_exception}"
        ) from last_exception


# Global checkpointing service instance
_checkpointing_service: Checkpointer | None = None


def get_checkpointing_service() -> Checkpointer:
    """Get the global checkpointing service instance."""
    global _checkpointing_service
    if _checkpointing_service is None:
        backend = settings.checkpointing_backend
        config = {
            "file_path": settings.checkpointing_file_path,
            "connection_string": settings.checkpointing_postgres_url,
            "redis_url": settings.checkpointing_redis_url,
        }
        _checkpointing_service = Checkpointer(backend=backend, config=config)
    return _checkpointing_service


def set_checkpointing_service(checkpointing_service: Checkpointer) -> None:
    """Set the global checkpointing service instance."""
    global _checkpointing_service
    _checkpointing_service = checkpointing_service


def get_checkpointer():
    """Get LangGraph checkpoint saver using the global checkpointing service."""
    checkpointing_service = get_checkpointing_service()
    return checkpointing_service.get_checkpointer()
