"""
Unit tests for server routes.

Covers all endpoints in routes.py using table-style tests and FastAPI TestClient.
"""

import json
import os
import sys
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from api_assistant.server.routes import create_agent_routes, create_basic_routes


@pytest.fixture
def app_and_agent():
    app = FastAPI()
    mock_agent = AsyncMock()
    create_basic_routes(app)
    create_agent_routes(app, mock_agent)
    return app, mock_agent


@pytest.fixture
def client(app_and_agent):
    app, _ = app_and_agent
    return TestClient(app)


class TestBasicRoutes:
    @pytest.mark.parametrize(
        "path,expected_status,expected_redirect",
        [
            ("/", 200, True),
            ("/healthz", 200, False),
        ],
    )
    def test_basic_routes(self, client, path, expected_status, expected_redirect):
        response = client.get(path, follow_redirects=False)
        if expected_redirect:
            assert response.status_code in (302, 307)
            assert response.headers["location"] == "/docs"
        else:
            assert response.status_code == expected_status
            assert response.json() == {"status": "Healthy"}


class TestAgentInvoke:
    @pytest.mark.parametrize(
        "input_messages,config,expected_status",
        [
            ([{"type": "human", "content": "hi"}], None, 200),
            ([], None, 422),  # Invalid: empty messages
        ],
    )
    def test_agent_invoke(
        self, client, app_and_agent, input_messages, config, expected_status
    ):
        _, mock_agent = app_and_agent
        mock_agent.ainvoke.return_value = {"result": "ok"}
        payload = {"input": {"messages": input_messages}, "config": config}
        with patch(
            "api_assistant.server.routes.setup_runtime_config_with_access_control",
            new=AsyncMock(return_value=({}, "tid")),
        ):
            response = client.post("/nalai/invoke", json=payload)
        if expected_status == 200:
            assert response.status_code == 200
            assert "output" in response.json()
        else:
            assert response.status_code == expected_status


class TestAgentStreamEvents:
    @pytest.mark.parametrize(
        "input_messages,config,expected_status",
        [
            ([{"type": "human", "content": "hi"}], None, 200),
            ([], None, 422),
        ],
    )
    def test_agent_stream_events(
        self, client, app_and_agent, input_messages, config, expected_status
    ):
        _, mock_agent = app_and_agent
        mock_event = {"event": "on_chat_model_stream", "data": {"content": "test"}}

        async def async_gen():
            yield mock_event

        def astream_events(*a, **kw):
            return async_gen()

        mock_agent.astream_events = astream_events
        payload = {"input": {"messages": input_messages}, "config": config}
        with patch(
            "api_assistant.server.routes.setup_runtime_config_with_access_control",
            new=AsyncMock(return_value=({}, str(uuid.uuid4()))),
        ):
            response = client.post("/nalai/stream_events", json=payload)
        if expected_status == 200:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
        else:
            assert response.status_code == expected_status


class TestHumanReview:
    @pytest.mark.parametrize(
        "action,expected_status",
        [
            ("continue", 200),
            ("abort", 200),
            ("update", 200),
            ("feedback", 200),
        ],
    )
    def test_human_review(self, client, app_and_agent, action, expected_status):
        _, mock_agent = app_and_agent
        mock_agent.get_state.return_value = []
        thread_id = str(uuid.uuid4())
        payload = {
            "action": action,
            "thread_id": thread_id,
        }
        if action in ["update", "feedback"]:
            payload["data"] = {"foo": "bar"}

        async def fake_stream_interruptable_events(*a, **kw):
            yield json.dumps({"event": "test", "data": {"foo": "bar"}})

        with patch(
            "api_assistant.server.routes.setup_runtime_config_with_access_control",
            new=AsyncMock(return_value=({}, thread_id)),
        ):
            with patch(
                "api_assistant.server.routes.stream_interruptable_events",
                new=fake_stream_interruptable_events,
            ):
                response = client.post(
                    "/nalai/human-review",
                    content=json.dumps(payload),
                    headers={"content-type": "text/plain"},
                )
        if expected_status == 200:
            if response.status_code != 200:
                print(f"Response body for action={action}: {response.text}")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
        else:
            assert response.status_code == expected_status

    def test_human_review_invalid_action(self, client, app_and_agent):
        """Test that invalid actions raise ValidationError."""
        _, mock_agent = app_and_agent
        mock_agent.get_state.return_value = []
        thread_id = str(uuid.uuid4())
        payload = {
            "action": "invalid",
            "thread_id": thread_id,
        }
        with patch(
            "api_assistant.server.routes.setup_runtime_config_with_access_control",
            new=AsyncMock(return_value=({}, thread_id)),
        ):
            with patch(
                "api_assistant.server.routes.stream_interruptable_events",
                new=AsyncMock(),
            ):
                with pytest.raises(Exception) as exc_info:
                    client.post(
                        "/nalai/human-review",
                        content=json.dumps(payload),
                        headers={"content-type": "text/plain"},
                    )
                # The ValidationError should be raised
                assert (
                    "ValidationError" in str(exc_info.value)
                    or "validation error" in str(exc_info.value).lower()
                )
