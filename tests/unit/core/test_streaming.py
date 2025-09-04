"""
Unit tests for streaming functionality.

Tests cover streaming events, chunks, and utilities.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)


from nalai.core.streaming import (
    Event,
    InterruptChunk,
    MessageChunk,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    StreamingChunk,
    ToolCallChunk,
    ToolCallUpdateChunk,
    ToolChunk,
    UpdateChunk,
    extract_usage_from_streaming_chunks,
)


class TestStreamingEvents:
    """Test suite for streaming events."""

    def test_response_created_event(self):
        """Test ResponseCreatedEvent creation."""
        event = ResponseCreatedEvent(conversation_id="conv_123")

        assert event.event == "response.created"
        assert event.conversation_id == "conv_123"
        assert event.id is not None

    def test_response_completed_event(self):
        """Test ResponseCompletedEvent creation."""
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        event = ResponseCompletedEvent(conversation_id="conv_123", usage=usage)

        assert event.event == "response.completed"
        assert event.conversation_id == "conv_123"
        assert event.usage == usage
        assert event.id is not None

    def test_response_error_event(self):
        """Test ResponseErrorEvent creation."""
        event = ResponseErrorEvent(
            conversation_id="conv_123", error="Something went wrong"
        )

        assert event.event == "response.error"
        assert event.conversation_id == "conv_123"
        assert event.error == "Something went wrong"
        assert event.id is not None


class TestStreamingChunks:
    """Test suite for streaming chunks."""

    def test_message_chunk(self):
        """Test MessageChunk creation."""
        chunk = MessageChunk(
            conversation_id="conv_123",
            task="test_task",
            content="Hello",
            id="chunk_123",
        )

        assert chunk.conversation_id == "conv_123"
        assert chunk.content == "Hello"
        assert chunk.task == "test_task"
        assert chunk.id == "chunk_123"

    def test_tool_call_chunk(self):
        """Test ToolCallChunk creation."""
        chunk = ToolCallChunk(
            conversation_id="conv_123",
            task="test_task",
            tool_call_id="call_123",
            name="search_function",
            args={"query": "test"},
            id="chunk_456",
        )

        assert chunk.conversation_id == "conv_123"
        assert chunk.tool_call_id == "call_123"
        assert chunk.name == "search_function"
        assert chunk.args == {"query": "test"}
        assert chunk.task == "test_task"
        assert chunk.id == "chunk_456"

    def test_tool_call_update_chunk(self):
        """Test ToolCallUpdateChunk creation."""
        chunk = ToolCallUpdateChunk(
            conversation_id="conv_123",
            task="test_task",
            tool_calls=[{"id": "call_123", "status": "completed"}],
        )

        assert chunk.conversation_id == "conv_123"
        assert chunk.task == "test_task"
        assert chunk.tool_calls == [{"id": "call_123", "status": "completed"}]

    def test_interrupt_chunk(self):
        """Test InterruptChunk creation."""
        chunk = InterruptChunk(
            conversation_id="conv_123",
            id="interrupt_123",
            values=[
                {
                    "type": "human_input_required",
                    "message": "Please provide additional information",
                }
            ],
        )

        assert chunk.conversation_id == "conv_123"
        assert chunk.id == "interrupt_123"
        assert chunk.values == [
            {
                "type": "human_input_required",
                "message": "Please provide additional information",
            }
        ]

    def test_tool_chunk(self):
        """Test ToolChunk creation."""
        chunk = ToolChunk(
            conversation_id="conv_123",
            id="tool_chunk_123",
            tool_call_id="call_123",
            tool_name="search_api",
            content="Tool execution result",
            args={"query": "test"},
        )

        assert chunk.conversation_id == "conv_123"
        assert chunk.id == "tool_chunk_123"
        assert chunk.tool_call_id == "call_123"
        assert chunk.tool_name == "search_api"
        assert chunk.content == "Tool execution result"
        assert chunk.args == {"query": "test"}

    def test_update_chunk(self):
        """Test UpdateChunk creation."""
        chunk = UpdateChunk(conversation_id="conv_123", task="test_task", messages=[])

        assert chunk.conversation_id == "conv_123"
        assert chunk.task == "test_task"
        assert chunk.messages == []


class TestStreamingUtilities:
    """Test suite for streaming utilities."""

    def test_extract_usage_from_streaming_chunks(self):
        """Test extract_usage_from_streaming_chunks function."""
        # Create mock chunks with usage data
        chunks = [
            MessageChunk(
                conversation_id="conv_123",
                task="test_task",
                content="Hello",
                id="chunk_1",
            ),
            MessageChunk(
                conversation_id="conv_123",
                task="test_task",
                content="World",
                id="chunk_2",
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            ),
        ]

        usage = extract_usage_from_streaming_chunks(chunks)

        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 5
        assert usage["total_tokens"] == 15

    def test_extract_usage_from_empty_chunks(self):
        """Test extract_usage_from_streaming_chunks with empty chunks."""
        chunks = []
        usage = extract_usage_from_streaming_chunks(chunks)

        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_extract_usage_from_chunks_without_usage(self):
        """Test extract_usage_from_streaming_chunks with chunks without usage data."""
        chunks = [
            MessageChunk(
                conversation_id="conv_123",
                task="test_task",
                content="Hello",
                id="chunk_1",
            ),
            MessageChunk(
                conversation_id="conv_123",
                task="test_task",
                content="World",
                id="chunk_2",
            ),
        ]

        usage = extract_usage_from_streaming_chunks(chunks)

        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0


class TestStreamingIntegration:
    """Test suite for streaming integration."""

    def test_event_union_type(self):
        """Test that Event union type works correctly."""
        # Create different event types
        created_event = ResponseCreatedEvent(conversation_id="conv_123")
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        completed_event = ResponseCompletedEvent(
            conversation_id="conv_123", usage=usage
        )
        error_event = ResponseErrorEvent(
            conversation_id="conv_123", error="Error occurred"
        )

        # All should be valid Event types
        events: list[Event] = [created_event, completed_event, error_event]

        assert len(events) == 3
        assert events[0].event == "response.created"
        assert events[1].event == "response.completed"
        assert events[2].event == "response.error"

    def test_streaming_chunk_union_type(self):
        """Test that StreamingChunk union type works correctly."""
        # Create different chunk types
        message_chunk = MessageChunk(
            conversation_id="conv_123", task="test_task", content="Hello", id="chunk_1"
        )
        tool_chunk = ToolChunk(
            conversation_id="conv_123",
            id="tool_chunk_1",
            tool_call_id="call_1",
            tool_name="search",
            content="Tool result",
            args={},
        )
        interrupt_chunk = InterruptChunk(
            conversation_id="conv_123",
            id="interrupt_1",
            values=[{"type": "human_input_required", "message": "Please respond"}],
        )

        # All should be valid StreamingChunk types
        chunks: list[StreamingChunk] = [message_chunk, tool_chunk, interrupt_chunk]

        assert len(chunks) == 3
        assert chunks[0].conversation_id == "conv_123"
        assert chunks[1].conversation_id == "conv_123"
        assert chunks[2].conversation_id == "conv_123"
