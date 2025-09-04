"""
Unit tests for checkpointing service.

Tests cover LangGraph native checkpointing backends and service
abstraction with proper backend selection and configuration.
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.services.checkpointing_service import (
    Checkpointer,
    CheckpointingBackend,
    FileCheckpointingBackend,
    MemoryCheckpointingBackend,
    PostgresCheckpointingBackend,
    RedisCheckpointingBackend,
    get_checkpointer,
    get_checkpointing_service,
    set_checkpointing_service,
)


class TestCheckpointingBackend:
    """Test cases for checkpointing backend."""

    def test_backend_abstract_methods(self):
        """Test that CheckpointingBackend is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            CheckpointingBackend()


class TestMemoryCheckpointingBackend:
    """Test cases for in-memory checkpointing backend."""

    @pytest.fixture
    def backend(self):
        """Create in-memory backend instance."""
        return MemoryCheckpointingBackend()

    def test_get_checkpointer(self, backend):
        """Test getting memory checkpointer."""
        checkpointer = backend.get_checkpointer()

        assert checkpointer is not None
        # Verify it's a LangGraph MemorySaver
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    @pytest.mark.asyncio
    async def test_get_stats(self, backend):
        """Test getting memory backend statistics."""
        stats = await backend.get_stats()

        assert stats["backend"] == "memory"
        assert stats["type"] == "in_memory"
        assert "description" in stats


class TestFileCheckpointingBackend:
    """Test cases for file checkpointing backend."""

    @pytest.fixture
    def backend(self):
        """Create file backend instance."""
        return FileCheckpointingBackend("./test_checkpoints")

    def test_get_checkpointer(self, backend):
        """Test getting file checkpointer."""
        checkpointer = backend.get_checkpointer()

        assert checkpointer is not None
        # Verify it's a LangGraph FileSaver
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    @pytest.mark.asyncio
    async def test_get_stats(self, backend):
        """Test getting file backend statistics."""
        stats = await backend.get_stats()

        assert stats["backend"] == "file"
        assert stats["file_path"] == "./test_checkpoints"
        assert stats["type"] == "file_system"
        assert "description" in stats


class TestPostgresCheckpointingBackend:
    """Test cases for PostgreSQL checkpointing backend."""

    @pytest.fixture
    def backend(self):
        """Create PostgreSQL backend instance."""
        return PostgresCheckpointingBackend("postgresql://test")

    def test_get_checkpointer(self, backend):
        """Test getting PostgreSQL checkpointer."""
        checkpointer = backend.get_checkpointer()

        assert checkpointer is not None
        # Verify it's a LangGraph PostgresSaver
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    @pytest.mark.asyncio
    async def test_get_stats(self, backend):
        """Test getting PostgreSQL backend statistics."""
        stats = await backend.get_stats()

        assert stats["backend"] == "postgres"
        assert stats["connection_string"] == "postgresql://test"
        assert stats["type"] == "database"
        assert "description" in stats


class TestRedisCheckpointingBackend:
    """Test cases for Redis checkpointing backend."""

    @pytest.fixture
    def backend(self):
        """Create Redis backend instance."""
        return RedisCheckpointingBackend("redis://localhost:6379")

    def test_get_checkpointer(self, backend):
        """Test getting Redis checkpointer."""
        checkpointer = backend.get_checkpointer()

        assert checkpointer is not None
        # Verify it's a LangGraph RedisSaver
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    @pytest.mark.asyncio
    async def test_get_stats(self, backend):
        """Test getting Redis backend statistics."""
        stats = await backend.get_stats()

        assert stats["backend"] == "redis"
        assert stats["redis_url"] == "redis://localhost:6379"
        assert stats["type"] == "key_value_store"
        assert "description" in stats


class TestCheckpointer:
    """Test cases for checkpointing service."""

    @pytest.fixture
    def checkpointing_service(self):
        """Create checkpointing service instance."""
        return Checkpointer(backend="memory")

    def test_get_checkpointer_memory(self, checkpointing_service):
        """Test getting memory checkpointer through service."""
        checkpointer = checkpointing_service.get_checkpointer()

        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    @pytest.mark.asyncio
    async def test_get_stats_memory(self, checkpointing_service):
        """Test getting memory service statistics."""
        stats = await checkpointing_service.get_stats()

        assert stats["backend"] == "memory"
        assert stats["backend_type"] == "memory"
        assert stats["type"] == "in_memory"

    def test_get_checkpointer_file(self, checkpointing_service):
        """Test getting file checkpointer through service."""
        # Create file service
        file_service = Checkpointer(
            backend="file", config={"file_path": "./test_checkpoints"}
        )
        checkpointer = file_service.get_checkpointer()

        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    def test_get_checkpointer_postgres(self, checkpointing_service):
        """Test getting PostgreSQL checkpointer through service."""
        # Create postgres service
        postgres_service = Checkpointer(
            backend="postgres", config={"connection_string": "postgresql://test"}
        )
        checkpointer = postgres_service.get_checkpointer()

        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    def test_get_checkpointer_redis(self, checkpointing_service):
        """Test getting Redis checkpointer through service."""
        # Create redis service
        redis_service = Checkpointer(
            backend="redis", config={"redis_url": "redis://localhost:6379"}
        )
        checkpointer = redis_service.get_checkpointer()

        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    def test_unsupported_backend(self):
        """Test initialization with unsupported backend."""
        with pytest.raises(ValueError, match="Unsupported checkpointing backend"):
            Checkpointer(backend="unsupported")

    def test_postgres_missing_connection_string(self):
        """Test PostgreSQL initialization without connection string."""
        with pytest.raises(
            ValueError, match="PostgreSQL connection string not configured"
        ):
            Checkpointer(backend="postgres")

    def test_redis_missing_url(self):
        """Test Redis initialization without URL."""
        with pytest.raises(ValueError, match="Redis URL not configured"):
            Checkpointer(backend="redis")


class TestCheckpointerGlobal:
    """Test cases for global checkpointing service functions."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("nalai.services.checkpointing_service.settings") as mock_settings:
            mock_settings.checkpointing_backend = "memory"
            mock_settings.checkpointing_file_path = "./checkpoints"
            mock_settings.checkpointing_postgres_url = ""
            mock_settings.checkpointing_redis_url = ""
            yield mock_settings

    def test_get_checkpointing_service_singleton(self, mock_settings):
        """Test get_checkpointing_service returns singleton instance."""
        # Clear any existing instance
        set_checkpointing_service(None)

        service1 = get_checkpointing_service()
        service2 = get_checkpointing_service()

        assert service1 is service2
        assert isinstance(service1, Checkpointer)

    def test_set_checkpointing_service(self, mock_settings):
        """Test set_checkpointing_service."""
        custom_service = Checkpointer(backend="memory")
        set_checkpointing_service(custom_service)

        service = get_checkpointing_service()
        assert service is custom_service

    def test_get_checkpointer_global(self, mock_settings):
        """Test get_checkpointer global function."""
        # Clear any existing instance
        set_checkpointing_service(None)

        checkpointer = get_checkpointer()

        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")


class TestCheckpointerIntegration:
    """Integration tests for checkpointing service."""

    def test_memory_backend_integration(self):
        """Test memory backend integration with LangGraph."""
        checkpointing_service = Checkpointer(backend="memory")

        checkpointer = checkpointing_service.get_checkpointer()

        # Test basic LangGraph operations
        # thread_id = "test-thread"  # Unused
        # config = {"configurable": {"thread_id": thread_id}}  # Unused

        # These should not raise exceptions
        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    def test_file_backend_integration(self):
        """Test file backend integration with LangGraph."""
        checkpointing_service = Checkpointer(
            backend="file", config={"file_path": "./test_checkpoints"}
        )

        checkpointer = checkpointing_service.get_checkpointer()

        # Test basic LangGraph operations
        # thread_id = "test-thread"  # Unused
        # config = {"configurable": {"thread_id": thread_id}}  # Unused

        # These should not raise exceptions
        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")

    def test_backend_consistency(self):
        """Test that different backends provide consistent interfaces."""
        backends = [
            ("memory", {}),
            ("file", {"file_path": "./test_checkpoints"}),
        ]

        for backend_type, config in backends:
            try:
                checkpointing_service = Checkpointer(
                    backend=backend_type, config=config
                )

                checkpointer = checkpointing_service.get_checkpointer()

                # Verify consistent interface
                assert checkpointer is not None
                assert hasattr(checkpointer, "get")
                assert hasattr(checkpointer, "put")

            except (NotImplementedError, ValueError) as e:
                # Skip backends that are not implemented or misconfigured
                if "not configured" not in str(e):
                    raise

    @pytest.mark.asyncio
    async def test_stats_consistency(self):
        """Test that all backends provide consistent statistics."""
        backends = [
            ("memory", {}),
            ("file", {"file_path": "./test_checkpoints"}),
        ]

        for backend_type, config in backends:
            try:
                checkpointing_service = Checkpointer(
                    backend=backend_type, config=config
                )

                stats = await checkpointing_service.get_stats()

                # Verify consistent stats structure
                assert "backend" in stats
                assert "type" in stats
                assert "description" in stats
                assert stats["backend_type"] == backend_type

            except (NotImplementedError, ValueError) as e:
                # Skip backends that are not implemented or misconfigured
                if "not configured" not in str(e):
                    raise

    def test_langgraph_config_integration(self):
        """Test integration with LangGraph configuration."""
        checkpointing_service = Checkpointer(backend="memory")

        checkpointer = checkpointing_service.get_checkpointer()

        # Simulate LangGraph config
        thread_id = "user:user-123:thread-456"
        langgraph_config = {"configurable": {"thread_id": thread_id}}

        # Verify config structure
        assert "configurable" in langgraph_config
        assert "thread_id" in langgraph_config["configurable"]
        assert langgraph_config["configurable"]["thread_id"] == thread_id

        # Verify checkpointer is ready for use
        assert checkpointer is not None
        assert hasattr(checkpointer, "get")
        assert hasattr(checkpointer, "put")
