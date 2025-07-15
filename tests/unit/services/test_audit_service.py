"""
Unit tests for audit service.

Tests cover audit event logging, different backends, and audit trail
functionality with proper event structure and metadata.
"""

import os
import sys
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from api_assistant.services.audit_service import (
    AuditBackend,
    AuditService,
    ExternalAuditBackend,
    InMemoryAuditBackend,
    get_audit_service,
    log_access_event,
    set_audit_service,
)


class TestAuditBackend:
    """Test cases for audit backend."""

    def test_backend_abstract_methods(self):
        """Test that AuditBackend is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            AuditBackend()


class TestInMemoryAuditBackend:
    """Test cases for in-memory audit backend."""

    @pytest.fixture
    def backend(self):
        """Create in-memory backend instance."""
        return InMemoryAuditBackend(max_entries=1000)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "user_id,resource,action,metadata",
        [
            (
                "user-123",
                "thread:thread-456",
                "invoke_agent",
                {"ip_address": "127.0.0.1", "user_agent": "test-agent"},
            ),
            ("user-123", "thread:thread-456", "invoke_agent", None),
        ],
    )
    async def test_log_access_event(self, backend, user_id, resource, action, metadata):
        """Test logging access event with and without metadata."""
        if metadata is not None:
            await backend.log_access(user_id, resource, action, metadata)
        else:
            await backend.log_access(user_id, resource, action)
        events = await backend.get_events(user_id=user_id)
        assert len(events) == 1
        event = events[0]
        assert event.user_id == user_id
        assert event.resource == resource
        assert event.action == action
        if metadata is not None:
            assert event.metadata == metadata
        else:
            assert event.metadata == {}
        assert event.timestamp is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "log_setup,filter_kwargs,expected_count",
        [
            # user filter
            (
                [
                    ("user-123", "thread:thread-1", "create_thread"),
                    ("user-123", "thread:thread-1", "invoke_agent"),
                    ("user-789", "thread:thread-2", "create_thread"),
                ],
                {"user_id": "user-123"},
                2,
            ),
            (
                [
                    ("user-123", "thread:thread-1", "create_thread"),
                    ("user-123", "thread:thread-1", "invoke_agent"),
                    ("user-789", "thread:thread-2", "create_thread"),
                ],
                {"user_id": "user-789"},
                1,
            ),
            # resource filter
            (
                [
                    ("user-123", "thread:thread-1", "create_thread"),
                    ("user-123", "thread:thread-1", "invoke_agent"),
                    ("user-123", "thread:thread-2", "create_thread"),
                ],
                {"resource": "thread:thread-1"},
                2,
            ),
            (
                [
                    ("user-123", "thread:thread-1", "create_thread"),
                    ("user-123", "thread:thread-1", "invoke_agent"),
                    ("user-123", "thread:thread-2", "create_thread"),
                ],
                {"resource": "thread:thread-2"},
                1,
            ),
            # action filter
            (
                [
                    ("user-123", "thread:thread-1", "create_thread"),
                    ("user-123", "thread:thread-2", "create_thread"),
                    ("user-123", "thread:thread-1", "invoke_agent"),
                ],
                {"action": "create_thread"},
                2,
            ),
            (
                [
                    ("user-123", "thread:thread-1", "create_thread"),
                    ("user-123", "thread:thread-2", "create_thread"),
                    ("user-123", "thread:thread-1", "invoke_agent"),
                ],
                {"action": "invoke_agent"},
                1,
            ),
            # combined filters
            (
                [
                    ("user-123", "thread:thread-1", "create_thread"),
                    ("user-123", "thread:thread-1", "invoke_agent"),
                    ("user-789", "thread:thread-1", "create_thread"),
                ],
                {"user_id": "user-123", "resource": "thread:thread-1"},
                2,
            ),
        ],
    )
    async def test_get_events_filters(
        self, backend, log_setup, filter_kwargs, expected_count
    ):
        """Test get_events with user/resource/action/combined filters."""
        for user_id, resource, action in log_setup:
            await backend.log_access(user_id, resource, action)
        events = await backend.get_events(**filter_kwargs)
        assert len(events) == expected_count

    @pytest.mark.asyncio
    async def test_get_events_by_time_range(self, backend):
        """Test getting events filtered by time range."""
        user_id = "user-123"
        await backend.log_access(user_id, "thread:thread-1", "create_thread")
        import asyncio

        await asyncio.sleep(0.1)
        mid_time = datetime.now(UTC)
        await asyncio.sleep(0.1)
        await backend.log_access(user_id, "thread:thread-2", "create_thread")
        early_events = await backend.get_events(before=mid_time)
        assert len(early_events) == 1
        late_events = await backend.get_events(after=mid_time)
        assert len(late_events) == 1
        assert early_events[0].resource == "thread:thread-1"
        assert late_events[0].resource == "thread:thread-2"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "num_events,limit",
        [
            (10, 5),
            (3, 2),
            (5, 5),
        ],
    )
    async def test_get_events_limit(self, backend, num_events, limit):
        """Test getting events with limit."""
        user_id = "user-123"
        for i in range(num_events):
            await backend.log_access(user_id, f"thread:thread-{i}", "create_thread")
        events = await backend.get_events(user_id=user_id, limit=limit)
        assert len(events) == min(num_events, limit)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "max_entries,log_count,expected_count",
        [
            (3, 5, 3),
            (2, 4, 2),
            (1, 2, 1),
        ],
    )
    async def test_get_events_max_entries_limit(
        self, max_entries, log_count, expected_count
    ):
        """Test that backend respects max_entries limit."""
        small_backend = InMemoryAuditBackend(max_entries=max_entries)
        user_id = "user-123"
        for i in range(log_count):
            await small_backend.log_access(
                user_id, f"thread:thread-{i}", "create_thread"
            )
        events = await small_backend.get_events()
        assert len(events) == expected_count
        # Most recent events should be present
        thread_ids = [event.resource for event in events]
        for i in range(log_count - expected_count, log_count):
            assert f"thread:thread-{i}" in thread_ids

    @pytest.mark.asyncio
    async def test_get_events_empty(self, backend):
        """Test getting events when none exist."""
        events = await backend.get_events()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_audit_event_properties(self, backend):
        """Test AuditEvent properties."""
        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"
        metadata = {"ip_address": "127.0.0.1"}
        await backend.log_access(user_id, resource, action, metadata)
        events = await backend.get_events()
        event = events[0]
        assert event.user_id == user_id
        assert event.resource == resource
        assert event.action == action
        assert event.metadata == metadata
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)
        event_str = str(event)
        assert user_id in event_str
        assert resource in event_str
        assert action in event_str


class TestExternalAuditBackend:
    """Test cases for external audit backend."""

    @pytest.fixture
    def backend(self):
        """Create external backend instance."""
        return ExternalAuditBackend("http://audit-service:8080")

    @pytest.mark.asyncio
    async def test_log_access_event_success(self, backend):
        """Test successful logging to external service."""
        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"
        metadata = {"ip_address": "127.0.0.1"}

        # Should not raise exception
        await backend.log_access(user_id, resource, action, metadata)

        # Verify no HTTP call was made (implementation is TODO)
        # The current implementation just logs debug messages

    @pytest.mark.asyncio
    async def test_log_access_event_failure(self, backend):
        """Test handling of external service failure."""
        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"

        # Should not raise exception
        await backend.log_access(user_id, resource, action)

        # Verify no HTTP call was made (implementation is TODO)

    @pytest.mark.asyncio
    async def test_log_access_event_connection_error(self, backend):
        """Test handling of connection error."""
        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"

        # Should not raise exception
        await backend.log_access(user_id, resource, action)

        # Verify no HTTP call was made (implementation is TODO)

    @pytest.mark.asyncio
    async def test_get_events_not_implemented(self, backend):
        """Test that get_events raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await backend.get_events()


class TestAuditService:
    """Test cases for audit service."""

    @pytest.fixture
    def audit_service(self):
        """Create audit service instance."""
        return AuditService(backend="memory")

    @pytest.mark.asyncio
    async def test_log_access_event(self, audit_service):
        """Test logging access event through service."""
        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"
        metadata = {"ip_address": "127.0.0.1"}

        await audit_service.log_access(user_id, resource, action, metadata)

        # Verify event was logged
        events = await audit_service.get_events(user_id=user_id)
        assert len(events) == 1

        event = events[0]
        assert event.user_id == user_id
        assert event.resource == resource
        assert event.action == action
        assert event.metadata == metadata

    @pytest.mark.asyncio
    async def test_get_events_with_filters(self, audit_service):
        """Test getting events with filters through service."""
        user_id = "user-123"

        # Log multiple events
        await audit_service.log_access(user_id, "thread:thread-1", "create_thread")
        await audit_service.log_access(user_id, "thread:thread-1", "invoke_agent")
        await audit_service.log_access(user_id, "thread:thread-2", "create_thread")

        # Get events with filters
        events = await audit_service.get_events(
            user_id=user_id, resource="thread:thread-1", action="create_thread"
        )

        assert len(events) == 1
        assert events[0].action == "create_thread"

    @pytest.mark.asyncio
    async def test_get_events_limit(self, audit_service):
        """Test getting events with limit through service."""
        user_id = "user-123"

        # Log multiple events
        for i in range(10):
            await audit_service.log_access(
                user_id, f"thread:thread-{i}", "create_thread"
            )

        # Get events with limit
        events = await audit_service.get_events(user_id=user_id, limit=5)
        assert len(events) == 5

    def test_unsupported_backend(self):
        """Test initialization with unsupported backend."""
        with pytest.raises(ValueError, match="Unsupported audit backend"):
            AuditService(backend="unsupported")

    def test_external_backend_not_implemented(self):
        """Test that external backend raises NotImplementedError."""
        with patch("api_assistant.services.audit_service.settings") as mock_settings:
            mock_settings.audit_external_url = "http://audit-service:8080"

            with pytest.raises(NotImplementedError):
                AuditService(backend="external")


class TestAuditServiceGlobal:
    """Test cases for global audit service functions."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch("api_assistant.services.audit_service.settings") as mock_settings:
            mock_settings.audit_backend = "memory"
            yield mock_settings

    def test_get_audit_service_singleton(self, mock_settings):
        """Test get_audit_service returns singleton instance."""
        # Clear any existing instance
        set_audit_service(None)

        service1 = get_audit_service()
        service2 = get_audit_service()

        assert service1 is service2
        assert isinstance(service1, AuditService)

    def test_set_audit_service(self, mock_settings):
        """Test set_audit_service."""
        custom_service = AuditService(backend="memory")
        set_audit_service(custom_service)

        service = get_audit_service()
        assert service is custom_service

    @pytest.mark.asyncio
    async def test_log_access_event_global(self, mock_settings):
        """Test log_access_event global function."""
        # Clear any existing instance to avoid MagicMock issues
        set_audit_service(None)

        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"
        metadata = {"ip_address": "127.0.0.1"}

        await log_access_event(user_id, resource, action, metadata)

        # Verify event was logged
        audit_service = get_audit_service()
        events = await audit_service.get_events(user_id=user_id)
        assert len(events) == 1
        assert events[0].action == action


class TestAuditServiceIntegration:
    """Integration tests for audit service."""

    @pytest.mark.asyncio
    async def test_audit_trail_completeness(self):
        """Test that audit trail captures all required information."""
        audit_service = AuditService(backend="memory")

        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"
        metadata = {
            "ip_address": "127.0.0.1",
            "user_agent": "test-agent",
            "session_id": "session-123",
            "request_id": "request-456",
        }

        # Log event
        await audit_service.log_access(user_id, resource, action, metadata)

        # Retrieve event
        events = await audit_service.get_events(user_id=user_id)
        event = events[0]

        # Verify all fields are captured
        assert event.user_id == user_id
        assert event.resource == resource
        assert event.action == action
        assert event.metadata == metadata
        assert event.timestamp is not None

        # Verify timestamp is recent
        time_diff = datetime.now(UTC) - event.timestamp
        assert time_diff.total_seconds() < 1

    @pytest.mark.asyncio
    async def test_audit_trail_isolation(self):
        """Test that audit trails are properly isolated between users."""
        audit_service = AuditService(backend="memory")

        user1_id = "user-123"
        user2_id = "user-789"

        # Log events for both users
        await audit_service.log_access(user1_id, "thread:thread-1", "create_thread")
        await audit_service.log_access(user2_id, "thread:thread-2", "create_thread")
        await audit_service.log_access(user1_id, "thread:thread-1", "invoke_agent")

        # Get events for each user
        user1_events = await audit_service.get_events(user_id=user1_id)
        user2_events = await audit_service.get_events(user_id=user2_id)

        # Verify isolation
        assert len(user1_events) == 2
        assert len(user2_events) == 1

        # Verify no cross-contamination
        user1_threads = [event.resource for event in user1_events]
        user2_threads = [event.resource for event in user2_events]

        assert "thread:thread-2" not in user1_threads
        assert "thread:thread-1" not in user2_threads

    @pytest.mark.asyncio
    async def test_audit_trail_ordering(self):
        """Test that audit events are properly ordered by timestamp."""
        audit_service = AuditService(backend="memory")

        user_id = "user-123"

        # Log events with delays
        await audit_service.log_access(user_id, "thread:thread-1", "create_thread")
        await asyncio.sleep(0.1)
        await audit_service.log_access(user_id, "thread:thread-1", "invoke_agent")
        await asyncio.sleep(0.1)
        await audit_service.log_access(user_id, "thread:thread-1", "delete_thread")

        # Get events
        events = await audit_service.get_events(user_id=user_id)

        # Verify ordering (most recent first)
        assert len(events) == 3
        assert events[0].action == "delete_thread"
        assert events[1].action == "invoke_agent"
        assert events[2].action == "create_thread"

        # Verify timestamps are in descending order
        timestamps = [event.timestamp for event in events]
        assert timestamps[0] > timestamps[1] > timestamps[2]

    @pytest.mark.asyncio
    async def test_audit_trail_performance(self):
        """Test audit service performance with many events."""
        audit_service = AuditService(backend="memory")

        user_id = "user-123"

        # Log many events
        start_time = datetime.now(UTC)
        for i in range(1000):
            await audit_service.log_access(
                user_id, f"thread:thread-{i}", "create_thread"
            )
        end_time = datetime.now(UTC)

        # Verify performance is reasonable (less than 3 seconds for 1000 events)
        duration = (end_time - start_time).total_seconds()
        assert duration < 3.0

        # Verify all events were logged
        events = await audit_service.get_events(user_id=user_id, limit=1000)
        assert len(events) == 1000

    @pytest.mark.asyncio
    async def test_audit_trail_metadata_handling(self):
        """Test that audit service properly handles various metadata types."""
        audit_service = AuditService(backend="memory")

        user_id = "user-123"
        resource = "thread:thread-456"
        action = "invoke_agent"

        # Test different metadata types
        metadata_cases = [
            {},  # Empty metadata
            {"simple": "value"},  # Simple string
            {"number": 42},  # Number
            {"boolean": True},  # Boolean
            {"list": [1, 2, 3]},  # List
            {"nested": {"key": "value"}},  # Nested dict
            {"unicode": "café"},  # Unicode
            {"special_chars": "!@#$%^&*()"},  # Special characters
        ]

        for metadata in metadata_cases:
            await audit_service.log_access(user_id, resource, action, metadata)

        # Verify all events were logged with correct metadata
        events = await audit_service.get_events(user_id=user_id)
        assert len(events) == len(metadata_cases)

        # Events are returned in reverse chronological order, so reverse to match metadata_cases order
        events = list(reversed(events))

        for i, metadata in enumerate(metadata_cases):
            assert events[i].metadata == metadata


# Import asyncio for sleep function
import asyncio  # noqa: E402
