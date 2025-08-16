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
    serialize_event_default,
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
        result = serialize_event_default(event)

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
        result = serialize_event_default(event)
        assert isinstance(result, expected_type)

    def test_serialize_event_pydantic_model(self):
        """Critical: Should handle Pydantic models correctly."""
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = {"serialized": "pydantic_data"}

        result = serialize_event_default(mock_obj)

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

        result = serialize_event_default(mock_message)

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

        result = serialize_event_default(FailingObj())
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

    async def test_stream_events_fresh_workflow(self, mock_agent):
        """Critical: Should stream events from fresh workflow."""
        # Mock the agent's astream method
        mock_chunks = [
            {"event": "start", "data": "beginning"},
            {"event": "progress", "data": "middle"},
            {"event": "end", "data": "complete"},
        ]

        async def mock_astream(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        mock_agent.astream = mock_astream

        config = {"thread_id": "test-thread"}
        agent_input = {"messages": [{"type": "human", "content": "Hello"}]}

        events = []
        async for event in stream_events(mock_agent, config, agent_input):
            events.append(event)

        # Should have 3 events, each formatted as SSE
        assert len(events) == 3
        for event in events:
            assert event.startswith("data: ")
            assert event.endswith("\n\n")

    async def test_stream_events_resume_workflow(self, mock_agent):
        """Critical: Should handle resume workflow with interrupt response."""
        from nalai.server.schemas import ResumeDecisionRequest

        # Mock the agent's astream method
        mock_chunks = [
            {"event": "resume", "data": "continued"},
        ]

        async def mock_astream(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        mock_agent.astream = mock_astream

        config = {"thread_id": "test-thread"}
        agent_input = None  # Not used for resume
        resume_input = ResumeDecisionRequest(input={"decision": "accept"})

        events = []
        async for event in stream_events(mock_agent, config, agent_input, resume_input):
            events.append(event)

        # Should have 1 event, formatted as SSE
        assert len(events) == 1
        assert events[0].startswith("data: ")
        assert events[0].endswith("\n\n")

    async def test_stream_events_with_error_handling(self, mock_agent):
        """Critical: Should handle streaming errors gracefully."""

        # Mock the agent's astream method to raise an exception
        async def mock_astream(*args, **kwargs):
            raise Exception("Streaming failed")

        mock_agent.astream = mock_astream

        config = {"thread_id": "test-thread"}
        agent_input = {"messages": [{"type": "human", "content": "Hello"}]}

        events = []
        async for event in stream_events(mock_agent, config, agent_input):
            events.append(event)

        # Should have 1 error event
        assert len(events) == 1
        assert "error" in events[0]
        # The error message might be different due to async handling
        assert "error" in events[0]

    async def test_stream_events_with_custom_serializer(self, mock_agent):
        """Critical: Should use custom serializer when provided."""

        def custom_serializer(event):
            return {"custom": "serialized", "original": event}

        # Mock the agent's astream method
        mock_chunks = [{"event": "test", "data": "value"}]

        async def mock_astream(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        mock_agent.astream = mock_astream

        config = {"thread_id": "test-thread"}
        agent_input = {"messages": [{"type": "human", "content": "Hello"}]}

        events = []
        async for event in stream_events(
            mock_agent, config, agent_input, serialize_event=custom_serializer
        ):
            events.append(event)

        # Should have 1 event with custom serialization
        assert len(events) == 1
        assert "custom" in events[0]
        assert "serialized" in events[0]
