"""
Unit tests for agent message exchange routes.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.server.api_agent import create_agent_api
from nalai.server.schemas.messages import HumanInputMessage, MessageRequest


@pytest.fixture
def app_and_agent():
    app = FastAPI()
    mock_agent = AsyncMock()
    create_agent_api(app, mock_agent)
    return app, mock_agent


@pytest.fixture
def mock_auth_service():
    """Mock the auth service to avoid authentication issues in tests."""
    with patch("nalai.server.runtime_config.get_user_context") as mock_get_user:
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user.return_value = mock_user_context
        yield mock_get_user


class TestAgentResponses:
    """Test agent responses endpoint."""

    @pytest.mark.asyncio
    async def test_agent_responses_basic_request(
        self, app_and_agent, mock_auth_service
    ):
        """Test basic agent request without conversation_id."""
        app, mock_agent = app_and_agent

        # Mock agent response
        from nalai.core.agent import Message

        mock_message = Message(content="Hello!", type="ai")

        mock_conversation_info = MagicMock(
            conversation_id="conv_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        mock_conversation_info.interrupt_info = (
            None  # Explicitly set to None to avoid MagicMock issues
        )

        mock_agent.chat.return_value = (
            [mock_message],  # messages
            mock_conversation_info,  # conversation_info
        )

        client = TestClient(app)

        request_data = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
            "store": True,
        }

        response = client.post(
            "/api/v1/messages",
            json=request_data,
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "conversation_id" in data
        assert data["conversation_id"] is not None
        assert "previous_response_id" in data
        assert (
            data["previous_response_id"] is None
        )  # No previous response for basic request
        assert "status" in data
        assert data["status"] == "completed"
        assert "output" in data
        assert len(data["output"]) > 0

        # Verify agent was called
        mock_agent.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_responses_with_conversation_id(
        self, app_and_agent, mock_auth_service
    ):
        """Test agent request with existing conversation_id."""
        app, mock_agent = app_and_agent

        # Mock agent response
        from nalai.core.agent import Message

        mock_message = Message(content="How can I help?", type="ai")

        mock_conversation_info = MagicMock(
            conversation_id="conv_abc123def456ghi789jkm2n3p4q5r6s7t8u9"
        )
        mock_conversation_info.interrupt_info = (
            None  # Explicitly set to None to avoid MagicMock issues
        )

        mock_agent.chat.return_value = (
            [mock_message],  # messages
            mock_conversation_info,  # conversation_info
        )

        client = TestClient(app)

        request_data = {
            "conversation_id": "conv_abc123def456ghi789jkm2n3p4q5r6s7t8u9",
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Continue our conversation"}],
                }
            ],
            "stream": "off",
            "store": True,
        }

        response = client.post(
            "/api/v1/messages",
            json=request_data,
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify conversation_id is preserved
        assert data["conversation_id"] == "conv_abc123def456ghi789jkm2n3p4q5r6s7t8u9"

        # Verify agent was called with correct conversation_id
        call_args = mock_agent.chat.call_args
        assert (
            call_args[0][1] == "conv_abc123def456ghi789jkm2n3p4q5r6s7t8u9"
        )  # conversation_id parameter

    @pytest.mark.asyncio
    async def test_agent_responses_with_previous_response_id(
        self, app_and_agent, mock_auth_service
    ):
        """Test agent request with previous_response_id."""
        app, mock_agent = app_and_agent

        # Mock agent response
        from nalai.core.agent import Message

        mock_message = Message(content="Continuing from previous response", type="ai")

        mock_conversation_info = MagicMock(
            conversation_id="conv_xyz789abc123def456ghi789jkm2n3p4q5r6s7t8u9"
        )
        mock_conversation_info.interrupt_info = None

        mock_agent.chat.return_value = (
            [mock_message],  # messages
            mock_conversation_info,  # conversation_info
        )

        client = TestClient(app)

        request_data = {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Continue from previous response"}
                    ],
                }
            ],
            "previous_response_id": "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9",
            "stream": "off",
            "store": True,
        }

        response = client.post(
            "/api/v1/messages",
            json=request_data,
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify previous_response_id is included in response
        assert "previous_response_id" in data
        assert data["previous_response_id"] == "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"

        # Verify agent was called with correct previous_response_id
        call_args = mock_agent.chat.call_args
        assert (
            call_args[0][3] == "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )  # previous_response_id parameter

    @pytest.mark.asyncio
    async def test_agent_responses_validation_error(
        self, app_and_agent, mock_auth_service
    ):
        """Test agent request with validation error."""
        app, mock_agent = app_and_agent

        client = TestClient(app)

        # Invalid request - empty input
        request_data = {"input": [], "stream": "off", "store": True}

        response = client.post("/api/v1/messages", json=request_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_agent_responses_streaming(self, app_and_agent, mock_auth_service):
        """Test agent request with streaming."""
        app, mock_agent = app_and_agent

        # Mock streaming response
        async def mock_stream():
            yield "Hello"
            yield " World"

        mock_conversation_info = MagicMock(conversation_id="conv_stream")
        mock_agent.chat_streaming.return_value = (
            mock_stream(),  # stream generator
            mock_conversation_info,  # conversation_info
        )

        client = TestClient(app)

        request_data = {
            "input": [
                {"role": "user", "content": [{"type": "text", "text": "Stream this"}]}
            ],
            "stream": "full",
            "store": True,
        }

        response = client.post(
            "/api/v1/messages",
            json=request_data,
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Note: X-Conversation-ID header is only set when conversation_id is not None
        # In this test, conversation_id is None (new conversation), so header won't be set

    @pytest.mark.parametrize(
        "stream_value,accept_header,expected_error_message",
        [
            (
                "full",
                "application/json",
                "Incompatible transport: stream=full requires Accept: text/event-stream",
            ),
            (
                "events",
                "application/json",
                "Incompatible transport: stream=events requires Accept: text/event-stream",
            ),
            (
                "off",
                "text/event-stream",
                "Incompatible transport: stream=off requires Accept: application/json",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_agent_responses_streaming_validation_406(
        self,
        app_and_agent,
        mock_auth_service,
        stream_value,
        accept_header,
        expected_error_message,
    ):
        """Test 406 errors for incompatible transport combinations."""
        app, mock_agent = app_and_agent

        client = TestClient(app)

        request_data = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": stream_value,
            "store": True,
        }

        response = client.post(
            "/api/v1/messages",
            json=request_data,
            headers={"Accept": accept_header},
        )

        assert response.status_code == 406
        assert expected_error_message in response.json()["detail"]


class TestResponseSchemas:
    """Test response schema validation."""

    def test_human_message_input_validation(self):
        """Test HumanMessageInput validation."""
        # Valid input
        valid_input = HumanInputMessage(
            role="user", content=[{"type": "text", "text": "Hello"}]
        )
        assert valid_input.role == "user"
        assert len(valid_input.content) == 1

        # Invalid input - empty content
        with pytest.raises(ValueError):  # Pydantic validation error for empty list
            HumanInputMessage(role="user", content=[])

    def test_tool_decision_input_validation(self):
        """Test ToolDecisionInput validation."""
        # Valid accept decision
        valid_accept = {
            "type": "tool_decision",
            "tool_call_id": "call_123",
            "decision": "accept",
        }
        # This should not raise an error
        from nalai.server.schemas.messages import ToolDecisionInputMessage

        ToolDecisionInputMessage(**valid_accept)

        # Valid edit decision with args
        valid_edit = {
            "type": "tool_decision",
            "tool_call_id": "call_123",
            "decision": "edit",
            "args": {"location": "NYC"},
        }
        ToolDecisionInputMessage(**valid_edit)

        # Invalid edit decision without args
        with pytest.raises(ValueError, match="Args are required for edit decision"):
            ToolDecisionInputMessage(
                type="tool_decision",
                tool_call_id="call_123",
                decision="edit",
                args=None,
            )

    def test_response_request_validation(self):
        """Test MessageRequest validation."""
        # Valid request
        valid_request = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
            "store": True,
        }

        request = MessageRequest(**valid_request)
        assert request.stream == "off"
        assert request.store is True
        assert len(request.input) == 1

        # Invalid request - empty input
        with pytest.raises(ValueError):  # Pydantic validation error
            MessageRequest(input=[], stream=False, store=True)
