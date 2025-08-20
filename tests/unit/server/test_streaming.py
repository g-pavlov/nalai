"""
Unit tests for event handling utilities.

Tests cover event serialization, formatting, processing, and streaming
with interrupt handling for the API Assistant server.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.graph.state import CompiledStateGraph

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.server.streaming import (
    format_sse_event_default,
    serialize_event,
    serialize_to_sse,
    stream_events,
)


class TestFormatSSEEventDefault:
    """Test SSE event formatting - critical for real-time communication."""

    @pytest.mark.parametrize(
        "event_type,data,expected",
        [
            ("message", "Hello world", "event: message\ndata: Hello world\n\n"),
            ("error", '{"error": "test"}', 'event: error\ndata: {"error": "test"}\n\n'),
            ("", "empty type", "event: \ndata: empty type\n\n"),
        ],
    )
    def test_format_sse_event_default(self, event_type, data, expected):
        """Critical: Should format SSE events correctly."""
        result = format_sse_event_default(event_type, data)
        assert result == expected


class TestSerializeToSSE:
    """Test SSE serialization function."""

    def test_serialize_to_sse_basic(self):
        """Should serialize basic objects to SSE format."""
        event = {"message": "Hello", "type": "ai"}

        def mock_serialize_func(obj):
            return obj

        result = serialize_to_sse(event, mock_serialize_func)
        expected = 'data: {"message": "Hello", "type": "ai"}\n\n'
        assert result == expected

    def test_serialize_to_sse_with_serialize_event_default(self):
        """Should work with the default serialize function."""
        event = {"content": "Test message", "type": "human"}

        result = serialize_to_sse(event, serialize_event)
        expected = 'data: {"content": "Test message", "type": "human"}\n\n'
        assert result == expected

    def test_serialize_to_sse_complex_object(self):
        """Should handle complex objects through serialization function."""

        class TestObject:
            def __init__(self, value):
                self.value = value

        event = TestObject("test_value")

        def custom_serialize(obj):
            if hasattr(obj, "value"):
                return {"serialized_value": obj.value}
            return obj

        result = serialize_to_sse(event, custom_serialize)
        expected = 'data: {"serialized_value": "test_value"}\n\n'
        assert result == expected


class TestSerializeEventDefault:
    """Test event serialization with data filtering - critical for security and performance."""

    @pytest.mark.parametrize(
        "event,expected_keys,expected_absent_keys",
        [
            (
                {"key": "value", "api_specs": "sensitive"},
                ["key"],
                ["api_specs"],
            ),
            (
                {"data": {"api_summaries": "sensitive", "content": "safe"}},
                ["data"],
                ["api_summaries"],
            ),
            (
                {"nested": {"level1": {"api_specs": "sensitive", "data": "safe"}}},
                ["nested"],
                ["api_specs"],
            ),
        ],
    )
    def test_serialize_event_filters_sensitive_data(
        self, event, expected_keys, expected_absent_keys
    ):
        """Critical: Should filter out sensitive data (api_specs, api_summaries)."""
        result = serialize_event(event)

        # Check that expected keys are present
        for key in expected_keys:
            assert key in str(result)

        # Check that sensitive keys are filtered out
        for key in expected_absent_keys:
            assert key not in str(result)

    @pytest.mark.parametrize(
        "event,expected_type",
        [
            ({"key": "value"}, dict),
            ("simple string", str),
            ([1, 2, 3], list),
            ((1, 2, 3), list),  # Tuples become lists
        ],
    )
    def test_serialize_event_basic_types(self, event, expected_type):
        """Critical: Should handle basic Python types correctly."""
        result = serialize_event(event)
        assert isinstance(result, expected_type)

    def test_serialize_event_pydantic_model(self):
        """Critical: Should handle Pydantic models correctly."""
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = {"serialized": "pydantic_data"}

        result = serialize_event(mock_obj)

        assert result == {"serialized": "pydantic_data"}
        mock_obj.model_dump.assert_called_once()

    def test_serialize_event_langchain_message(self):
        """Critical: Should handle LangChain message objects specially."""

        # Create a proper mock that doesn't cause infinite recursion
        class MockLangChainMessage:
            def __init__(self):
                self.content = "Hello"
                self.id = "msg_123"
                self.tool_calls = None
                self.tool_call_chunks = None
                self.invalid_tool_calls = None

            @property
            def __class__(self):
                class MockClass:
                    __name__ = "HumanMessage"

                return MockClass()

        mock_message = MockLangChainMessage()

        result = serialize_event(mock_message)

        expected = {
            "type": "HumanMessage",
            "content": "Hello",
            "id": "msg_123",
            "tool_calls": None,
            "tool_call_chunks": None,
            "invalid_tool_calls": None,
        }
        assert result == expected

    def test_serialize_event_with_exception_handling(self):
        """Critical: Should handle serialization errors gracefully."""

        class FailingObj:
            def __str__(self):
                raise Exception("Serialization failed")

            def __repr__(self):
                return "<FailingObj>"

        result = serialize_event(FailingObj())
        # The function catches exceptions and returns an empty dict as fallback
        # This is the actual behavior when all serialization attempts fail
        assert isinstance(result, dict)
        assert result == {}


@pytest.mark.asyncio
class TestStreamEvents:
    """Test async event streaming - critical for real-time functionality."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = AsyncMock(spec=CompiledStateGraph)
        return agent

    @pytest.mark.parametrize(
        "workflow_type,agent_behavior,expected_events,expected_content_check",
        [
            ("fresh", "success", 3, "data: "),
            ("resume", "success", 1, "data: "),
            ("fresh", "error", 1, "error"),
            ("fresh", "custom_serializer", 1, "custom"),
        ],
    )
    async def test_stream_events_scenarios(
        self,
        mock_agent,
        workflow_type,
        agent_behavior,
        expected_events,
        expected_content_check,
    ):
        """Should handle all streaming scenarios correctly."""
        from nalai.server.schemas import ResumeDecisionRequest

        if agent_behavior == "success":
            # Mock successful streaming
            mock_chunks = (
                [
                    {"event": "start", "data": "beginning"},
                    {"event": "progress", "data": "middle"},
                    {"event": "end", "data": "complete"},
                ]
                if workflow_type == "fresh"
                else [{"event": "resume", "data": "continued"}]
            )

            async def mock_astream(*args, **kwargs):
                for chunk in mock_chunks:
                    yield chunk

            mock_agent.astream = mock_astream

        elif agent_behavior == "error":
            # Mock streaming error
            async def mock_astream(*args, **kwargs):
                raise Exception("Streaming failed")

            mock_agent.astream = mock_astream

        elif agent_behavior == "custom_serializer":
            # Mock with custom serializer
            mock_chunks = [{"event": "test", "data": "value"}]

            async def mock_astream(*args, **kwargs):
                for chunk in mock_chunks:
                    yield chunk

            mock_agent.astream = mock_astream

        config = {"thread_id": "test-thread"}
        agent_input = (
            {"messages": [("human", "Hello")]} if workflow_type == "fresh" else None
        )
        resume_input = (
            ResumeDecisionRequest(input={"decision": "accept"})
            if workflow_type == "resume"
            else None
        )

        # Custom serializer for custom_serializer test
        custom_serializer = None
        if agent_behavior == "custom_serializer":

            def custom_serializer(event):
                return {"custom": "serialized", "original": event}

        events = []
        async for event in stream_events(
            mock_agent,
            config,
            agent_input,
            resume_input,
            serialize_func=custom_serializer,
        ):
            events.append(event)

        assert len(events) == expected_events
        for event in events:
            assert event.startswith("data: ") or expected_content_check in event
            if event.startswith("data: "):
                assert event.endswith("\n\n")
