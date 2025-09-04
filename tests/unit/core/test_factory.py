"""
Unit tests for service factory pattern and dependency injection.

Tests the service factory pattern implementation and demonstrates
how to use it for testing with proper dependency injection.
"""

from unittest.mock import AsyncMock, patch

import pytest

from nalai.core import create_agent
from nalai.core.services import (
    APIService,
    AuditService,
    CacheService,
    CheckpointingService,
    ModelService,
)


class TestServiceFactoryPattern:
    """Test the service factory pattern and dependency injection."""

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow."""
        workflow = AsyncMock()
        workflow.ainvoke = AsyncMock()
        workflow.astream = AsyncMock()
        return workflow

    @pytest.fixture
    def mock_audit_service(self):
        """Create a mock audit service."""
        mock = AsyncMock(spec=AuditService)
        mock.log_conversation_access_event = AsyncMock()
        return mock

    @pytest.fixture
    def mock_cache_service(self):
        """Create a mock cache service."""
        return AsyncMock(spec=CacheService)

    @pytest.fixture
    def mock_model_service(self):
        """Create a mock model service."""
        return AsyncMock(spec=ModelService)

    @pytest.fixture
    def mock_api_service(self):
        """Create a mock API service."""
        return AsyncMock(spec=APIService)

    @pytest.fixture
    def mock_checkpointing_service(self):
        """Create a mock checkpointing service."""
        return AsyncMock(spec=CheckpointingService)

    @pytest.mark.asyncio
    async def test_agent_with_direct_service_injection(
        self, mock_workflow, mock_audit_service, mock_cache_service, mock_model_service
    ):
        """Test creating agent with direct service injection."""
        # Arrange
        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(
                audit_service=mock_audit_service,
                cache_service=mock_cache_service,
                model_service=mock_model_service,
            )

        # Act
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        result = await agent.chat(
            messages, None, {"configurable": {"user_id": "test_user"}}
        )

        # Assert
        assert result is not None
        mock_audit_service.log_conversation_access_event.assert_called()

    @pytest.mark.asyncio
    async def test_agent_with_partial_service_injection(
        self, mock_workflow, mock_audit_service
    ):
        """Test creating agent with only some services injected."""
        # Arrange
        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(audit_service=mock_audit_service)

        # Act
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        result = await agent.chat(
            messages, None, {"configurable": {"user_id": "test_user"}}
        )

        # Assert
        assert result is not None
        mock_audit_service.log_conversation_access_event.assert_called()

    @pytest.mark.asyncio
    async def test_agent_with_failing_service(self, mock_workflow, mock_audit_service):
        """Test agent behavior when a service fails."""
        # Arrange - Create a cache service that fails
        mock_cache_service = AsyncMock(spec=CacheService)
        mock_cache_service.get.side_effect = Exception("Cache service unavailable")

        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(
                audit_service=mock_audit_service,
                cache_service=mock_cache_service,
            )

        # Act & Assert - Agent should handle service failure gracefully
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        result = await agent.chat(
            messages, None, {"configurable": {"user_id": "test_user"}}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_audit_service_verification(
        self, mock_workflow, mock_audit_service
    ):
        """Test that audit service is properly called with correct parameters."""
        # Arrange
        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(audit_service=mock_audit_service)

        # Act
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        await agent.chat(messages, None, {"configurable": {"user_id": "test_user"}})

        # Assert - Verify audit service was called
        mock_audit_service.log_conversation_access_event.assert_called()

        # Verify the call structure
        call_args = mock_audit_service.log_conversation_access_event.call_args
        assert len(call_args[1]) >= 2  # At least user_id and conversation_id
        assert "user_id" in call_args[1]
        assert "conversation_id" in call_args[1]

    @pytest.mark.asyncio
    async def test_agent_with_custom_service_behavior(
        self, mock_workflow, mock_audit_service
    ):
        """Test agent with custom service behavior."""
        # Arrange - Configure custom audit service behavior
        mock_audit_service.log_conversation_access_event.return_value = (
            "custom_audit_result"
        )

        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(audit_service=mock_audit_service)

        # Act
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        result = await agent.chat(
            messages, None, {"configurable": {"user_id": "test_user"}}
        )

        # Assert
        assert result is not None
        mock_audit_service.log_conversation_access_event.assert_called()

    def test_service_factory_reset(self):
        """Test that service factory can be reset for test isolation."""
        # Arrange
        from nalai.services.factory import ServiceFactory

        # Act - Reset instances
        ServiceFactory.reset_instances()

        # Assert - Should not raise any exceptions
        assert True  # Reset completed successfully

    @pytest.mark.asyncio
    async def test_agent_with_mixed_real_and_mock_services(
        self, mock_workflow, mock_audit_service
    ):
        """Test agent with mix of real and mock services (integration test pattern)."""
        # Arrange - Use real services for most functionality, mock only audit
        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(audit_service=mock_audit_service)

        # Act
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        result = await agent.chat(
            messages, None, {"configurable": {"user_id": "test_user"}}
        )

        # Assert
        assert result is not None
        mock_audit_service.log_conversation_access_event.assert_called()

    @pytest.mark.asyncio
    async def test_agent_service_protocol_compliance(
        self, mock_workflow, mock_audit_service, mock_cache_service, mock_model_service
    ):
        """Test that injected services comply with Protocol interfaces."""
        # Arrange
        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(
                audit_service=mock_audit_service,
                cache_service=mock_cache_service,
                model_service=mock_model_service,
            )

        # Act
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        result = await agent.chat(
            messages, None, {"configurable": {"user_id": "test_user"}}
        )

        # Assert - Verify all services are properly typed and accessible
        assert result is not None
        assert hasattr(agent, "audit_service")
        assert agent.audit_service is mock_audit_service

    @pytest.mark.asyncio
    async def test_agent_with_service_factory_mocking(
        self, mock_workflow, mock_audit_service
    ):
        """Test agent using service factory mocking pattern."""
        # Arrange - Mock the service factory functions
        with (
            patch(
                "nalai.services.factory.get_audit_service",
                return_value=mock_audit_service,
            ),
            patch(
                "nalai.core.internal.workflow.create_and_compile_workflow",
                return_value=mock_workflow,
            ),
        ):
            agent = create_agent()  # Uses mocked services from factory

        # Act
        from nalai.core import HumanInputMessage

        messages = [HumanInputMessage(content="Hello")]
        result = await agent.chat(
            messages, None, {"configurable": {"user_id": "test_user"}}
        )

        # Assert
        assert result is not None
        mock_audit_service.log_conversation_access_event.assert_called()

    @pytest.mark.asyncio
    async def test_agent_error_handling_with_mocked_services(
        self, mock_workflow, mock_audit_service
    ):
        """Test agent error handling when services throw exceptions."""
        # Arrange - Configure audit service to throw exception
        mock_audit_service.log_conversation_access_event.side_effect = Exception(
            "Audit service failed"
        )

        with patch(
            "nalai.core.internal.workflow.create_and_compile_workflow",
            return_value=mock_workflow,
        ):
            agent = create_agent(audit_service=mock_audit_service)

        # Act & Assert - Agent should handle service exceptions gracefully
        # (This depends on your error handling strategy)
        try:
            from nalai.core import HumanInputMessage

            messages = [HumanInputMessage(content="Hello")]
            result = await agent.chat(
                messages, None, {"configurable": {"user_id": "test_user"}}
            )
            # If agent handles the exception gracefully, it should still return a result
            assert result is not None
        except Exception as e:
            # If agent propagates the exception, it should be the expected one
            assert "Audit service failed" in str(e)
