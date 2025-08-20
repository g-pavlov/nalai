"""
Unit tests for server routes.
"""

import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.server.routes import (
    create_basic_routes,
    create_conversation_routes,
    get_conversation_headers,
    handle_agent_errors,
    is_streaming_request,
)


@pytest.fixture
def app_and_agent():
    app = FastAPI()
    mock_agent = AsyncMock()
    create_basic_routes(app)
    create_conversation_routes(app, mock_agent)
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

    def test_get_conversation_headers(self):
        """Should return correct conversation headers."""
        conversation_id = "test-conversation-123"
        headers = get_conversation_headers(conversation_id)

        assert headers == {"X-Conversation-ID": conversation_id}
        assert isinstance(headers, dict)

    @pytest.mark.parametrize(
        "accept_header,expected",
        [
            ("text/event-stream", True),
            ("application/json, text/event-stream", True),
            ("text/event-stream, application/json", True),
            ("application/json", False),
            ("", False),  # Empty string doesn't contain "text/event-stream"
            (None, True),  # Default behavior when header is missing
        ],
    )
    def test_is_streaming_request(self, accept_header, expected):
        """Should correctly detect streaming requests."""
        from unittest.mock import Mock

        from fastapi import Request

        mock_request = Mock(spec=Request)
        mock_request.headers = (
            {"accept": accept_header} if accept_header is not None else {}
        )

        result = is_streaming_request(mock_request)
        assert result == expected

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


class TestConversationInvoke:
    """Test synchronous conversation invocation - critical business logic."""

    @patch("nalai.server.runtime_config.get_user_context")
    def test_successful_conversation_invoke(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should handle conversation requests correctly."""
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
        mock_agent.chat.return_value = (mock_messages, mock_conversation_info)

        payload = {
            "input": [{"type": "human", "content": "Hello"}],
        }

        response = client.post("/api/v1/conversations", json=payload)

        assert response.status_code == 200
        assert "output" in response.json()
        assert "X-Conversation-ID" in response.headers
        mock_agent.chat.assert_called_once()

    @pytest.mark.parametrize(
        "payload,expected_status",
        [
            ({"input": []}, 422),  # Empty messages
            (
                {
                    "input": [{"type": "human", "content": ""}],
                },
                422,
            ),  # Empty content
        ],
    )
    def test_conversation_invoke_validation_failures(
        self, client, payload, expected_status
    ):
        """Critical: Should reject invalid inputs."""
        response = client.post("/api/v1/conversations", json=payload)
        assert response.status_code == expected_status


class TestConversationStreamEvents:
    """Test streaming conversation events - critical for real-time functionality."""

    @patch("nalai.server.runtime_config.get_user_context")
    def test_successful_stream_events(
        self,
        mock_get_user_context,
        client,
        app_and_agent,
        mock_auth_service,
        mock_middleware_auth,
    ):
        """Critical: Should stream events with proper SSE format."""
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
        mock_agent.chat_streaming.return_value = (async_gen(), mock_conversation_info)

        payload = {
            "input": [{"type": "human", "content": "Hello"}],
        }

        response = client.post(
            "/api/v1/conversations",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        # Note: For create_conversation (new conversation), headers are not set in streaming mode
        # This is different from continue_conversation which has the conversation_id upfront

    @pytest.mark.parametrize(
        "payload,expected_status",
        [
            ({"messages": []}, 422),  # Empty messages
            (
                {
                    "messages": [{"type": "human", "content": ""}],
                },
                422,
            ),  # Empty content
        ],
    )
    def test_stream_events_validation_failures(self, client, payload, expected_status):
        """Critical: Should reject invalid inputs for streaming."""
        response = client.post(
            "/api/v1/conversations",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == expected_status


class TestResumeDecision:
    """Test resume decision functionality - critical for human-in-the-loop."""

    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    def test_resume_decision_stream_success_cases(
        self, mock_get_access_control, mock_get_user_context, client, app_and_agent
    ):
        """Critical: Should handle resume decisions correctly."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        # Mock access control
        mock_access_control = AsyncMock()
        mock_access_control.validate_thread_access.return_value = True
        mock_get_access_control.return_value = mock_access_control

        conversation_id = str(uuid.uuid4())
        print(f"Generated thread_id: user:test-user:{conversation_id}")

        import json

        mock_event = {"event": "on_chat_model_stream", "data": {"content": "test"}}

        async def async_gen():
            # Yield properly formatted SSE strings like the real implementation
            yield f"data: {json.dumps(mock_event)}\n\n"

        # Mock the resume_interrupted_streaming method to return tuple (stream_generator, conversation_info)
        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = conversation_id
        mock_agent.resume_interrupted_streaming.return_value = (
            async_gen(),
            mock_conversation_info,
        )

        payload = {"input": {"decision": "accept"}}

        response = client.post(
            f"/api/v1/conversations/{conversation_id}/resume-decision",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "X-Conversation-ID" in response.headers

    @pytest.mark.parametrize(
        "decision,args,expected_status",
        [
            ("accept", None, 200),
            ("edit", {"url": "https://example.com"}, 200),
            ("reject", None, 200),
        ],
    )
    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    def test_resume_decision_batch_success_cases(
        self,
        mock_get_access_control,
        mock_get_user_context,
        decision,
        args,
        expected_status,
        client,
        app_and_agent,
    ):
        """Critical: Should handle resume decisions in batch mode."""
        _, mock_agent = app_and_agent
        # Mock agent to return tuple (messages, conversation_info) as expected by the interface
        from langchain_core.messages import AIMessage, HumanMessage

        mock_messages = [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
        mock_conversation_info = MagicMock()
        mock_conversation_info.conversation_id = "test-conversation-123"
        mock_agent.resume_interrupted.return_value = (
            mock_messages,
            mock_conversation_info,
        )

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        # Mock access control
        mock_access_control = AsyncMock()
        mock_access_control.validate_thread_access.return_value = True
        mock_get_access_control.return_value = mock_access_control

        conversation_id = str(uuid.uuid4())

        payload = {"input": {"decision": decision}}

        if decision == "edit" and args is not None:
            payload["input"]["args"] = args

        response = client.post(
            f"/api/v1/conversations/{conversation_id}/resume-decision", json=payload
        )

        assert response.status_code == expected_status
        assert "output" in response.json()
        assert "X-Conversation-ID" in response.headers

    @pytest.mark.parametrize(
        "conversation_id,decision,expected_status",
        [
            (
                "invalid-uuid",
                "accept",
                422,
            ),  # Invalid UUID - should be 422 Validation Error
            (
                "12345678-1234-1234-1234-123456789abc",
                "invalid_type",
                422,
            ),  # Invalid decision - should be 422 Validation Error
        ],
    )
    def test_resume_decision_validation_failures(
        self, conversation_id, decision, expected_status, client, app_and_agent
    ):
        """Critical: Should reject invalid resume decision inputs."""
        payload = {"input": {"decision": decision}}

        response = client.post(
            f"/api/v1/conversations/{conversation_id}/resume-decision", json=payload
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
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    @patch("nalai.server.runtime_config.create_runtime_config")
    def test_load_conversation_scenarios(
        self,
        mock_create_runtime_config,
        mock_get_checkpointer,
        mock_get_access_control,
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

        # Mock access control for all scenarios
        mock_access_control = AsyncMock()
        mock_access_control.validate_thread_access.return_value = True
        mock_access_control.create_user_scoped_thread_id.return_value = (
            "user:test-user:550e8400-e29b-41d4-a716-446655440000"
        )
        mock_access_control.get_thread_ownership.return_value = MagicMock(
            metadata={"title": "Test Conversation"},
            created_at=MagicMock(isoformat=lambda: "2024-01-01T00:00:00"),
            last_accessed=MagicMock(isoformat=lambda: "2024-01-01T12:00:00"),
        )
        mock_get_access_control.return_value = mock_access_control

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
            assert data["messages"][0]["type"] == "human"
            assert data["messages"][0]["content"] == "Hello"
            assert data["messages"][1]["type"] == "ai"
            assert data["messages"][1]["content"] == "Hi there!"
            assert data["messages"][2]["type"] == "tool"
            assert data["messages"][2]["content"] == "API response"
            assert data["messages"][2]["name"] == "test_api"
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
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    def test_list_conversations_scenarios(
        self,
        mock_get_checkpointer,
        mock_get_access_control,
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
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    def test_delete_conversation_scenarios(
        self,
        mock_get_checkpointer,
        mock_get_access_control,
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
