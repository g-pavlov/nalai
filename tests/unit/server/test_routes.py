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

from nalai.server.routes import create_basic_routes, create_conversation_routes


@pytest.fixture
def mock_modify_runtime_config():
    """Create a mock runtime config function for testing."""

    def mock_func(config, req):
        # Convert Pydantic model to dict if needed
        if hasattr(config, "model_dump"):
            config = config.model_dump()
        elif config is None:
            config = {}

        # Ensure configurable section exists
        if "configurable" not in config:
            config["configurable"] = {}

        # Use the thread_id from the config if it exists, otherwise use a test one
        if "configurable" in config and "thread_id" in config["configurable"]:
            # Keep the existing thread_id from the request
            pass
        else:
            config["configurable"]["thread_id"] = "test-thread-123"
        return config

    return mock_func


@pytest.fixture
def mock_modify_runtime_config_error():
    """Create a mock runtime config function that raises an error."""

    def mock_func(config, req):
        raise Exception("Access denied")

    return mock_func


@pytest.fixture
def app_and_agent(mock_modify_runtime_config):
    app = FastAPI()
    mock_agent = AsyncMock()
    create_basic_routes(app)
    create_conversation_routes(
        app, mock_agent, modify_runtime_config=mock_modify_runtime_config
    )
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

    @patch("nalai.services.thread_access_control.get_user_context")
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

        mock_agent.ainvoke.return_value = {"output": "test response"}

        payload = {
            "messages": [{"type": "human", "content": "Hello"}],
        }

        response = client.post("/api/v1/conversations", json=payload)

        assert response.status_code == 200
        assert "output" in response.json()
        assert "X-Conversation-ID" in response.headers
        mock_agent.ainvoke.assert_called_once()

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
    def test_conversation_invoke_validation_failures(
        self, client, payload, expected_status
    ):
        """Critical: Should reject invalid inputs."""
        response = client.post("/api/v1/conversations", json=payload)
        assert response.status_code == expected_status

    def test_conversation_invoke_with_access_control_error(
        self, mock_modify_runtime_config_error
    ):
        """Critical: Should handle access control failures gracefully."""
        app = FastAPI()
        mock_agent = AsyncMock()
        create_basic_routes(app)
        create_conversation_routes(
            app, mock_agent, modify_runtime_config=mock_modify_runtime_config_error
        )
        client = TestClient(app)

        payload = {
            "messages": [{"type": "human", "content": "Hello"}],
        }

        # Check the actual response
        response = client.post("/api/v1/conversations", json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")

        # Should return 401 Unauthorized
        assert response.status_code == 401


class TestConversationStreamEvents:
    """Test streaming conversation events - critical for real-time functionality."""

    @patch("nalai.services.thread_access_control.get_user_context")
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

        mock_event = {"event": "on_chat_model_stream", "data": {"content": "test"}}

        async def async_gen():
            yield mock_event

        mock_agent.astream_events = lambda *a, **kw: async_gen()

        payload = {
            "messages": [{"type": "human", "content": "Hello"}],
        }

        response = client.post(
            "/api/v1/conversations",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "X-Conversation-ID" in response.headers

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
    def test_resume_decision_stream_success_cases(
        self, mock_get_user_context, client, app_and_agent
    ):
        """Critical: Should handle resume decisions correctly."""
        _, mock_agent = app_and_agent

        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        conversation_id = str(uuid.uuid4())
        print(f"Generated thread_id: user:test-user:{conversation_id}")

        mock_event = {"event": "on_chat_model_stream", "data": {"content": "test"}}

        async def async_gen():
            yield mock_event

        mock_agent.astream_events = lambda *a, **kw: async_gen()

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
    def test_resume_decision_batch_success_cases(
        self, decision, args, expected_status, client, app_and_agent
    ):
        """Critical: Should handle resume decisions in batch mode."""
        _, mock_agent = app_and_agent
        mock_agent.ainvoke.return_value = {"output": "test response"}

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
            ("invalid-uuid", "accept", 400),  # Invalid UUID - should be 400 Bad Request
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

    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    def test_load_conversation_success(
        self,
        mock_get_checkpointer,
        mock_get_access_control,
        mock_get_user_context,
        client,
        app_and_agent,
    ):
        """Should load conversation successfully."""
        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        # Mock access control
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

        # Mock checkpointing service
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = {
            "messages": [
                ("human", "Hello"),
                ("ai", "Hi there!"),
                (
                    "tool",
                    {
                        "content": "API response",
                        "name": "test_api",
                        "tool_call_id": "call_123",
                    },
                ),
            ],
            "completed": False,
        }
        mock_get_checkpointer.return_value = mock_checkpointer

        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/api/v1/conversations/{conversation_id}")

        assert response.status_code == 200
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
        assert data["metadata"]["title"] == "Test Conversation"

    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    def test_load_conversation_access_denied(
        self, mock_get_access_control, mock_get_user_context, client, app_and_agent
    ):
        """Should deny access to conversation user doesn't own."""
        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        # Mock access control - deny access
        mock_access_control = AsyncMock()
        mock_access_control.validate_thread_access.return_value = False
        mock_get_access_control.return_value = mock_access_control

        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/api/v1/conversations/{conversation_id}")

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @patch("nalai.server.runtime_config.get_user_context")
    @patch("nalai.services.thread_access_control.get_thread_access_control")
    @patch("nalai.services.checkpointing_service.get_checkpointer")
    def test_load_conversation_not_found(
        self,
        mock_get_checkpointer,
        mock_get_access_control,
        mock_get_user_context,
        client,
        app_and_agent,
    ):
        """Should return 404 when conversation doesn't exist."""
        # Mock user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "test-user"
        mock_get_user_context.return_value = mock_user_context

        # Mock access control
        mock_access_control = AsyncMock()
        mock_access_control.validate_thread_access.return_value = True
        mock_access_control.create_user_scoped_thread_id.return_value = (
            "user:test-user:550e8400-e29b-41d4-a716-446655440000"
        )
        mock_get_access_control.return_value = mock_access_control

        # Mock checkpointing service - return None (not found)
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget.return_value = None
        mock_get_checkpointer.return_value = mock_checkpointer

        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/api/v1/conversations/{conversation_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_load_conversation_invalid_id(self, client, app_and_agent):
        """Should return 400 for invalid conversation ID format."""
        conversation_id = "invalid-id"
        response = client.get(f"/api/v1/conversations/{conversation_id}")

        assert response.status_code == 400
