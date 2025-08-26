"""
Tests for SSE serializer utilities.
"""

import json

import pytest

from nalai.server.sse_serializer import (
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    ResponseMessageEvent,
    ResponseResumedEvent,
    create_custom_event,
    create_event,
    create_streaming_event,
    serialize_to_sse,
)


class TestSerializeToSSE:
    """Test the basic serialize_to_sse function."""

    def test_serialize_to_sse_basic(self):
        """Test basic SSE serialization."""
        event = {"message": "Hello, World!"}
        result = serialize_to_sse(event, lambda x: x)
        expected = f"data: {json.dumps(event)}\n\n"
        assert result == expected

    def test_serialize_to_sse_with_serialize_event_default(self):
        """Test SSE serialization with custom serialize function."""
        event = {"message": "Hello, World!"}
        result = serialize_to_sse(event, lambda x: {"custom": x})
        expected = f"data: {json.dumps({'custom': event})}\n\n"
        assert result == expected

    def test_serialize_to_sse_complex_object(self):
        """Test SSE serialization with complex nested object."""
        event = {
            "nested": {
                "list": [1, 2, 3],
                "dict": {"key": "value"},
                "null": None,
                "bool": True,
            }
        }
        result = serialize_to_sse(event, lambda x: x)
        expected = f"data: {json.dumps(event)}\n\n"
        assert result == expected


class TestPydanticEventModels:
    """Test Pydantic event models."""

    def test_response_resumed_event(self):
        """Test ResponseResumedEvent model."""
        event = ResponseResumedEvent(conversation="conv-123")
        assert event.event == "response.resumed"
        assert event.conversation == "conv-123"
        assert event.id is not None

    def test_response_message_event(self):
        """Test ResponseMessageEvent model."""
        event = ResponseMessageEvent(
            conversation="conv-123", content="Hello", role="assistant"
        )
        assert event.event == "response.message"
        assert event.conversation == "conv-123"
        assert event.content == "Hello"
        assert event.role == "assistant"

    def test_response_completed_event(self):
        """Test ResponseCompletedEvent model."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20}
        event = ResponseCompletedEvent(conversation="conv-123", usage=usage)
        assert event.event == "response.completed"
        assert event.conversation == "conv-123"
        assert event.usage == usage

    def test_response_error_event(self):
        """Test ResponseErrorEvent model."""
        event = ResponseErrorEvent(
            conversation="conv-123", error="Something went wrong"
        )
        assert event.event == "response.error"
        assert event.conversation == "conv-123"
        assert event.error == "Something went wrong"

    def test_response_created_event(self):
        """Test ResponseCreatedEvent model."""
        event = ResponseCreatedEvent(conversation="conv-123")
        assert event.event == "response.created"
        assert event.conversation == "conv-123"


class TestEventCreationFunctions:
    """Test the event creation functions using the direct pattern."""

    def test_create_response_resumed_event(self):
        """Test create_event with ResponseResumedEvent."""
        result = create_event(ResponseResumedEvent, "conv-123")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        # Parse the JSON to verify structure
        json_str = result[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(json_str)
        assert data["event"] == "response.resumed"
        assert data["conversation"] == "conv-123"
        assert "id" in data

    def test_create_response_message_event(self):
        """Test create_event with ResponseMessageEvent."""
        result = create_event(ResponseMessageEvent, "conv-123", content="Hello World", role="assistant")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["event"] == "response.message"
        assert data["conversation"] == "conv-123"
        assert data["content"] == "Hello World"
        assert data["role"] == "assistant"

    def test_create_response_message_event_default_role(self):
        """Test create_event with ResponseMessageEvent using default role."""
        result = create_event(ResponseMessageEvent, "conv-123", content="Hello World")
        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["role"] == "assistant"

    def test_create_response_completed_event(self):
        """Test create_event with ResponseCompletedEvent."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20}
        result = create_event(ResponseCompletedEvent, "conv-123", usage=usage)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["event"] == "response.completed"
        assert data["conversation"] == "conv-123"
        assert data["usage"] == usage

    def test_create_response_completed_event_no_usage(self):
        """Test create_event with ResponseCompletedEvent without usage."""
        result = create_event(ResponseCompletedEvent, "conv-123")
        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["usage"] is None

    def test_create_response_error_event(self):
        """Test create_event with ResponseErrorEvent."""
        result = create_event(ResponseErrorEvent, "conv-123", error="Something went wrong")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["event"] == "response.error"
        assert data["conversation"] == "conv-123"
        assert data["error"] == "Something went wrong"

    def test_create_response_created_event(self):
        """Test create_event with ResponseCreatedEvent."""
        result = create_event(ResponseCreatedEvent, "conv-123")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["event"] == "response.created"
        assert data["conversation"] == "conv-123"


class TestGenericEventFactory:
    """Test the generic event factory function."""

    def test_create_event_with_response_resumed(self):
        """Test create_event with ResponseResumedEvent."""
        result = create_event(ResponseResumedEvent, "conv-123")
        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["event"] == "response.resumed"
        assert data["conversation"] == "conv-123"

    def test_create_event_with_response_message(self):
        """Test create_event with ResponseMessageEvent."""
        result = create_event(
            ResponseMessageEvent, "conv-123", content="Hello", role="user"
        )
        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["event"] == "response.message"
        assert data["conversation"] == "conv-123"
        assert data["content"] == "Hello"
        assert data["role"] == "user"


class TestStreamingAndCustomEvents:
    """Test streaming and custom event functions."""

    def test_create_streaming_event(self):
        """Test create_streaming_event function."""
        event = {"type": "token", "content": "Hello"}
        result = create_streaming_event(event, lambda x: x)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data == event

    def test_create_custom_event(self):
        """Test create_custom_event function."""
        result = create_custom_event("custom.event", "conv-123", data="test", count=42)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["event"] == "custom.event"
        assert data["conversation"] == "conv-123"
        assert data["data"] == "test"
        assert data["count"] == 42


class TestEventValidation:
    """Test event validation and error handling."""

    def test_event_models_require_conversation(self):
        """Test that event models require conversation_id."""
        with pytest.raises(ValueError):
            ResponseResumedEvent()  # Missing conversation_id

    def test_event_models_require_content_for_message(self):
        """Test that ResponseMessageEvent requires content."""
        with pytest.raises(ValueError):
            ResponseMessageEvent(conversation="conv-123")  # Missing content

    def test_event_models_require_error_for_error_event(self):
        """Test that ResponseErrorEvent requires error message."""
        with pytest.raises(ValueError):
            ResponseErrorEvent(conversation="conv-123")  # Missing error
