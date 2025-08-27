"""
Tests for SSE serializer event models and factory functions.
"""

import json
from unittest.mock import Mock

from nalai.core.agent import (
    InterruptChunk,
    MessageChunk,
    ToolCallChunk,
    ToolChunk,
    UpdateChunk,
)
from nalai.server.sse_serializer import (
    BaseSSEEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    ResponseInterruptEvent,
    ResponseOutputTextCompleteEvent,
    ResponseOutputTextDeltaEvent,
    ResponseResumedEvent,
    ResponseToolCallsCompleteEvent,
    ResponseToolCallsDeltaEvent,
    ResponseToolEvent,
    ResponseUpdateEvent,
    StreamingContext,
    create_streaming_event_from_chunk,
)


class TestSSEEventModels:
    """Test SSE event model validation and structure."""

    def test_base_sse_event_creation(self):
        """Test base SSE event creation with required fields."""
        event = BaseSSEEvent(event="test.event", conversation="conv-123")

        assert event.event == "test.event"
        assert event.conversation == "conv-123"
        assert event.id is not None  # Should be auto-generated

    def test_response_created_event(self):
        """Test response.created event model."""
        event = ResponseCreatedEvent(conversation="conv-123")

        assert event.event == "response.created"
        assert event.conversation == "conv-123"
        assert event.id is not None

    def test_output_text_delta_event(self):
        """Test response.output_text.delta event model."""
        event = ResponseOutputTextDeltaEvent(
            conversation="conv-123", content="Hello, world!"
        )

        assert event.event == "response.output_text.delta"
        assert event.conversation == "conv-123"
        assert event.content == "Hello, world!"

    def test_output_text_complete_event(self):
        """Test response.output_text.complete event model."""
        event = ResponseOutputTextCompleteEvent(
            conversation="conv-123", content="Complete response content"
        )

        assert event.event == "response.output_text.complete"
        assert event.conversation == "conv-123"
        assert event.content == "Complete response content"

    def test_tool_calls_delta_event(self):
        """Test response.tool_calls.delta event model."""
        tool_calls = [{"id": "call_1", "name": "test_tool", "args": {"param": "value"}}]
        event = ResponseToolCallsDeltaEvent(
            conversation="conv-123", tool_calls=tool_calls
        )

        assert event.event == "response.tool_calls.delta"
        assert event.conversation == "conv-123"
        assert event.tool_calls == tool_calls

    def test_tool_calls_complete_event(self):
        """Test response.tool_calls.complete event model."""
        tool_calls = [{"id": "call_1", "name": "test_tool", "args": {"param": "value"}}]
        event = ResponseToolCallsCompleteEvent(
            conversation="conv-123", tool_calls=tool_calls
        )

        assert event.event == "response.tool_calls.complete"
        assert event.conversation == "conv-123"
        assert event.tool_calls == tool_calls

    def test_interrupt_event(self):
        """Test response.interrupt event model."""
        event = ResponseInterruptEvent(
            conversation="conv-123",
            interrupt_id="int-456",
            action="test_action",
            args={"param": "value"},
            config={"timeout": 30},
            description="Test interrupt",
        )

        assert event.event == "response.interrupt"
        assert event.conversation == "conv-123"
        assert event.interrupt_id == "int-456"
        assert event.action == "test_action"
        assert event.args == {"param": "value"}
        assert event.config == {"timeout": 30}
        assert event.description == "Test interrupt"

    def test_resumed_event(self):
        """Test response.resumed event model."""
        event = ResponseResumedEvent(conversation="conv-123")

        assert event.event == "response.resumed"
        assert event.conversation == "conv-123"

    def test_completed_event(self):
        """Test response.completed event model."""
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        event = ResponseCompletedEvent(conversation="conv-123", usage=usage)

        assert event.event == "response.completed"
        assert event.conversation == "conv-123"
        assert event.usage == usage

    def test_error_event(self):
        """Test response.error event model."""
        event = ResponseErrorEvent(
            conversation="conv-123",
            error="Something went wrong",
            detail="Additional error details",
        )

        assert event.event == "response.error"
        assert event.conversation == "conv-123"
        assert event.error == "Something went wrong"
        assert event.detail == "Additional error details"

    def test_tool_event(self):
        """Test response.tool event model."""
        event = ResponseToolEvent(
            conversation="conv-123",
            tool_call_id="call-456",
            tool_name="test_tool",
            status="success",
            content="Tool execution result",
        )

        assert event.event == "response.tool"
        assert event.conversation == "conv-123"
        assert event.tool_call_id == "call-456"
        assert event.tool_name == "test_tool"
        assert event.status == "success"
        assert event.content == "Tool execution result"

    def test_update_event(self):
        """Test response.update event model."""
        messages = [{"content": "Test message", "type": "ai"}]
        event = ResponseUpdateEvent(
            conversation="conv-123",
            task="test_task",
            messages=messages,
        )

        assert event.event == "response.update"
        assert event.conversation == "conv-123"
        assert event.task == "test_task"
        assert event.messages == messages


class TestEventFactoryFunctions:
    """Test event factory functions that create SSE-formatted strings."""

    def test_create_response_created_event(self):
        """Test ResponseCreatedEvent.create factory method."""
        sse_data = ResponseCreatedEvent.create("conv-123")

        # Parse the SSE data - don't strip to preserve the double newline
        lines = sse_data.split("\n")
        assert len(lines) == 3  # data line + empty line + final empty line
        assert lines[0].startswith("data: ")
        assert lines[1] == ""  # Empty line after data
        assert lines[2] == ""  # Final empty line

        # Parse the JSON data
        json_data = json.loads(lines[0][6:])  # Remove 'data: ' prefix

        assert json_data["event"] == "response.created"
        assert json_data["conversation"] == "conv-123"
        assert "id" in json_data

    def test_create_output_text_delta_event(self):
        """Test ResponseOutputTextDeltaEvent.create factory method."""
        sse_data = ResponseOutputTextDeltaEvent.create("conv-123", "Hello, world!")

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.output_text.delta"
        assert json_data["conversation"] == "conv-123"
        assert json_data["content"] == "Hello, world!"

    def test_create_output_text_complete_event(self):
        """Test ResponseOutputTextCompleteEvent.create factory method."""
        sse_data = ResponseOutputTextCompleteEvent.create(
            "conv-123", "Complete content"
        )

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.output_text.complete"
        assert json_data["conversation"] == "conv-123"
        assert json_data["content"] == "Complete content"

    def test_create_tool_calls_delta_event(self):
        """Test ResponseToolCallsDeltaEvent.create factory method."""
        tool_calls = [{"id": "call_1", "name": "test_tool", "args": {"param": "value"}}]
        sse_data = ResponseToolCallsDeltaEvent.create("conv-123", tool_calls)

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.tool_calls.delta"
        assert json_data["conversation"] == "conv-123"
        assert json_data["tool_calls"] == tool_calls

    def test_create_tool_calls_complete_event(self):
        """Test ResponseToolCallsCompleteEvent.create factory method."""
        tool_calls = [{"id": "call_1", "name": "test_tool", "args": {"param": "value"}}]
        sse_data = ResponseToolCallsCompleteEvent.create("conv-123", tool_calls)

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.tool_calls.complete"
        assert json_data["conversation"] == "conv-123"
        assert json_data["tool_calls"] == tool_calls

    def test_create_resumed_event(self):
        """Test ResponseResumedEvent.create factory method."""
        sse_data = ResponseResumedEvent.create("conv-123")

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.resumed"
        assert json_data["conversation"] == "conv-123"

    def test_create_completed_event(self):
        """Test ResponseCompletedEvent.create factory method."""
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        sse_data = ResponseCompletedEvent.create("conv-123", usage)

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.completed"
        assert json_data["conversation"] == "conv-123"
        assert json_data["usage"] == usage

    def test_create_error_event(self):
        """Test ResponseErrorEvent.create factory method."""
        sse_data = ResponseErrorEvent.create(
            "conv-123", "Something went wrong", "Additional error details"
        )

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.error"
        assert json_data["conversation"] == "conv-123"
        assert json_data["error"] == "Something went wrong"
        assert json_data["detail"] == "Additional error details"

    def test_create_tool_event(self):
        """Test ResponseToolEvent.create factory method."""
        sse_data = ResponseToolEvent.create(
            "conv-123", "call-456", "test_tool", "success", "Tool execution result"
        )

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.tool"
        assert json_data["conversation"] == "conv-123"
        assert json_data["tool_call_id"] == "call-456"
        assert json_data["tool_name"] == "test_tool"
        assert json_data["status"] == "success"
        assert json_data["content"] == "Tool execution result"

    def test_create_update_event(self):
        """Test ResponseUpdateEvent.create factory method."""
        messages = [{"content": "Test message", "type": "ai"}]
        sse_data = ResponseUpdateEvent.create("conv-123", "test_task", messages)

        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.update"
        assert json_data["conversation"] == "conv-123"
        assert json_data["task"] == "test_task"
        assert json_data["messages"] == messages


class TestEventModelValidation:
    """Test event model validation and error handling."""

    def test_interrupt_event_without_action_request(self):
        """Test interrupt event with optional action field."""
        event = ResponseInterruptEvent(
            conversation="conv-123",
            interrupt_id="int-456",
            action="unknown",
            config={"timeout": 30},
            description="Test interrupt without action",
        )

        assert event.action == "unknown"
        assert event.config == {"timeout": 30}

    def test_interrupt_event_default_values(self):
        """Test interrupt event with default values."""
        event = ResponseInterruptEvent(conversation="conv-123", action="unknown")

        assert event.action == "unknown"
        assert event.args == {}
        assert event.config == {}
        assert event.description == ""

    def test_action_request_default_args(self):
        """Test interrupt event with default args."""
        event = ResponseInterruptEvent(conversation="conv-123", action="test_action")

        assert event.action == "test_action"
        assert event.args == {}

    def test_completed_event_without_usage(self):
        """Test completed event without usage information."""
        event = ResponseCompletedEvent(conversation="conv-123")

        assert event.event == "response.completed"
        assert event.conversation == "conv-123"
        assert event.usage is None

    def test_error_event_without_detail(self):
        """Test error event without detail information."""
        event = ResponseErrorEvent(
            conversation="conv-123", error="Something went wrong"
        )

        assert event.event == "response.error"
        assert event.conversation == "conv-123"
        assert event.error == "Something went wrong"
        assert event.detail is None


class TestSSEFormatCompliance:
    """Test that generated SSE events comply with the expected format."""

    def test_sse_format_structure(self):
        """Test that SSE events have the correct format structure."""
        sse_data = ResponseCreatedEvent.create("conv-123")

        # SSE format should be: "data: {json}\n\n"
        lines = sse_data.split("\n")
        assert len(lines) == 3  # data line + empty line + final empty line
        assert lines[0].startswith("data: ")
        assert lines[1] == ""  # Empty line after data
        assert lines[2] == ""  # Final empty line

        # JSON should be valid
        json_data = json.loads(lines[0][6:])
        assert isinstance(json_data, dict)

    def test_all_events_have_required_fields(self):
        """Test that all events have the required base fields."""
        events = [
            ResponseCreatedEvent.create("conv-123"),
            ResponseOutputTextDeltaEvent.create("conv-123", "test"),
            ResponseOutputTextCompleteEvent.create("conv-123", "test"),
            ResponseToolCallsDeltaEvent.create("conv-123", []),
            ResponseToolCallsCompleteEvent.create("conv-123", []),
            ResponseInterruptEvent.create("conv-123", "int-1", "action", {}),
            ResponseResumedEvent.create("conv-123"),
            ResponseCompletedEvent.create("conv-123"),
            ResponseErrorEvent.create("conv-123", "error"),
        ]

        for sse_data in events:
            json_data = json.loads(sse_data.split("\n")[0][6:])

            # All events should have these required fields
            assert "event" in json_data
            assert "id" in json_data
            assert "conversation" in json_data

            # Event should be a string
            assert isinstance(json_data["event"], str)
            # ID should be a string
            assert isinstance(json_data["id"], str)
            # Conversation should be a string
            assert isinstance(json_data["conversation"], str)


class TestConversionFunctions:
    """Test conversion functions from internal models to SSE events."""

    def test_convert_message_chunk_to_sse_event(self):
        """Test converting a message chunk to SSE event."""
        chunk = MessageChunk(
            type="message",
            conversation_id="conv-123",
            task="test_task",
            content="Hello, world!",
            id="msg-123",
        )

        context = StreamingContext("conv-123")
        sse_data = create_streaming_event_from_chunk(chunk, "conv-123", context)
        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.output_text.delta"
        assert json_data["conversation"] == "conv-123"
        assert json_data["content"] == "Hello, world!"

    def test_convert_tool_call_chunk_to_sse_event(self):
        """Test converting tool call chunk to SSE event."""
        tool_calls = [{"id": "call_1", "name": "test_tool", "args": {"param": "value"}}]
        chunk = ToolCallChunk(
            type="tool_call",
            conversation_id="conv-123",
            task="test_task",
            id="tool-123",
            tool_calls=tool_calls,
        )

        context = StreamingContext("conv-123")
        sse_data = create_streaming_event_from_chunk(chunk, "conv-123", context)
        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.tool_calls.delta"
        assert json_data["conversation"] == "conv-123"
        assert json_data["tool_calls"] == tool_calls

    def test_convert_interrupt_chunk_to_sse_event(self):
        """Test converting interrupt chunk to SSE event."""
        interrupt_data = {
            "action_request": {
                "action": "test_action",
                "args": {"param": "value"},
            },
            "config": {"timeout": 30},
            "description": "Test interrupt",
        }
        chunk = InterruptChunk(
            type="interrupt",
            conversation_id="conv-123",
            id="int-456",
            value=interrupt_data,
        )

        context = StreamingContext("conv-123")
        sse_data = create_streaming_event_from_chunk(chunk, "conv-123", context)
        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.interrupt"
        assert json_data["conversation"] == "conv-123"
        assert json_data["interrupt_id"] == "int-456"
        assert json_data["action"] == "test_action"
        assert json_data["args"] == {"param": "value"}
        assert json_data["config"] == {"timeout": 30}
        assert json_data["description"] == "Test interrupt"

    def test_convert_tool_chunk_to_sse_event(self):
        """Test converting tool chunk to SSE event."""
        chunk = ToolChunk(
            type="tool",
            conversation_id="conv-123",
            id="tool-123",
            status="success",
            tool_call_id="call-456",
            content="Tool result content",
            tool_name="test_tool",
        )

        context = StreamingContext("conv-123")
        sse_data = create_streaming_event_from_chunk(chunk, "conv-123", context)
        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.tool"
        assert json_data["conversation"] == "conv-123"
        assert json_data["tool_call_id"] == "call-456"
        assert json_data["tool_name"] == "test_tool"
        assert json_data["status"] == "success"
        assert json_data["content"] == "Tool result content"

    def test_convert_update_chunk_to_sse_event(self):
        """Test converting update chunk to SSE event."""
        from nalai.core.agent import Message

        messages = [
            Message(
                content="Test message",
                type="ai",
                id="msg-123",
            )
        ]
        chunk = UpdateChunk(
            type="update",
            conversation_id="conv-123",
            task="test_task",
            messages=messages,
        )

        context = StreamingContext("conv-123")
        sse_data = create_streaming_event_from_chunk(chunk, "conv-123", context)
        json_data = json.loads(sse_data.split("\n")[0][6:])

        assert json_data["event"] == "response.update"
        assert json_data["conversation"] == "conv-123"
        assert json_data["task"] == "test_task"
        assert len(json_data["messages"]) == 1
        assert json_data["messages"][0]["content"] == "Test message"

    def test_create_streaming_event_from_chunk_with_unknown_type(self):
        """Test the main conversion function with unknown chunk type."""
        # Test with a mock chunk that doesn't match any known type
        mock_chunk = Mock()
        mock_chunk.__class__.__name__ = "UnknownChunk"

        context = StreamingContext("conv-123")
        sse_data = create_streaming_event_from_chunk(mock_chunk, "conv-123", context)

        # Should return empty string for unknown types
        assert sse_data == ""
