"""
Unit tests for event handling utilities.

Tests cover event serialization, formatting, processing, and streaming
with interrupt handling for the API Assistant server.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from langgraph.graph.state import CompiledStateGraph

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.server.event_handlers import (
    format_sse_event_default,
    process_and_format_event,
    serialize_event_default,
    stream_interruptable_events,
)


class TestSerializeEventDefault:
    """Test default event serialization."""

    @pytest.mark.parametrize(
        "event,expected",
        [
            (
                {"key": "value", "nested": {"inner": "data"}},
                {"key": "value", "nested": {"inner": "data"}},
            ),
            ("simple string", "simple string"),
            (
                {"level1": {"level2": {"level3": "deep_value"}}},
                {"level1": {"level2": {"level3": "deep_value"}}},
            ),
        ],
    )
    def test_serialize_event_default(self, event, expected):
        """Test serialization of various event types."""
        result = serialize_event_default(event)
        assert result == expected

    def test_serialize_event_default_with_model_dump_method(self):
        """Test serialization of objects with model_dump method (Pydantic models)."""
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = {"serialized": "pydantic_data"}

        result = serialize_event_default(mock_obj)

        assert result == {"serialized": "pydantic_data"}
        mock_obj.model_dump.assert_called_once()

    def test_serialize_event_default_with_to_dict_method(self):
        """Test serialization of objects with to_dict method."""
        mock_obj = MagicMock()
        # The function checks for model_dump() first, then to_dict()
        # Since we want to test to_dict(), we need to ensure model_dump() doesn't exist
        del mock_obj.model_dump
        mock_obj.to_dict.return_value = {"serialized": "data"}

        result = serialize_event_default(mock_obj)

        assert result == {"serialized": "data"}
        mock_obj.to_dict.assert_called_once()

    def test_serialize_event_default_with_dict_attr(self):
        """Test serialization of objects with __dict__ attribute."""
        mock_obj = MagicMock()
        mock_obj.__dict__ = {"attr1": "value1", "attr2": "value2"}

        result = serialize_event_default(mock_obj)

        assert result == {"attr1": "value1", "attr2": "value2"}

    def test_serialize_event_default_with_exception(self):
        """Test serialization with exception handling."""

        class FailingObj:
            def to_dict(self):
                raise Exception("Serialization failed")

            @property
            def __dict__(self):
                raise Exception("Serialization failed")

            def __str__(self):
                return "FailingObj(str)"

        result = serialize_event_default(FailingObj())
        assert isinstance(result, str)
        assert "FailingObj" in result


class TestFormatSseEventDefault:
    """Test default SSE event formatting."""

    @pytest.mark.parametrize(
        "event_type,data,expected",
        [
            (
                "test_event",
                '{"key": "value"}',
                'event: test_event\ndata: {"key": "value"}\n\n',
            ),
            ("empty_event", "", "event: empty_event\ndata: \n\n"),
            (
                "special_event",
                '{"message": "Hello\\nWorld\\twith\\rspecial chars"}',
                'event: special_event\ndata: {"message": "Hello\\nWorld\\twith\\rspecial chars"}\n\n',
            ),
        ],
    )
    def test_format_sse_event_default(self, event_type, data, expected):
        """Test SSE event formatting with various inputs."""
        result = format_sse_event_default(event_type, data)
        assert result == expected


class TestProcessAndFormatEvent:
    """Test event processing and formatting."""

    @pytest.fixture
    def mock_serialize_event(self):
        """Create a mock serialize event function."""
        return MagicMock(return_value={"serialized": "data"})

    @pytest.fixture
    def mock_format_sse_event(self):
        """Create a mock format SSE event function."""
        return MagicMock(return_value="formatted_sse_event")

    @pytest.mark.parametrize(
        "event,allowed_events,expected_result,should_call_serialize,should_call_format",
        [
            (
                {"event": "on_chat_model_stream", "data": {"content": "test"}},
                ["on_chat_model_stream", "on_tool_end"],
                "formatted_sse_event",
                True,
                True,
            ),
            (
                {"event": "on_chain_start", "data": {"content": "test"}},
                ["on_chat_model_stream", "on_tool_end"],
                None,
                False,
                False,
            ),
            (
                {
                    "event": "on_chain_stream",
                    "data": {"chunk": {"__interrupt__": [{"value": "interrupt_data"}]}},
                },
                ["on_chat_model_stream"],
                "formatted_sse_event",
                True,
                True,
            ),
            (
                {
                    "event": "on_chain_stream",
                    "data": {"chunk": {"content": "normal_content"}},
                },
                ["on_chat_model_stream"],
                None,
                False,
                False,
            ),
            (
                {"data": {"content": "test"}},
                ["on_chat_model_stream"],
                None,
                False,
                False,
            ),
            (
                {"event": "on_chat_model_stream", "data": {"content": "test"}},
                [],
                None,
                False,
                False,
            ),
        ],
    )
    def test_process_and_format_event(
        self,
        mock_serialize_event,
        mock_format_sse_event,
        event,
        allowed_events,
        expected_result,
        should_call_serialize,
        should_call_format,
    ):
        """Test event processing with various scenarios."""
        result = process_and_format_event(
            event, allowed_events, mock_serialize_event, mock_format_sse_event
        )

        assert result == expected_result

        if should_call_serialize:
            mock_serialize_event.assert_called_once_with(event)
        else:
            mock_serialize_event.assert_not_called()

        if should_call_format:
            mock_format_sse_event.assert_called_once_with(
                "data", '{"serialized": "data"}'
            )
        else:
            mock_format_sse_event.assert_not_called()


class TestStreamInterruptableEvents:
    """Test streaming of interruptable events."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock compiled agent."""
        agent = MagicMock(spec=CompiledStateGraph)
        return agent

    @pytest.fixture
    def mock_serialize_event(self):
        """Create a mock serialize event function."""
        return MagicMock(return_value={"serialized": "data"})

    @pytest.fixture
    def mock_format_sse_event(self):
        """Create a mock format SSE event function."""
        return MagicMock(return_value="formatted_sse_event")

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {"configurable": {"thread_id": "test-thread"}}

    @pytest.fixture
    def resume_input(self):
        """Create resume input data."""
        return {"action": "continue"}

    @pytest.mark.parametrize(
        "agent_events,has_interrupts,expected_event_count,should_raise_exception",
        [
            (
                [
                    {"event": "on_chat_model_stream", "data": {"content": "test1"}},
                    {"event": "on_tool_end", "data": {"result": "test2"}},
                ],
                True,
                3,  # 2 events + 1 interrupt
                False,
            ),
            (
                [{"event": "on_chain_start", "data": {"content": "test"}}],
                False,
                0,  # No allowed events, so expect 0
                False,
            ),
            (
                [{"event": "on_chat_model_stream", "data": {"content": "test"}}],
                False,
                1,
                False,
            ),
            (
                [],
                False,
                1,  # Error event
                True,
            ),
            (
                [
                    "not_a_dict_event",
                    {"event": "on_chat_model_stream", "data": {"content": "test"}},
                ],
                False,
                1,  # Only the dict event is processed
                False,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_stream_interruptable_events(
        self,
        mock_agent,
        mock_serialize_event,
        mock_format_sse_event,
        mock_config,
        resume_input,
        agent_events,
        has_interrupts,
        expected_event_count,
        should_raise_exception,
    ):
        """Test event streaming with various scenarios."""
        # Mock agent events
        mock_agent.astream_events.return_value.__aiter__.return_value = agent_events

        # Mock agent state
        mock_snapshot = MagicMock()
        if should_raise_exception:
            mock_agent.astream_events.side_effect = Exception("Streaming failed")
            mock_snapshot.__len__.return_value = 0
        else:
            mock_snapshot.__len__.return_value = 1 if has_interrupts else 0
            if has_interrupts:
                mock_snapshot.__getitem__.return_value.__len__.return_value = 1
                mock_snapshot.__getitem__.return_value.__getitem__.return_value.interrupts = [
                    MagicMock()
                ]
            else:
                mock_snapshot.__getitem__.return_value.__len__.return_value = 0

        mock_agent.get_state.return_value = mock_snapshot

        events = []
        # Use the real formatter for error event test
        if should_raise_exception:
            from nalai.server.event_handlers import format_sse_event_default

            async for event in stream_interruptable_events(
                mock_agent,
                resume_input,
                mock_config,
                serialize_event=mock_serialize_event,
                format_sse_event=format_sse_event_default,
            ):
                events.append(event)
        else:
            async for event in stream_interruptable_events(
                mock_agent,
                resume_input,
                mock_config,
                serialize_event=mock_serialize_event,
                format_sse_event=mock_format_sse_event,
            ):
                events.append(event)

        assert len(events) == expected_event_count

        if should_raise_exception and events:
            # The real formatter should produce an error event type
            assert events[0].startswith("event: error")
        elif not should_raise_exception:
            assert all(event == "formatted_sse_event" for event in events)

        if not should_raise_exception:
            mock_agent.astream_events.assert_called_once()

    @pytest.mark.parametrize(
        "allowed_events",
        [
            ["on_chain_start"],
            ["on_chat_model_stream", "on_tool_end"],
            [],
        ],
    )
    @pytest.mark.asyncio
    async def test_stream_interruptable_events_with_custom_allowed_events(
        self,
        mock_agent,
        mock_serialize_event,
        mock_format_sse_event,
        mock_config,
        resume_input,
        allowed_events,
    ):
        """Test streaming with custom allowed events."""
        # Mock agent events
        mock_events = [{"event": "on_chain_start", "data": {"content": "test"}}]
        mock_agent.astream_events.return_value.__aiter__.return_value = mock_events

        # Mock agent state (no interrupts)
        mock_snapshot = MagicMock()
        mock_snapshot.__len__.return_value = 0
        mock_agent.get_state.return_value = mock_snapshot

        events = []
        async for event in stream_interruptable_events(
            mock_agent,
            resume_input,
            mock_config,
            serialize_event=mock_serialize_event,
            format_sse_event=mock_format_sse_event,
            allowed_events=allowed_events,
        ):
            events.append(event)

        expected_count = 1 if "on_chain_start" in allowed_events else 0
        assert len(events) == expected_count
        mock_agent.astream_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_interruptable_events_interrupt_access_error(
        self,
        mock_agent,
        mock_serialize_event,
        mock_format_sse_event,
        mock_config,
        resume_input,
    ):
        """Test streaming with interrupt access error."""
        # Mock agent events
        mock_events = [{"event": "on_chat_model_stream", "data": {"content": "test"}}]
        mock_agent.astream_events.return_value.__aiter__.return_value = mock_events

        # Mock agent state with interrupt access error
        mock_snapshot = MagicMock()
        mock_snapshot.__len__.return_value = 1
        mock_snapshot.__getitem__.return_value.__len__.return_value = 1
        mock_snapshot.__getitem__.return_value.__getitem__.side_effect = IndexError(
            "No interrupts"
        )
        mock_agent.get_state.return_value = mock_snapshot

        events = []
        async for event in stream_interruptable_events(
            mock_agent,
            resume_input,
            mock_config,
            serialize_event=mock_serialize_event,
            format_sse_event=mock_format_sse_event,
        ):
            events.append(event)

        assert len(events) == 1  # Only the streamed event, no interrupt
        mock_agent.astream_events.assert_called_once()
