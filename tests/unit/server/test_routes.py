"""
Unit tests for server routes.
"""

import os
import sys
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.server.routes import create_agent_routes, create_basic_routes


@pytest.fixture
def mock_modify_runtime_config():
    """Create a mock runtime config function for testing."""

    async def mock_func(config, req):
        # Convert Pydantic model to dict if needed
        if hasattr(config, "model_dump"):
            config = config.model_dump()
        elif config is None:
            config = {}

        # Ensure configurable section exists
        if "configurable" not in config:
            config["configurable"] = {}

        config["configurable"]["thread_id"] = "test-thread-123"
        return config, "test-thread-123"

    return mock_func


@pytest.fixture
def mock_modify_runtime_config_error():
    """Create a mock runtime config function that raises an error."""

    async def mock_func(config, req):
        raise Exception("Access denied")

    return mock_func


@pytest.fixture
def app_and_agent(mock_modify_runtime_config):
    app = FastAPI()
    mock_agent = AsyncMock()
    create_basic_routes(app)
    create_agent_routes(
        app, mock_agent, modify_runtime_config=mock_modify_runtime_config
    )
    return app, mock_agent


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


class TestAgentInvoke:
    """Test synchronous agent invocation - critical business logic."""

    def test_successful_agent_invoke(self, client, app_and_agent):
        """Critical: Agent should process valid input and return response."""
        _, mock_agent = app_and_agent
        mock_agent.ainvoke.return_value = {"result": "test response"}

        payload = {
            "input": {"messages": [{"type": "human", "content": "Hello"}]},
            "config": {"configurable": {"thread_id": "test-thread"}},
        }

        response = client.post("/nalai/invoke", json=payload)

        assert response.status_code == 200
        assert "output" in response.json()
        assert "X-Thread-ID" in response.headers
        mock_agent.ainvoke.assert_called_once()

    @pytest.mark.parametrize(
        "payload,expected_status",
        [
            ({"input": {"messages": []}, "config": {}}, 422),  # Empty messages
            (
                {
                    "input": {"messages": [{"type": "human", "content": ""}]},
                    "config": {},
                },
                422,
            ),  # Empty content
        ],
    )
    def test_agent_invoke_validation_failures(self, client, payload, expected_status):
        """Critical: Should reject invalid inputs."""
        response = client.post("/nalai/invoke", json=payload)
        assert response.status_code == expected_status

    def test_agent_invoke_with_access_control_error(
        self, mock_modify_runtime_config_error
    ):
        """Critical: Should handle access control failures gracefully."""
        app = FastAPI()
        mock_agent = AsyncMock()
        create_basic_routes(app)
        create_agent_routes(
            app, mock_agent, modify_runtime_config=mock_modify_runtime_config_error
        )
        client = TestClient(app)

        payload = {
            "input": {"messages": [{"type": "human", "content": "Hello"}]},
            "config": {"configurable": {"thread_id": "unauthorized-thread"}},
        }

        # Should raise the exception as expected
        with pytest.raises(Exception, match="Access denied"):
            client.post("/nalai/invoke", json=payload)


class TestAgentStreamEvents:
    """Test streaming agent events - critical for real-time functionality."""

    def test_successful_stream_events(self, client, app_and_agent):
        """Critical: Should stream events with proper SSE format."""
        _, mock_agent = app_and_agent
        mock_event = {"event": "on_chat_model_stream", "data": {"content": "test"}}

        async def async_gen():
            yield mock_event

        mock_agent.astream_events = lambda *a, **kw: async_gen()

        payload = {
            "input": {"messages": [{"type": "human", "content": "Hello"}]},
            "config": {"configurable": {"thread_id": "test-thread"}},
        }

        response = client.post("/nalai/stream_events", json=payload)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "X-Thread-ID" in response.headers

    @pytest.mark.parametrize(
        "payload,expected_status",
        [
            ({"input": {"messages": []}, "config": {}}, 422),  # Empty messages
            (
                {
                    "input": {"messages": [{"type": "human", "content": ""}]},
                    "config": {},
                },
                422,
            ),  # Empty content
        ],
    )
    def test_stream_events_validation_failures(self, client, payload, expected_status):
        """Critical: Should reject invalid inputs for streaming."""
        response = client.post("/nalai/stream_events", json=payload)
        assert response.status_code == expected_status


class TestToolInterrupt:
    """Test tool interruption functionality - critical for user interaction."""

    @pytest.mark.parametrize(
        "response_type,args,expected_status",
        [
            ("accept", None, 200),
            ("edit", {"new_args": "updated value"}, 200),
            ("response", {"feedback": "good"}, 200),
        ],
    )
    def test_tool_interrupt_stream_success_cases(
        self, client, app_and_agent, response_type, args, expected_status
    ):
        """Critical: Should handle different interrupt response types in streaming mode."""
        _, mock_agent = app_and_agent
        mock_event = {"event": "on_chat_model_stream", "data": {"content": "processed"}}

        async def async_gen():
            yield mock_event

        mock_agent.astream_events = lambda *a, **kw: async_gen()

        payload = {
            "thread_id": str(uuid.uuid4()),
            "response_type": response_type,
            "args": args,
        }

        response = client.post("/nalai/tool-interrupt/stream", json=payload)

        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.headers["content-type"].startswith("text/event-stream")

    @pytest.mark.parametrize(
        "response_type,args,expected_status",
        [
            ("accept", None, 200),
            ("edit", {"new_args": "updated value"}, 200),
            ("response", {"feedback": "good"}, 200),
        ],
    )
    def test_tool_interrupt_batch_success_cases(
        self, client, app_and_agent, response_type, args, expected_status
    ):
        """Critical: Should handle different interrupt response types in batch mode."""
        _, mock_agent = app_and_agent
        mock_agent.ainvoke.return_value = {"result": "processed response"}

        payload = {
            "thread_id": str(uuid.uuid4()),
            "response_type": response_type,
            "args": args,
        }

        response = client.post("/nalai/tool-interrupt/batch", json=payload)

        assert response.status_code == expected_status
        if expected_status == 200:
            assert "output" in response.json()

    @pytest.mark.parametrize(
        "thread_id,response_type,expected_status",
        [
            ("invalid-uuid", "accept", 422),  # Invalid thread_id
            (str(uuid.uuid4()), "invalid_type", 422),  # Invalid response_type
        ],
    )
    def test_tool_interrupt_validation_failures(
        self, client, thread_id, response_type, expected_status
    ):
        """Critical: Should reject invalid inputs for tool interrupts."""
        payload = {"thread_id": thread_id, "response_type": response_type, "args": None}
        response = client.post("/nalai/tool-interrupt/stream", json=payload)
        assert response.status_code == expected_status
