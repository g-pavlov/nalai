"""
Unit tests for server routes.
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
from nalai.server.api_conversations import (
    create_conversations_api,
    handle_agent_errors,
)


@pytest.fixture
def app_and_agent():
    app = FastAPI()
    mock_agent = AsyncMock()
    from nalai.server.api_system import create_server_api

    create_server_api(app)
    create_conversations_api(app, mock_agent)
    create_agent_api(app, mock_agent)
    return app, mock_agent


@pytest.fixture
def mock_auth_service():
    """Mock the auth service to avoid authentication issues in tests."""
    with patch("nalai.services.auth_service.get_auth_service") as mock_get_auth:
        mock_auth = AsyncMock()
        mock_identity = MagicMock()
        mock_identity.user_id = "test-user"
        mock_identity.email = "test@example.com"
        mock_auth.authenticate_request.return_value = mock_identity
        mock_get_auth.return_value = mock_auth
        yield mock_auth


@pytest.fixture
def mock_middleware_auth():
    """Mock auth middleware to avoid authentication issues in tests."""
    with patch("nalai.services.auth_service.get_auth_service") as mock_get_auth:
        mock_auth = AsyncMock()
        mock_identity = MagicMock()
        mock_identity.user_id = "test-user"
        mock_identity.email = "test@example.com"
        mock_auth.authenticate_request.return_value = mock_identity
        mock_get_auth.return_value = mock_auth
        yield mock_auth


@pytest.fixture
def client(app_and_agent):
    app, _ = app_and_agent
    return TestClient(app)


class TestHelperFunctions:
    """Test helper functions extracted from routes."""

    # def test_get_conversation_headers(self):
    #     """Should return correct conversation headers."""
    #     conversation_id = "test-conversation-123"
    #     headers = get_conversation_headers(conversation_id)

    #     assert headers == {"X-Conversation-ID": conversation_id}
    #     assert isinstance(headers, dict)

    # @pytest.mark.parametrize(
    #     "accept_header,expected",
    #     [
    #         ("text/event-stream", True),
    #         ("application/json, text/event-stream", True),
    #         ("text/event-stream, application/json", True),
    #         ("application/json", False),
    #         ("", False),  # Empty string doesn't contain "text/event-stream"
    #         (None, True),  # Default behavior when header is missing
    #     ],
    # )
    # def test_is_streaming_request(self, accept_header, expected):
    #     """Should correctly detect streaming requests."""
    #     from unittest.mock import Mock

    #     from fastapi import Request

    #     mock_request = Mock(spec=Request)
    #     mock_request.headers = (
    #         {"accept": accept_header} if accept_header is not None else {}
    #     )

    #     result = is_streaming_request(mock_request)
    #     assert result == expected

    @pytest.mark.parametrize(
        "error_class,error_message,expected_status,expected_detail",
        [
            (None, None, None, "success"),  # Success case
            ("ValidationError", "Invalid input", 422, "Invalid input"),
            ("AccessDeniedError", "Access denied", 403, "Access denied"),
            (
                "ConversationNotFoundError",
                "Conversation not found",
                404,
                "Conversation not found",
            ),
            ("InvocationError", "Internal error", 500, "Internal server error"),
        ],
    )
    @pytest.mark.asyncio
    async def test_handle_agent_errors(
        self, error_class, error_message, expected_status, expected_detail
    ):
        """Should handle all agent error types correctly."""
        from nalai.core.agent import (
            AccessDeniedError,
            ConversationNotFoundError,
            InvocationError,
            ValidationError,
        )

        @handle_agent_errors
        async def test_func():
            if error_class is None:
                return "success"

            error_map = {
                "ValidationError": ValidationError,
                "AccessDeniedError": AccessDeniedError,
                "ConversationNotFoundError": ConversationNotFoundError,
                "InvocationError": InvocationError,
            }
            raise error_map[error_class](error_message)

        if error_class is None:
            # Success case
            result = await test_func()
            assert result == expected_detail
        else:
            # Error cases
            with pytest.raises(Exception) as exc_info:
                await test_func()

            assert exc_info.value.status_code == expected_status
            assert expected_detail in str(exc_info.value.detail)


class TestBasicRoutes:
    """Test basic infrastructure endpoints."""

    @pytest.mark.parametrize(
        "path,expected_status,expected_redirect,expected_content",
        [
            ("/", 307, True, None),  # Redirect to docs (FastAPI uses 307)
            ("/healthz", 200, False, {"status": "Healthy"}),  # Health check
        ],
    )
    def test_basic_routes(
        self, client, path, expected_status, expected_redirect, expected_content
    ):
        """Critical: Basic infrastructure endpoints should work correctly."""
        response = client.get(path, follow_redirects=False)

        assert response.status_code == expected_status

        if expected_redirect:
            assert response.headers["location"] == "/docs"
        elif expected_content:
            assert response.json() == expected_content


class TestAgentAPI:
    """Test agent API responses (/api/v1/messages) - critical business logic."""

    @patch("nalai.server.runtime_config.get_user_context")
    def test_successful_agent_responses(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should return proper agent response structure."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Mock agent to return tuple (messages, conversation_info) as expected by the interface
        from langchain_core.messages import AIMessage, HumanMessage

        mock_messages = [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = "test-conversation-123"
        mock_conversation_info.interrupt_info = None
        mock_agent.chat.return_value = (mock_messages, mock_conversation_info)

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        # Test OpenAI-compatible fields
        assert "id" in response_data
        assert "conversation_id" in response_data
        assert "output" in response_data
        assert "usage" in response_data
        assert "created_at" in response_data

        # Test agent-specific fields
        assert "status" in response_data
        assert response_data["status"] == "completed"
        assert "interrupts" in response_data
        assert response_data["interrupts"] is None
        assert "metadata" in response_data

        # Test output structure
        assert isinstance(response_data["output"], list)
        assert len(response_data["output"]) == 2

        # Test message structure
        for message in response_data["output"]:
            assert "id" in message
            assert "role" in message
            assert "content" in message
            assert isinstance(message["content"], list)
            assert len(message["content"]) > 0
            assert message["content"][0]["type"] == "text"
            assert "text" in message["content"][0]

            # Only assistant messages have metadata (usage and finish_reason)
            if message["role"] == "assistant":
                assert "finish_reason" in message
                assert "usage" in message

        mock_agent.chat.assert_called_once()

    @patch("nalai.server.runtime_config.get_user_context")
    def test_agent_responses_with_tool_calls(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should handle messages with tool calls."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Mock agent with tool calls
        from langchain_core.messages import AIMessage, HumanMessage

        mock_messages = [
            HumanMessage(content="Hello"),
            AIMessage(
                content="I'll check the weather for you.",
                tool_calls=[
                    {
                        "id": "call_123",
                        "type": "function",
                        "name": "get_weather",
                        "args": {"location": "Seattle"},
                    }
                ],
            ),
        ]
        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = "test-conversation-123"
        mock_conversation_info.interrupt_info = None
        mock_conversation_info.interrupt_info = None
        mock_agent.chat.return_value = (mock_messages, mock_conversation_info)

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        # Find AI message with tool calls
        ai_message = None
        for message in response_data["output"]:
            if message["role"] == "assistant":
                ai_message = message
                break

        assert ai_message is not None
        assert "tool_calls" in ai_message
        assert ai_message["tool_calls"] is not None
        assert len(ai_message["tool_calls"]) == 1
        assert ai_message["tool_calls"][0]["id"] == "call_123"

    @patch("nalai.server.runtime_config.get_user_context")
    def test_agent_responses_with_interrupt(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should handle interrupted responses."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Mock agent with interrupt - agent stores interrupt in conversation_info
        from langchain_core.messages import AIMessage, HumanMessage

        mock_messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="I'll check the weather for you."),
        ]

        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = "test-conversation-123"
        mock_conversation_info.interrupt_info = None
        mock_conversation_info.interrupt_info = {
            "type": "tool_call",
            "tool_call_id": "call_123",
            "action": "get_weather",
            "args": {"location": "Seattle"},
            "config": {"timeout": 30},
        }

        # Mock agent to return messages with interrupt
        mock_agent.chat.return_value = (mock_messages, mock_conversation_info)

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        # Test interrupt handling
        assert response_data["status"] == "interrupted"
        assert response_data["interrupts"] is not None
        assert response_data["interrupts"][0]["type"] == "tool_call"
        assert response_data["interrupts"][0]["tool_call_id"] == "call_123"
        assert response_data["interrupts"][0]["action"] == "get_weather"
        assert response_data["interrupts"][0]["args"]["location"] == "Seattle"

    @patch("nalai.server.runtime_config.get_user_context")
    def test_agent_responses_error_handling(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should handle errors properly."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Mock agent to raise exception
        mock_agent.chat.side_effect = Exception("Test error")

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        assert (
            response.status_code == 200
        )  # Error responses are still 200 with error status
        response_data = response.json()

        # Test error handling
        assert response_data["status"] == "error"
        assert response_data["interrupts"] is None
        assert response_data["metadata"] is not None
        assert "error" in response_data["metadata"]
        assert response_data["metadata"]["error"] == "Test error"
        assert response_data["output"] == []

    @patch("nalai.server.runtime_config.get_user_context")
    def test_agent_responses_metadata_structure(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should have proper metadata structure."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Mock agent with metadata
        from langchain_core.messages import AIMessage, HumanMessage

        mock_messages = [
            HumanMessage(content="Hello"),
            AIMessage(
                content="Hi there!",
                finish_reason="stop",
                usage={"completion_tokens": 5},
            ),
        ]
        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = "test-conversation-123"
        mock_conversation_info.interrupt_info = None
        mock_conversation_info.interrupt_info = None
        mock_agent.chat.return_value = (mock_messages, mock_conversation_info)

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        # Test response metadata structure - should be null for successful responses
        assert response_data["metadata"] is None

        # Test message metadata structure
        ai_message = None
        for message in response_data["output"]:
            if message["role"] == "assistant":
                ai_message = message
                break

        assert ai_message is not None
        # finish_reason and usage are now top-level fields in AssistantOutputMessage
        assert "finish_reason" in ai_message
        assert "usage" in ai_message

        # Test actual values
        assert ai_message["finish_reason"] == "stop"
        assert ai_message["usage"]["completion_tokens"] == 5

    @pytest.mark.parametrize(
        "error_type,error_message,expected_error_in_metadata",
        [
            # Agent-specific errors
            (
                "AccessDeniedError",
                "Access denied to conversation",
                "Access denied to conversation",
            ),
            (
                "ConversationNotFoundError",
                "Conversation not found",
                "Conversation not found",
            ),
            ("InvocationError", "Agent invocation failed", "Agent invocation failed"),
            (
                "ValidationError",
                "Invalid conversation format",
                "Invalid conversation format",
            ),
            # Infrastructure errors
            (
                "DatabaseError",
                "Database connection failed",
                "Database connection failed",
            ),
            ("TimeoutError", "Model service timeout", "Model service timeout"),
            ("MemoryError", "Out of memory", "Out of memory"),
            ("NetworkError", "Network connection failed", "Network connection failed"),
            # Generic errors
            ("Exception", "Unexpected error occurred", "Unexpected error occurred"),
            ("RuntimeError", "Runtime error in agent", "Runtime error in agent"),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    def test_agent_responses_different_error_types(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
        error_type,
        error_message,
        expected_error_in_metadata,
    ):
        """Critical: Should handle different types of agent errors properly."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Create the appropriate error type
        if error_type == "AccessDeniedError":
            from nalai.core.agent import AccessDeniedError

            error = AccessDeniedError(error_message)
        elif error_type == "ConversationNotFoundError":
            from nalai.core.agent import ConversationNotFoundError

            error = ConversationNotFoundError(error_message)
        elif error_type == "InvocationError":
            from nalai.core.agent import InvocationError

            error = InvocationError(error_message)
        elif error_type == "ValidationError":
            from nalai.core.agent import ValidationError

            error = ValidationError(error_message)
        elif error_type == "DatabaseError":
            error = Exception(f"DatabaseError: {error_message}")
        elif error_type == "TimeoutError":
            error = Exception(f"TimeoutError: {error_message}")
        elif error_type == "MemoryError":
            error = Exception(f"MemoryError: {error_message}")
        elif error_type == "NetworkError":
            error = Exception(f"NetworkError: {error_message}")
        elif error_type == "RuntimeError":
            error = RuntimeError(error_message)
        else:  # Generic Exception
            error = Exception(error_message)

        # Mock agent to raise the specific error
        mock_agent.chat.side_effect = error

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        # Agent-specific errors should return proper HTTP status codes
        if error_type in [
            "AccessDeniedError",
            "ConversationNotFoundError",
            "InvocationError",
            "ValidationError",
        ]:
            # These should return HTTP error status codes, not 200
            expected_status = {
                "AccessDeniedError": 403,
                "ConversationNotFoundError": 404,
                "InvocationError": 500,
                "ValidationError": 422,
            }[error_type]
            assert response.status_code == expected_status
            response_data = response.json()
            assert "detail" in response_data

            # InvocationError returns generic message for security
            if error_type == "InvocationError":
                assert response_data["detail"] == "Internal server error"
            else:
                assert expected_error_in_metadata in response_data["detail"]
        else:
            # Other errors (infrastructure, generic) should still return 200 with error status
            assert response.status_code == 200
            response_data = response.json()

            # Test error handling
            assert response_data["status"] == "error"
            assert response_data["interrupts"] is None
            assert response_data["metadata"] is not None
            assert "error" in response_data["metadata"]
            assert expected_error_in_metadata in response_data["metadata"]["error"]
            assert response_data["output"] == []

    @pytest.mark.parametrize(
        "agent_error,expected_error_message",
        [
            # Agent-specific errors that should be reflected in response metadata
            ("AccessDeniedError", "Access denied to conversation"),
            ("ConversationNotFoundError", "Conversation not found"),
            ("InvocationError", "Agent invocation failed"),
            ("ValidationError", "Invalid conversation format"),
            (
                "ClientError",
                "An assistant message with 'tool_calls' must be followed by tool messages",
            ),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    def test_agent_injected_errors_reflected_in_response(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
        agent_error,
        expected_error_message,
    ):
        """Critical: Agent-injected errors should be properly reflected in API response."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Create the appropriate agent error
        if agent_error == "AccessDeniedError":
            from nalai.core.agent import AccessDeniedError

            error = AccessDeniedError(expected_error_message)
        elif agent_error == "ConversationNotFoundError":
            from nalai.core.agent import ConversationNotFoundError

            error = ConversationNotFoundError(expected_error_message)
        elif agent_error == "InvocationError":
            from nalai.core.agent import InvocationError

            error = InvocationError(expected_error_message)
        elif agent_error == "ValidationError":
            from nalai.core.agent import ValidationError

            error = ValidationError(expected_error_message)
        elif agent_error == "ClientError":
            from nalai.core.agent import ClientError

            error = ClientError(expected_error_message, http_status=400)

        # Mock agent to inject the specific error
        mock_agent.chat.side_effect = error

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        # Agent-specific errors should return proper HTTP status codes
        expected_status = {
            "AccessDeniedError": 403,
            "ConversationNotFoundError": 404,
            "InvocationError": 500,
            "ValidationError": 422,
            "ClientError": 400,
        }[agent_error]

        assert response.status_code == expected_status
        response_data = response.json()
        assert "detail" in response_data

        # InvocationError returns generic message for security
        if agent_error == "InvocationError":
            assert response_data["detail"] == "Internal server error"
        else:
            assert expected_error_message in response_data["detail"]

    @pytest.mark.parametrize(
        "payload,expected_status",
        [
            ({"input": []}, 422),  # Empty messages
            (
                {
                    "input": [
                        {"role": "user", "content": [{"type": "text", "text": ""}]}
                    ],
                },
                422,
            ),  # Empty content
            ({"input": ""}, 422),  # Empty string
            ({"input": "   "}, 422),  # Whitespace-only string
        ],
    )
    def test_agent_responses_validation_failures(
        self, client, payload, expected_status
    ):
        """Critical: Should reject invalid inputs."""
        response = client.post("/api/v1/messages", json=payload)
        assert response.status_code == expected_status

    @patch("nalai.server.runtime_config.get_user_context")
    def test_agent_responses_string_input(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should handle string input as implicit human message."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        # Mock agent to return tuple (messages, conversation_info) as expected by the interface
        from langchain_core.messages import AIMessage, HumanMessage

        mock_messages = [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = "test-conversation-123"
        mock_conversation_info.interrupt_info = None
        mock_agent.chat.return_value = (mock_messages, mock_conversation_info)

        # Test string input
        payload = {
            "input": "Hello, how are you?",
            "stream": "off",
        }

        response = client.post("/api/v1/messages", json=payload)

        assert response.status_code == 200
        response_data = response.json()

        # Test OpenAI-compatible fields
        assert "id" in response_data
        assert "conversation_id" in response_data
        assert "output" in response_data
        assert "usage" in response_data
        assert "created_at" in response_data

        # Test agent-specific fields
        assert "status" in response_data
        assert response_data["status"] == "completed"
        assert "interrupts" in response_data
        assert response_data["interrupts"] is None
        assert "metadata" in response_data

        # Test output structure
        assert isinstance(response_data["output"], list)
        assert len(response_data["output"]) == 2

        # Test message structure
        for message in response_data["output"]:
            assert "id" in message
            assert "role" in message
            assert "content" in message
            assert isinstance(message["content"], list)
            assert len(message["content"]) > 0
            assert message["content"][0]["type"] == "text"
            assert "text" in message["content"][0]

            # Only assistant messages have metadata (usage and finish_reason)
            if message["role"] == "assistant":
                assert "finish_reason" in message
                assert "usage" in message

        mock_agent.chat.assert_called_once()

        # Verify that the agent was called with a HumanMessage containing the string content
        call_args = mock_agent.chat.call_args
        messages = call_args[0][0]  # First argument is messages
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "Hello, how are you?"


class TestAgentAPIStreamEvents:
    """Test streaming agent API responses (/api/v1/messages) - critical for real-time functionality."""

    @patch("nalai.server.runtime_config.get_user_context")
    def test_successful_agent_stream_events(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should stream agent events with proper SSE format."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_user_context.ip_address = "127.0.0.1"
        mock_user_context.user_agent = "test-agent"
        mock_user_context.session_id = "test-session"
        mock_user_context.request_id = "test-request"
        mock_get_user_context.return_value = mock_user_context

        import json

        mock_event = {"event": "on_chat_model_stream", "data": {"content": "test"}}

        async def async_gen():
            # Yield properly formatted SSE strings like the real implementation
            yield f"data: {json.dumps(mock_event)}\n\n"

        # Mock the chat_streaming method to return tuple (stream_generator, conversation_info)
        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = "test-conversation-123"
        mock_conversation_info.interrupt_info = None
        mock_conversation_info.interrupt_info = None
        mock_agent.chat_streaming.return_value = (async_gen(), mock_conversation_info)

        payload = {
            "input": [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            "stream": "full",
        }

        response = client.post(
            "/api/v1/messages",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        # Note: For agent responses (new conversation), headers are not set in streaming mode
        # This is different from continuing conversations which have the conversation_id upfront

    @pytest.mark.parametrize(
        "payload,expected_status",
        [
            ({"input": []}, 422),  # Empty messages
            (
                {
                    "input": [
                        {"role": "user", "content": [{"type": "text", "text": ""}]}
                    ],
                },
                422,
            ),  # Empty content
        ],
    )
    def test_agent_stream_events_validation_failures(
        self, client, payload, expected_status
    ):
        """Critical: Should reject invalid inputs for streaming."""
        response = client.post(
            "/api/v1/messages",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == expected_status


class TestLoadConversation:
    """Test load conversation functionality."""

    @pytest.mark.parametrize(
        "conversation_id,agent_behavior,expected_status,expected_detail_keyword",
        [
            ("550e8400-e29b-41d4-a716-446655440000", "success", 200, None),
            (
                "550e8400-e29b-41d4-a716-446655440000",
                "access_denied",
                403,
                "Access denied",
            ),
            ("550e8400-e29b-41d4-a716-446655440000", "not_found", 404, "not found"),
            ("invalid-id", "any", 422, None),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.core.checkpoints.get_checkpoints")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    @patch("nalai.server.runtime_config.create_runtime_config")
    def test_load_conversation_scenarios(
        self,
        mock_create_runtime_config,
        mock_get_checkpointer,
        mock_get_checkpoints,
        mock_get_user_context,
        conversation_id,
        agent_behavior,
        expected_status,
        expected_detail_keyword,
        client,
        app_and_agent,
    ):
        """Should handle all load conversation scenarios correctly."""
        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        _, mock_agent = app_and_agent

        # Mock checkpoints for all scenarios
        mock_checkpoints = AsyncMock()
        mock_checkpoints.validate_user_access.return_value = True
        mock_checkpoints.get_conversation_metadata.return_value = {
            "conversation_id": conversation_id,
            "user_id": "test-user",
            "created_at": "2024-01-01T00:00:00",
            "last_accessed": "2024-01-01T12:00:00",
            "message_count": 3,
            "checkpoint_count": 1,
        }
        mock_get_checkpoints.return_value = mock_checkpoints

        # Mock create_runtime_config
        mock_create_runtime_config.return_value = {
            "configurable": {"thread_id": "test-thread"}
        }

        if agent_behavior == "success":
            # Mock successful conversation
            # Create proper BaseMessage objects for the test
            from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

            mock_messages = [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there!"),
                ToolMessage(
                    content="API response", name="test_api", tool_call_id="call_123"
                ),
            ]

            mock_conversation = MagicMock()
            mock_conversation.conversation_id = conversation_id
            mock_conversation.created_at = "2023-01-01T00:00:00Z"
            mock_conversation.last_accessed = "2023-01-01T00:00:00Z"
            mock_conversation.status = "active"
            # Mock agent to return tuple (messages, conversation_info) as expected by the interface
            mock_agent.load_conversation.return_value = (
                mock_messages,
                mock_conversation,
            )

        elif agent_behavior == "access_denied":
            from nalai.core.agent import AccessDeniedError

            mock_agent.load_conversation.side_effect = AccessDeniedError(
                "Access denied"
            )

        elif agent_behavior == "not_found":
            from nalai.core.agent import ConversationNotFoundError

            mock_agent.load_conversation.side_effect = ConversationNotFoundError(
                "Conversation not found"
            )

        response = client.get(f"/api/v1/conversations/{conversation_id}")

        # Debug output
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")

        assert response.status_code == expected_status

        if expected_status == 200:
            data = response.json()
            assert data["conversation_id"] == conversation_id
            assert len(data["messages"]) == 3
            assert data["messages"][0]["role"] == "human"
            assert data["messages"][0]["content"][0]["text"] == "Hello"
            assert data["messages"][1]["role"] == "assistant"
            assert data["messages"][1]["content"][0]["text"] == "Hi there!"
            assert data["messages"][2]["role"] == "tool"
            assert data["messages"][2]["content"][0]["text"] == "API response"
            assert data["messages"][2]["tool_call_id"] == "call_123"
            assert data["status"] == "active"
        elif expected_detail_keyword:
            assert expected_detail_keyword in response.json()["detail"]


class TestListConversations:
    """Test list conversations endpoint."""

    @pytest.mark.parametrize(
        "agent_behavior,expected_status,expected_count,expected_detail_keyword",
        [
            ("success", 200, 2, None),
            ("unauthorized", 403, 0, "Authentication required"),
            ("empty", 200, 0, None),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.core.checkpoints.get_checkpoints")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    def test_list_conversations_scenarios(
        self,
        mock_get_checkpointer,
        mock_get_checkpoints,
        mock_get_user_context,
        agent_behavior,
        expected_status,
        expected_count,
        expected_detail_keyword,
        client,
        app_and_agent,
    ):
        """Should handle all list conversations scenarios correctly."""
        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        _, mock_agent = app_and_agent

        if agent_behavior == "success":
            # Mock successful conversations list
            # Mock successful conversations list with proper string values
            mock_summary1 = MagicMock()
            mock_summary1.conversation_id = "conv-1"
            mock_summary1.created_at = "2023-01-01T12:00:00"
            mock_summary1.last_accessed = (
                "2023-01-02T12:00:00"  # Use last_accessed instead of last_updated
            )
            mock_summary1.preview = "Hello, this is a test message"
            mock_summary1.status = "active"
            mock_summary1.metadata = {"title": "First Conversation"}

            mock_summary2 = MagicMock()
            mock_summary2.conversation_id = "conv-2"
            mock_summary2.created_at = "2023-01-03T12:00:00"
            mock_summary2.last_accessed = (
                "2023-01-04T12:00:00"  # Use last_accessed instead of last_updated
            )
            mock_summary2.preview = "Hello, this is a test message"
            mock_summary2.status = "active"
            mock_summary2.metadata = {"title": "Second Conversation"}

            mock_agent.list_conversations.return_value = [mock_summary1, mock_summary2]

        elif agent_behavior == "unauthorized":
            from nalai.core.agent import AccessDeniedError

            mock_agent.list_conversations.side_effect = AccessDeniedError(
                "Authentication required"
            )

        elif agent_behavior == "empty":
            mock_agent.list_conversations.return_value = []

        response = client.get("/api/v1/conversations")

        assert response.status_code == expected_status

        if expected_status == 200:
            data = response.json()
            assert data["total_count"] == expected_count
            assert len(data["conversations"]) == expected_count

            if expected_count > 0:
                # Check first conversation
                conv1 = data["conversations"][0]
                assert conv1["conversation_id"] == "conv-1"
                assert conv1["created_at"] == "2023-01-01T12:00:00"
                assert conv1["last_updated"] == "2023-01-02T12:00:00"
                assert conv1["preview"] == "Hello, this is a test message"
                assert conv1["metadata"]["title"] == "First Conversation"

                # Check second conversation
                conv2 = data["conversations"][1]
                assert conv2["conversation_id"] == "conv-2"
                assert conv2["created_at"] == "2023-01-03T12:00:00"
                assert conv2["last_updated"] == "2023-01-04T12:00:00"
                assert conv2["preview"] == "Hello, this is a test message"
                assert conv2["metadata"]["title"] == "Second Conversation"
        elif expected_detail_keyword:
            assert expected_detail_keyword in response.json()["detail"]


class TestDeleteConversation:
    """Test delete conversation endpoint."""

    @pytest.mark.parametrize(
        "conversation_id,agent_behavior,expected_status,expected_detail_keyword",
        [
            ("550e8400-e29b-41d4-a716-446655440001", "success", 204, None),
            (
                "550e8400-e29b-41d4-a716-446655440001",
                "access_denied",
                403,
                "Access denied to conversation",
            ),
            (
                "550e8400-e29b-41d4-a716-446655440001",
                "not_found",
                404,
                "Conversation not found",
            ),
            (
                "550e8400-e29b-41d4-a716-446655440001",
                "unauthorized",
                403,
                "Authentication required",
            ),
            ("invalid-id-format", "any", 422, "must be a valid UUID4"),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.core.checkpoints.get_checkpoints")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    def test_delete_conversation_scenarios(
        self,
        mock_get_checkpointer,
        mock_get_checkpoints,
        mock_get_user_context,
        conversation_id,
        agent_behavior,
        expected_status,
        expected_detail_keyword,
        client,
        app_and_agent,
    ):
        """Should handle all delete conversation scenarios correctly."""
        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        _, mock_agent = app_and_agent

        if agent_behavior == "success":
            mock_agent.delete_conversation.return_value = True
        elif agent_behavior == "access_denied":
            from nalai.core.agent import AccessDeniedError

            mock_agent.delete_conversation.side_effect = AccessDeniedError(
                "Access denied to conversation"
            )
        elif agent_behavior == "not_found":
            mock_agent.delete_conversation.return_value = False
        elif agent_behavior == "unauthorized":
            from nalai.core.agent import AccessDeniedError

            mock_agent.delete_conversation.side_effect = AccessDeniedError(
                "Authentication required"
            )

        response = client.delete(f"/api/v1/conversations/{conversation_id}")

        assert response.status_code == expected_status

        if expected_status == 204:
            assert response.content == b""
            mock_agent.delete_conversation.assert_called_once()
        elif expected_detail_keyword:
            assert expected_detail_keyword in response.json()["detail"]
