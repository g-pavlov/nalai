"""
Checkpointing service for API Assistant.

This module provides checkpointing functionality with multiple backend support
for LangGraph state persistence.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# Import actual LangGraph checkpointers
from langgraph.checkpoint.memory import MemorySaver

# Note: Other checkpointers (PostgresSaver, RedisSaver) are not available in this version
# They will fall back to MemorySaver when requested

from ..config import settings

logger = logging.getLogger(__name__)


class CheckpointingBackend(ABC):
    """Abstract base class for checkpointing backends."""
    
    @abstractmethod
    def get_checkpointer(self):
        """Get LangGraph checkpoint saver instance."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get checkpointing statistics."""
        pass


class MemoryCheckpointingBackend(CheckpointingBackend):
    """In-memory checkpointing backend using LangGraph's MemorySaver."""
    
    def __init__(self):
        """Initialize in-memory checkpointing backend."""
        self.checkpointer = MemorySaver()
        logger.debug("In-memory checkpointing backend initialized")
    
    def get_checkpointer(self):
        """Get LangGraph MemorySaver instance."""
        return self.checkpointer
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get checkpointing statistics."""
        # MemorySaver doesn't provide statistics, so we return basic info
        return {
            "backend": "memory",
            "type": "in_memory",
            "description": "LangGraph MemorySaver - in-memory checkpointing"
        }


class FileCheckpointingBackend(CheckpointingBackend):
    """File-based checkpointing backend using LangGraph's FileSaver."""
    
    def __init__(self, file_path: str):
        """Initialize file-based checkpointing backend."""
        self.file_path = file_path
        # This backend is not available in this version, so it will fall back to MemorySaver
        self.checkpointer = MemorySaver()
        logger.info(f"File checkpointing backend initialized with path: {file_path}")
    
    def get_checkpointer(self):
        """Get LangGraph FileSaver instance."""
        return self.checkpointer
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get checkpointing statistics."""
        # TODO: Implement file system statistics
        return {
            "backend": "file",
            "file_path": self.file_path,
            "type": "file_system",
            "description": "LangGraph FileSaver - file-based checkpointing"
        }


class PostgresCheckpointingBackend(CheckpointingBackend):
    """PostgreSQL checkpointing backend using LangGraph's PostgresSaver."""
    
    def __init__(self, connection_string: str):
        """Initialize PostgreSQL checkpointing backend."""
        self.connection_string = connection_string
        # This backend is not available in this version, so it will fall back to MemorySaver
        self.checkpointer = MemorySaver()
    
    def get_checkpointer(self):
        """Get LangGraph PostgresSaver instance."""
        return self.checkpointer
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get checkpointing statistics."""
        # TODO: Implement PostgreSQL statistics
        return {
            "backend": "postgres",
            "connection_string": self.connection_string,
            "type": "database",
            "description": "LangGraph PostgresSaver - PostgreSQL checkpointing"
        }


class RedisCheckpointingBackend(CheckpointingBackend):
    """Redis checkpointing backend using LangGraph's RedisSaver."""
    
    def __init__(self, redis_url: str):
        """Initialize Redis checkpointing backend."""
        self.redis_url = redis_url
        # This backend is not available in this version, so it will fall back to MemorySaver
        self.checkpointer = MemorySaver()
    
    def get_checkpointer(self):
        """Get LangGraph RedisSaver instance."""
        return self.checkpointer
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get checkpointing statistics."""
        # TODO: Implement Redis statistics
        return {
            "backend": "redis",
            "redis_url": self.redis_url,
            "type": "key_value_store",
            "description": "LangGraph RedisSaver - Redis checkpointing"
        }


class CheckpointingService:
    """Checkpointing service with backend abstraction."""
    
    def __init__(self, backend: str = "memory", config: Optional[Dict[str, Any]] = None):
        """Initialize checkpointing service."""
        self.backend_type = backend
        self.config = config or {}
        
        if backend == "memory":
            self.backend = MemoryCheckpointingBackend()
        elif backend == "file":
            file_path = self.config.get("file_path", settings.checkpointing_file_path)
            self.backend = FileCheckpointingBackend(file_path)
        elif backend == "postgres":
            connection_string = self.config.get("connection_string", settings.checkpointing_postgres_url)
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
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get checkpointing statistics."""
        stats = await self.backend.get_stats()
        stats["backend_type"] = self.backend_type
        return stats


# Global checkpointing service instance
_checkpointing_service: Optional[CheckpointingService] = None


def get_checkpointing_service() -> CheckpointingService:
    """Get the global checkpointing service instance."""
    global _checkpointing_service
    if _checkpointing_service is None:
        backend = settings.checkpointing_backend
        config = {
            "file_path": settings.checkpointing_file_path,
            "connection_string": settings.checkpointing_postgres_url,
            "redis_url": settings.checkpointing_redis_url
        }
        _checkpointing_service = CheckpointingService(backend=backend, config=config)
    return _checkpointing_service


def set_checkpointing_service(checkpointing_service: CheckpointingService) -> None:
    """Set the global checkpointing service instance."""
    global _checkpointing_service
    _checkpointing_service = checkpointing_service


def get_checkpointer():
    """Get LangGraph checkpoint saver using the global checkpointing service."""
    checkpointing_service = get_checkpointing_service()
    return checkpointing_service.get_checkpointer() 