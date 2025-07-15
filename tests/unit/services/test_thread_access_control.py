"""
Unit tests for thread access control service.

Tests cover thread ownership validation, user-scoped thread ID generation,
and all access control scenarios with proper isolation.
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))

from api_assistant.services.thread_access_control import (
    ThreadAccessControlBackend,
    InMemoryThreadAccessControl,
    ThreadAccessControl,
    get_thread_access_control,
    set_thread_access_control,
    validate_thread_access,
    create_user_scoped_thread_id,
)
from api_assistant.server.models.identity import ThreadOwnership


class TestThreadAccessControlBackend:
    """Test cases for thread access control backend."""

    def test_backend_abstract_methods(self):
        """Test that ThreadAccessControlBackend is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            ThreadAccessControlBackend()


class TestInMemoryThreadAccessControl:
    """Test cases for in-memory thread access control backend."""

    @pytest.fixture
    def backend(self):
        """Create in-memory backend instance."""
        return InMemoryThreadAccessControl()

    @pytest.mark.asyncio
    async def test_validate_thread_access_owner(self, backend):
        """Test thread access validation for thread owner."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread ownership
        await backend.create_thread(user_id, thread_id)
        
        # Validate access
        result = await backend.validate_thread_access(user_id, thread_id)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_thread_access_non_owner(self, backend):
        """Test thread access validation for non-owner."""
        owner_id = "user-123"
        non_owner_id = "user-789"
        thread_id = "thread-456"
        
        # Create thread ownership
        await backend.create_thread(owner_id, thread_id)
        
        # Validate access for non-owner
        result = await backend.validate_thread_access(non_owner_id, thread_id)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_thread_access_nonexistent_thread(self, backend):
        """Test thread access validation for nonexistent thread."""
        user_id = "user-123"
        thread_id = "nonexistent-thread"
        
        # Validate access for nonexistent thread
        result = await backend.validate_thread_access(user_id, thread_id)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_create_thread_new(self, backend):
        """Test creating a new thread."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        await backend.create_thread(user_id, thread_id)
        
        # Verify thread was created
        result = await backend.validate_thread_access(user_id, thread_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_create_thread_existing_same_owner(self, backend):
        """Test creating thread that already exists with same owner."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread twice
        await backend.create_thread(user_id, thread_id)
        await backend.create_thread(user_id, thread_id)  # Should not raise error
        
        # Verify thread still exists
        result = await backend.validate_thread_access(user_id, thread_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_create_thread_existing_different_owner(self, backend):
        """Test creating thread that already exists with different owner."""
        user1_id = "user-123"
        user2_id = "user-789"
        thread_id = "thread-456"
        
        # Create thread for first user
        await backend.create_thread(user1_id, thread_id)
        
        # Try to create same thread for different user
        with pytest.raises(ValueError, match="already owned by user"):
            await backend.create_thread(user2_id, thread_id)

    @pytest.mark.asyncio
    async def test_list_user_threads(self, backend):
        """Test listing threads for a user."""
        user1_id = "user-123"
        user2_id = "user-789"
        
        # Create threads for user1
        await backend.create_thread(user1_id, "thread-1")
        await backend.create_thread(user1_id, "thread-2")
        
        # Create thread for user2
        await backend.create_thread(user2_id, "thread-3")
        
        # List threads for user1
        user1_threads = await backend.list_user_threads(user1_id)
        
        assert len(user1_threads) == 2
        thread_ids = [thread.thread_id for thread in user1_threads]
        assert "thread-1" in thread_ids
        assert "thread-2" in thread_ids
        assert "thread-3" not in thread_ids

    @pytest.mark.asyncio
    async def test_list_user_threads_empty(self, backend):
        """Test listing threads for user with no threads."""
        user_id = "user-123"
        
        threads = await backend.list_user_threads(user_id)
        
        assert len(threads) == 0

    @pytest.mark.asyncio
    async def test_delete_thread_owner(self, backend):
        """Test deleting thread by owner."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread
        await backend.create_thread(user_id, thread_id)
        
        # Delete thread
        result = await backend.delete_thread(user_id, thread_id)
        
        assert result is True
        
        # Verify thread no longer exists
        access_result = await backend.validate_thread_access(user_id, thread_id)
        assert access_result is False

    @pytest.mark.asyncio
    async def test_delete_thread_non_owner(self, backend):
        """Test deleting thread by non-owner."""
        owner_id = "user-123"
        non_owner_id = "user-789"
        thread_id = "thread-456"
        
        # Create thread
        await backend.create_thread(owner_id, thread_id)
        
        # Try to delete by non-owner
        result = await backend.delete_thread(non_owner_id, thread_id)
        
        assert result is False
        
        # Verify thread still exists
        access_result = await backend.validate_thread_access(owner_id, thread_id)
        assert access_result is True

    @pytest.mark.asyncio
    async def test_delete_thread_nonexistent(self, backend):
        """Test deleting nonexistent thread."""
        user_id = "user-123"
        thread_id = "nonexistent-thread"
        
        result = await backend.delete_thread(user_id, thread_id)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_update_thread_access(self, backend):
        """Test updating thread access timestamp."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread
        await backend.create_thread(user_id, thread_id)
        
        # Get initial access time
        initial_ownership = backend._thread_ownership[thread_id]
        initial_access = initial_ownership.last_accessed
        
        # Update access
        await backend.update_thread_access(user_id, thread_id)
        
        # Verify access time was updated
        updated_ownership = backend._thread_ownership[thread_id]
        assert updated_ownership.last_accessed > initial_access

    @pytest.mark.asyncio
    async def test_update_thread_access_nonexistent(self, backend):
        """Test updating access for nonexistent thread."""
        user_id = "user-123"
        thread_id = "nonexistent-thread"
        
        # Should not raise error
        await backend.update_thread_access(user_id, thread_id)

    @pytest.mark.asyncio
    async def test_update_thread_access_wrong_owner(self, backend):
        """Test updating access for thread owned by different user."""
        owner_id = "user-123"
        non_owner_id = "user-789"
        thread_id = "thread-456"
        
        # Create thread
        await backend.create_thread(owner_id, thread_id)
        
        # Get initial access time
        initial_ownership = backend._thread_ownership[thread_id]
        initial_access = initial_ownership.last_accessed
        
        # Update access for non-owner (should not update)
        await backend.update_thread_access(non_owner_id, thread_id)
        
        # Verify access time was not updated
        updated_ownership = backend._thread_ownership[thread_id]
        assert updated_ownership.last_accessed == initial_access


class TestThreadAccessControl:
    """Test cases for thread access control service."""

    @pytest.fixture
    def access_control(self):
        """Create thread access control instance."""
        return ThreadAccessControl(backend="memory")

    @pytest.mark.asyncio
    async def test_validate_thread_access(self, access_control):
        """Test thread access validation through service."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread
        await access_control.create_thread(user_id, thread_id)
        
        # Validate access
        result = await access_control.validate_thread_access(user_id, thread_id)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_create_thread_with_id(self, access_control):
        """Test creating thread with specific ID."""
        user_id = "user-123"
        thread_id = "custom-thread-id"
        
        result = await access_control.create_thread(user_id, thread_id)
        
        assert result == thread_id
        
        # Verify thread was created
        access_result = await access_control.validate_thread_access(user_id, thread_id)
        assert access_result is True

    @pytest.mark.asyncio
    async def test_create_thread_without_id(self, access_control):
        """Test creating thread without specifying ID."""
        user_id = "user-123"
        
        result = await access_control.create_thread(user_id)
        
        # Should generate UUID
        assert result is not None
        assert len(result) > 0
        
        # Verify thread was created
        access_result = await access_control.validate_thread_access(user_id, result)
        assert access_result is True

    @pytest.mark.asyncio
    async def test_create_thread_with_metadata(self, access_control):
        """Test creating thread with metadata."""
        user_id = "user-123"
        thread_id = "thread-456"
        metadata = {"description": "Test thread", "tags": ["test", "demo"]}
        
        result = await access_control.create_thread(user_id, thread_id, metadata)
        
        assert result == thread_id
        
        # Verify metadata was stored
        ownership = await access_control.get_thread_ownership(thread_id)
        assert ownership.metadata == metadata

    @pytest.mark.asyncio
    async def test_list_user_threads(self, access_control):
        """Test listing user threads through service."""
        user_id = "user-123"
        
        # Create multiple threads
        await access_control.create_thread(user_id, "thread-1")
        await access_control.create_thread(user_id, "thread-2")
        
        threads = await access_control.list_user_threads(user_id)
        
        assert len(threads) == 2
        thread_ids = [thread.thread_id for thread in threads]
        assert "thread-1" in thread_ids
        assert "thread-2" in thread_ids

    @pytest.mark.asyncio
    async def test_delete_thread(self, access_control):
        """Test deleting thread through service."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread
        await access_control.create_thread(user_id, thread_id)
        
        # Delete thread
        result = await access_control.delete_thread(user_id, thread_id)
        
        assert result is True
        
        # Verify thread no longer exists
        access_result = await access_control.validate_thread_access(user_id, thread_id)
        assert access_result is False

    @pytest.mark.asyncio
    async def test_create_user_scoped_thread_id(self, access_control):
        """Test creating user-scoped thread ID."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        scoped_id = await access_control.create_user_scoped_thread_id(user_id, thread_id)
        
        assert scoped_id == f"user:{user_id}:{thread_id}"

    @pytest.mark.asyncio
    async def test_extract_base_thread_id(self, access_control):
        """Test extracting base thread ID from user-scoped ID."""
        user_id = "user-123"
        thread_id = "thread-456"
        scoped_id = f"user:{user_id}:{thread_id}"
        
        extracted_id = await access_control.extract_base_thread_id(scoped_id)
        
        assert extracted_id == thread_id

    @pytest.mark.asyncio
    async def test_extract_base_thread_id_no_prefix(self, access_control):
        """Test extracting base thread ID from non-scoped ID."""
        thread_id = "thread-456"
        
        extracted_id = await access_control.extract_base_thread_id(thread_id)
        
        assert extracted_id == thread_id

    @pytest.mark.asyncio
    async def test_get_thread_ownership(self, access_control):
        """Test getting thread ownership information."""
        user_id = "user-123"
        thread_id = "thread-456"
        metadata = {"description": "Test thread"}
        
        # Create thread
        await access_control.create_thread(user_id, thread_id, metadata)
        
        # Get ownership
        ownership = await access_control.get_thread_ownership(thread_id)
        
        assert ownership is not None
        assert ownership.thread_id == thread_id
        assert ownership.user_id == user_id
        assert ownership.metadata == metadata

    @pytest.mark.asyncio
    async def test_get_thread_ownership_nonexistent(self, access_control):
        """Test getting ownership for nonexistent thread."""
        thread_id = "nonexistent-thread"
        
        ownership = await access_control.get_thread_ownership(thread_id)
        
        assert ownership is None

    def test_unsupported_backend(self):
        """Test initialization with unsupported backend."""
        with pytest.raises(ValueError, match="Unsupported thread access control backend"):
            ThreadAccessControl(backend="unsupported")

    def test_redis_backend_not_implemented(self):
        """Test that Redis backend raises NotImplementedError."""
        with patch("api_assistant.services.thread_access_control.settings") as mock_settings:
            mock_settings.cache_redis_url = "redis://localhost:6379"
            
            with pytest.raises(NotImplementedError):
                ThreadAccessControl(backend="redis")


class TestThreadAccessControlGlobal:
    """Test cases for global thread access control functions."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("api_assistant.services.thread_access_control.settings") as mock_settings:
            mock_settings.thread_access_control_backend = "memory"
            yield mock_settings

    def test_get_thread_access_control_singleton(self, mock_settings):
        """Test get_thread_access_control returns singleton instance."""
        # Clear any existing instance
        set_thread_access_control(None)
        
        control1 = get_thread_access_control()
        control2 = get_thread_access_control()
        
        assert control1 is control2
        assert isinstance(control1, ThreadAccessControl)

    def test_set_thread_access_control(self, mock_settings):
        """Test set_thread_access_control."""
        custom_control = ThreadAccessControl(backend="memory")
        set_thread_access_control(custom_control)
        
        control = get_thread_access_control()
        assert control is custom_control

    @pytest.mark.asyncio
    async def test_validate_thread_access_global(self, mock_settings):
        """Test validate_thread_access global function."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread
        access_control = get_thread_access_control()
        await access_control.create_thread(user_id, thread_id)
        
        # Validate access
        result = await validate_thread_access(user_id, thread_id)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_create_user_scoped_thread_id_global(self, mock_settings):
        """Test create_user_scoped_thread_id global function."""
        user_id = "user-123"
        thread_id = "thread-456"
        
        scoped_id = await create_user_scoped_thread_id(user_id, thread_id)
        
        assert scoped_id == f"user:{user_id}:{thread_id}"


class TestThreadAccessControlIntegration:
    """Integration tests for thread access control."""

    @pytest.mark.asyncio
    async def test_multiple_users_thread_isolation(self):
        """Test that threads are properly isolated between users."""
        access_control = ThreadAccessControl(backend="memory")
        
        user1_id = "user-123"
        user2_id = "user-789"
        thread_id = "shared-thread-id"
        
        # User1 creates thread
        await access_control.create_thread(user1_id, thread_id)
        
        # User1 can access thread
        user1_access = await access_control.validate_thread_access(user1_id, thread_id)
        assert user1_access is True
        
        # User2 cannot access thread
        user2_access = await access_control.validate_thread_access(user2_id, thread_id)
        assert user2_access is False
        
        # User2 cannot delete thread
        user2_delete = await access_control.delete_thread(user2_id, thread_id)
        assert user2_delete is False
        
        # Thread still exists for User1
        user1_access_after = await access_control.validate_thread_access(user1_id, thread_id)
        assert user1_access_after is True

    @pytest.mark.asyncio
    async def test_user_scoped_thread_id_isolation(self):
        """Test that user-scoped thread IDs provide natural isolation."""
        access_control = ThreadAccessControl(backend="memory")
        
        user1_id = "user-123"
        user2_id = "user-789"
        base_thread_id = "shared-thread"
        
        # Create user-scoped thread IDs
        user1_scoped_id = await access_control.create_user_scoped_thread_id(user1_id, base_thread_id)
        user2_scoped_id = await access_control.create_user_scoped_thread_id(user2_id, base_thread_id)
        
        # They should be different
        assert user1_scoped_id != user2_scoped_id
        assert user1_scoped_id == f"user:{user1_id}:{base_thread_id}"
        assert user2_scoped_id == f"user:{user2_id}:{base_thread_id}"
        
        # Extract base thread IDs
        user1_base = await access_control.extract_base_thread_id(user1_scoped_id)
        user2_base = await access_control.extract_base_thread_id(user2_scoped_id)
        
        # Base thread IDs should be the same
        assert user1_base == user2_base
        assert user1_base == base_thread_id

    @pytest.mark.asyncio
    async def test_thread_lifecycle(self):
        """Test complete thread lifecycle."""
        access_control = ThreadAccessControl(backend="memory")
        
        user_id = "user-123"
        
        # 1. Create thread
        thread_id = await access_control.create_thread(user_id)
        assert thread_id is not None
        
        # 2. Verify access
        access = await access_control.validate_thread_access(user_id, thread_id)
        assert access is True
        
        # 3. List threads
        threads = await access_control.list_user_threads(user_id)
        assert len(threads) == 1
        assert threads[0].thread_id == thread_id
        
        # 4. Get ownership
        ownership = await access_control.get_thread_ownership(thread_id)
        assert ownership.user_id == user_id
        assert ownership.thread_id == thread_id
        
        # 5. Delete thread
        delete_result = await access_control.delete_thread(user_id, thread_id)
        assert delete_result is True
        
        # 6. Verify thread no longer exists
        access_after = await access_control.validate_thread_access(user_id, thread_id)
        assert access_after is False
        
        threads_after = await access_control.list_user_threads(user_id)
        assert len(threads_after) == 0

    @pytest.mark.asyncio
    async def test_concurrent_access_simulation(self):
        """Test simulating concurrent access patterns."""
        access_control = ThreadAccessControl(backend="memory")
        
        user_id = "user-123"
        thread_id = "thread-456"
        
        # Create thread
        await access_control.create_thread(user_id, thread_id)
        
        # Simulate multiple access attempts
        access_results = []
        for _ in range(10):
            result = await access_control.validate_thread_access(user_id, thread_id)
            access_results.append(result)
        
        # All should succeed
        assert all(access_results)
        
        # Simulate access from different user
        other_user_id = "user-789"
        other_access_results = []
        for _ in range(10):
            result = await access_control.validate_thread_access(other_user_id, thread_id)
            other_access_results.append(result)
        
        # All should fail
        assert not any(other_access_results) 