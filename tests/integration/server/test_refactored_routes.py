"""
Integration tests for refactored routes.

Tests the integration between HTTP routes and conversation handlers
using the new interface-based architecture.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from nalai.core.conversation import ConversationHandler, ConversationResult
from nalai.server.schemas import (
    ListConversationsResponse,
    LoadConversationResponse,
)


class TestRefactoredRoutesIntegration:
    """Test integration between routes and conversation handlers."""

    @pytest.fixture
    def mock_conversation_handler(self):
        """Create a mock conversation handler."""
        handler = AsyncMock(spec=ConversationHandler)
        return handler

    @pytest.fixture
    def client(self, mock_conversation_handler):
        """Create a test client with mocked conversation handler."""
        from nalai.server.app import create_app
        from nalai.server.routes_refactored import create_conversation_routes

        app = create_app()

        # Mock the conversation handler injection
        with patch(
            "nalai.server.routes_refactored.ConversationHandlerInterface"
        ) as mock_interface:
            mock_interface.return_value = mock_conversation_handler
            create_conversation_routes(app, mock_conversation_handler)

        return TestClient(app)

    @pytest.mark.asyncio
    async def test_create_conversation_json_response(
        self, client, mock_conversation_handler
    ):
        """Test create conversation with JSON response."""
        # Arrange
        request_data = {
            "messages": [{"content": "Hello", "type": "human"}],
            "model_config": {"platform": "ollama", "model": "llama3.2"},
        }

        expected_result = ConversationResult(
            conversation_id="test-123",
            output={"messages": [{"content": "Hello", "type": "ai"}]},
            streaming=False,
        )
        mock_conversation_handler.create_conversation.return_value = expected_result

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.post(
                "/api/v1/conversations",
                json=request_data,
                headers={"Accept": "application/json"},
            )

        # Assert
        assert response.status_code == 200
        assert response.json() == {"output": expected_result.output}
        assert response.headers["X-Conversation-ID"] == expected_result.conversation_id

        # Verify handler was called
        mock_conversation_handler.create_conversation.assert_called_once()
        call_args = mock_conversation_handler.create_conversation.call_args
        assert call_args[0][1] == "user123"  # user_id
        assert call_args[0][2] == "mock_context"  # user_context

    @pytest.mark.asyncio
    async def test_create_conversation_streaming_response(
        self, client, mock_conversation_handler
    ):
        """Test create conversation with streaming response."""
        # Arrange
        request_data = {
            "messages": [{"content": "Hello", "type": "human"}],
            "model_config": {"platform": "ollama", "model": "llama3.2"},
        }

        # Mock streaming response
        async def mock_stream():
            yield 'data: {"messages": [{"content": "Hello", "type": "ai"}]}\n\n'

        mock_conversation_handler.stream_conversation.return_value = mock_stream()

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.post(
                "/api/v1/conversations",
                json=request_data,
                headers={"Accept": "text/event-stream"},
            )

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
        assert "Hello" in response.text

    @pytest.mark.asyncio
    async def test_continue_conversation_success(
        self, client, mock_conversation_handler
    ):
        """Test continue conversation with valid conversation ID."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        request_data = {
            "messages": [{"content": "Continue", "type": "human"}],
            "model_config": {"platform": "ollama", "model": "llama3.2"},
        }

        expected_result = ConversationResult(
            conversation_id=conversation_id,
            output={"messages": [{"content": "Continued", "type": "ai"}]},
            streaming=False,
        )
        mock_conversation_handler.continue_conversation.return_value = expected_result

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.post(
                f"/api/v1/conversations/{conversation_id}",
                json=request_data,
                headers={"Accept": "application/json"},
            )

        # Assert
        assert response.status_code == 200
        assert response.json() == {"output": expected_result.output}
        assert response.headers["X-Conversation-ID"] == conversation_id

    @pytest.mark.asyncio
    async def test_continue_conversation_invalid_uuid(self, client):
        """Test continue conversation with invalid UUID."""
        # Arrange
        invalid_conversation_id = "invalid-uuid"
        request_data = {
            "messages": [{"content": "Continue", "type": "human"}],
            "model_config": {"platform": "ollama", "model": "llama3.2"},
        }

        # Act
        response = client.post(
            f"/api/v1/conversations/{invalid_conversation_id}", json=request_data
        )

        # Assert
        assert response.status_code == 422
        assert "Invalid conversation ID format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_load_conversation_success(self, client, mock_conversation_handler):
        """Test load conversation with valid conversation ID."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"

        expected_response = LoadConversationResponse(
            conversation_id=conversation_id,
            messages=[{"content": "Hello", "type": "human"}],
            metadata={"title": "Test conversation"},
            status="active",
        )
        mock_conversation_handler.load_conversation.return_value = expected_response

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.get(f"/api/v1/conversations/{conversation_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conversation_id
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_load_conversation_not_found(self, client, mock_conversation_handler):
        """Test load conversation that doesn't exist."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"

        from nalai.core.conversation.exceptions import ConversationNotFoundError

        mock_conversation_handler.load_conversation.side_effect = (
            ConversationNotFoundError()
        )

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.get(f"/api/v1/conversations/{conversation_id}")

        # Assert
        assert response.status_code == 404
        assert "Conversation not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_conversations_success(self, client, mock_conversation_handler):
        """Test list conversations for user."""
        # Arrange
        expected_response = ListConversationsResponse(conversations=[], total_count=0)
        mock_conversation_handler.list_conversations.return_value = expected_response

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.get("/api/v1/conversations")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["conversations"] == []

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, client, mock_conversation_handler):
        """Test delete conversation successfully."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_conversation_handler.delete_conversation.return_value = True

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.delete(f"/api/v1/conversations/{conversation_id}")

        # Assert
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_resume_decision_success(self, client, mock_conversation_handler):
        """Test resume decision with approve decision."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        request_data = {
            "input": {
                "decision": "approve",
                "tool_calls": [
                    {"name": "http_request", "args": {"url": "https://api.example.com"}}
                ],
            }
        }

        expected_result = ConversationResult(
            conversation_id=conversation_id,
            output={"messages": [{"content": "Tool executed", "type": "ai"}]},
            streaming=False,
        )
        mock_conversation_handler.handle_resume_decision.return_value = expected_result

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/resume-decision",
                json=request_data,
                headers={"Accept": "application/json"},
            )

        # Assert
        assert response.status_code == 200
        assert response.json() == {"output": expected_result.output}
        assert response.headers["X-Conversation-ID"] == conversation_id

    @pytest.mark.asyncio
    async def test_error_handling_access_denied(
        self, client, mock_conversation_handler
    ):
        """Test error handling for access denied."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        request_data = {
            "messages": [{"content": "Continue", "type": "human"}],
            "model_config": {"platform": "ollama", "model": "llama3.2"},
        }

        from nalai.core.conversation.exceptions import AccessDeniedError

        mock_conversation_handler.continue_conversation.side_effect = (
            AccessDeniedError()
        )

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.post(
                f"/api/v1/conversations/{conversation_id}", json=request_data
            )

        # Assert
        assert response.status_code == 403
        assert "Access denied to conversation" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_error_handling_validation_error(
        self, client, mock_conversation_handler
    ):
        """Test error handling for validation error."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        request_data = {
            "messages": [{"content": "Continue", "type": "human"}],
            "model_config": {"platform": "ollama", "model": "llama3.2"},
        }

        from nalai.core.conversation.exceptions import ValidationError

        mock_conversation_handler.continue_conversation.side_effect = ValidationError(
            "Invalid input"
        )

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.post(
                f"/api/v1/conversations/{conversation_id}", json=request_data
            )

        # Assert
        assert response.status_code == 422
        assert "Invalid input" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_error_handling_internal_error(
        self, client, mock_conversation_handler
    ):
        """Test error handling for internal conversation handler error."""
        # Arrange
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        request_data = {
            "messages": [{"content": "Continue", "type": "human"}],
            "model_config": {"platform": "ollama", "model": "llama3.2"},
        }

        from nalai.core.conversation.exceptions import ConversationHandlerError

        mock_conversation_handler.continue_conversation.side_effect = (
            ConversationHandlerError("Internal error")
        )

        # Mock user context
        with patch(
            "nalai.server.routes_refactored.get_user_context_safe"
        ) as mock_context:
            mock_context.return_value = ("user123", "mock_context")

            # Act
            response = client.post(
                f"/api/v1/conversations/{conversation_id}", json=request_data
            )

        # Assert
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
