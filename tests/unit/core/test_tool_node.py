"""
Unit tests for the custom tool node with chunk accumulation.
"""

import json
from unittest.mock import Mock

import pytest

from api_assistant.core.tool_node import (
    ChunkAccumulatingToolNode,
    create_chunk_accumulating_tool_node,
)
from api_assistant.server.streaming_processor import (
    StreamingEventProcessor,
    create_streaming_event_processor,
)


class TestChunkAccumulatingToolNode:
    """Test the custom tool node with chunk accumulation."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock tool
        self.mock_tool = Mock()
        self.mock_tool.name = "test_tool"
        self.mock_tool.invoke.return_value = "Tool executed successfully"

        # Create the tool node
        self.tool_node = ChunkAccumulatingToolNode([self.mock_tool])

    def test_initialization(self):
        """Test tool node initialization."""
        assert "test_tool" in self.tool_node.tools
        assert self.tool_node.tool_call_buffers == {}
        assert self.tool_node.completed_tool_calls == {}

    def test_accumulate_chunk(self):
        """Test accumulating tool call chunks."""
        tool_call_id = "call_123"

        # Accumulate first chunk
        self.tool_node.accumulate_chunk(
            {"id": tool_call_id, "args": '{"param1": "value1"'}
        )

        assert tool_call_id in self.tool_node.tool_call_buffers
        assert self.tool_node.tool_call_buffers[tool_call_id] == '{"param1": "value1"'

        # Accumulate second chunk
        self.tool_node.accumulate_chunk(
            {"id": tool_call_id, "args": ', "param2": "value2"}'}
        )

        assert (
            self.tool_node.tool_call_buffers[tool_call_id]
            == '{"param1": "value1", "param2": "value2"}'
        )

    def test_execute_complete_tool_call(self):
        """Test executing a tool call with complete JSON."""
        tool_call_id = "call_123"
        complete_args = {"param1": "value1", "param2": "value2"}

        # Accumulate complete JSON
        self.tool_node.accumulate_chunk(
            {"id": tool_call_id, "args": json.dumps(complete_args)}
        )

        # Execute the tool
        result = self.tool_node._execute_tool("test_tool", complete_args, tool_call_id)

        assert result.content == "Tool executed successfully"
        assert result.name == "test_tool"
        assert result.tool_call_id == tool_call_id

        # Verify tool was called with correct arguments
        self.mock_tool.invoke.assert_called_once_with(complete_args)

    def test_handle_incomplete_json(self):
        """Test handling incomplete JSON chunks."""
        tool_call_id = "call_123"

        # Accumulate incomplete JSON
        self.tool_node.accumulate_chunk(
            {"id": tool_call_id, "args": '{"param1": "value1"'}
        )

        # Try to parse - should still be incomplete
        accumulated_args = self.tool_node.tool_call_buffers[tool_call_id]
        with pytest.raises(json.JSONDecodeError):
            json.loads(accumulated_args)

        # Add more to complete it
        self.tool_node.accumulate_chunk({"id": tool_call_id, "args": "}"})

        # Now should be complete
        accumulated_args = self.tool_node.tool_call_buffers[tool_call_id]
        parsed_args = json.loads(accumulated_args)
        assert parsed_args == {"param1": "value1"}

    def test_clear_buffers(self):
        """Test clearing accumulated buffers."""
        tool_call_id = "call_123"

        # Accumulate some chunks
        self.tool_node.accumulate_chunk(
            {"id": tool_call_id, "args": '{"test": "data"}'}
        )

        assert tool_call_id in self.tool_node.tool_call_buffers

        # Clear buffers
        self.tool_node.clear_buffers()

        assert self.tool_node.tool_call_buffers == {}
        assert self.tool_node.completed_tool_calls == {}

    def test_get_buffered_tool_calls(self):
        """Test getting buffered tool calls for debugging."""
        tool_call_id = "call_123"

        # Accumulate some chunks
        self.tool_node.accumulate_chunk(
            {"id": tool_call_id, "args": '{"test": "data"}'}
        )

        buffered = self.tool_node.get_buffered_tool_calls()
        assert buffered == {tool_call_id: '{"test": "data"}'}


class TestStreamingEventProcessor:
    """Test the streaming event processor."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock tool node
        self.mock_tool_node = Mock()
        self.mock_tool_node.accumulate_chunk = Mock()

        # Create the streaming processor
        self.processor = StreamingEventProcessor(self.mock_tool_node)

    def test_process_chat_model_stream_with_tool_calls(self):
        """Test processing chat model stream events with tool calls."""
        event = {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": {
                    "tool_call_chunks": [
                        {"id": "call_123", "args": '{"param1": "value1"'}
                    ],
                    "invalid_tool_calls": [
                        {"id": "call_123", "error": "Invalid tool call"}
                    ],
                }
            },
        }

        # Process the event
        result = self.processor.process_event(event)

        # Should suppress invalid tool calls while accumulating
        assert result is not None
        assert result["data"]["chunk"]["invalid_tool_calls"] == []

        # Check that chunk was accumulated
        assert "call_123" in self.processor.tool_call_buffers
        assert self.processor.tool_call_buffers["call_123"] == '{"param1": "value1"'

    def test_process_complete_tool_call(self):
        """Test processing a complete tool call."""
        # First, accumulate an incomplete chunk
        self.processor._accumulate_tool_call_chunk(
            {"id": "call_123", "args": '{"param1": "value1"'}
        )

        # Then add the completing chunk
        self.processor._accumulate_tool_call_chunk({"id": "call_123", "args": "}"})

        # Check for complete tool calls
        complete_calls = self.processor._check_for_complete_tool_calls()

        assert len(complete_calls) == 1
        assert complete_calls[0]["id"] == "call_123"
        assert complete_calls[0]["args"] == {"param1": "value1"}

    def test_process_other_event_types(self):
        """Test processing other event types (should pass through unchanged)."""
        event = {"event": "on_tool_end", "data": {"tool_name": "test_tool"}}

        result = self.processor.process_event(event)

        # Should pass through unchanged
        assert result == event

    def test_clear_buffers(self):
        """Test clearing processor buffers."""
        # Accumulate some chunks
        self.processor._accumulate_tool_call_chunk(
            {"id": "call_123", "args": '{"test": "data"}'}
        )

        assert "call_123" in self.processor.tool_call_buffers

        # Clear buffers
        self.processor.clear_buffers()

        assert self.processor.tool_call_buffers == {}
        assert self.processor.processed_events == []


def test_create_chunk_accumulating_tool_node():
    """Test factory function for creating tool node."""
    mock_tool = Mock()
    mock_tool.name = "test_tool"

    tool_node = create_chunk_accumulating_tool_node([mock_tool])

    assert isinstance(tool_node, ChunkAccumulatingToolNode)
    assert "test_tool" in tool_node.tools


def test_create_streaming_event_processor():
    """Test factory function for creating streaming processor."""
    mock_tool_node = Mock()

    processor = create_streaming_event_processor(mock_tool_node)

    assert isinstance(processor, StreamingEventProcessor)
    assert processor.tool_node == mock_tool_node
