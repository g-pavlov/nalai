"""
Tests for serialization utilities.
"""

from unittest.mock import Mock

import pytest

from nalai.core.serialization import (
    filter_langgraph_streaming_chunk,
    serialize_event,
    serialize_langgraph_streaming_chunk,
)


class TestSerializeEventDefault:
    """Test the default serialize_event function."""

    @pytest.mark.parametrize(
        "event,expected_keys,expected_absent_keys",
        [
            (
                {
                    "api_specs": "secret",
                    "messages": ["hello"],
                    "data": {"api_summaries": "secret"},
                },
                ["messages", "data"],
                ["api_specs", "api_summaries"],
            ),
            (
                {"config": {"enabled": True, "api_specs": "secret"}},
                ["config"],
                ["api_specs"],
            ),
            (
                {"__interrupt__": [{"value": "test"}]},
                ["__interrupt__"],
                [],
            ),
        ],
    )
    def test_serialize_event_filters_sensitive_data(
        self, event, expected_keys, expected_absent_keys
    ):
        """Test that sensitive data is filtered from serialized events."""
        result = serialize_event(event)

        # Check that expected keys are present
        for key in expected_keys:
            assert key in result

        # Check that sensitive keys are absent
        for key in expected_absent_keys:
            assert key not in str(result)

    @pytest.mark.parametrize(
        "event,expected_type",
        [
            ({"key": "value"}, dict),
            ("simple string", str),
            (["item1", "item2"], list),
            (["item1", "item2"], list),
        ],
    )
    def test_serialize_event_basic_types(self, event, expected_type):
        """Test serialization of basic types."""
        result = serialize_event(event)
        assert isinstance(result, expected_type)

    def test_serialize_event_pydantic_model(self):
        """Test serialization of Pydantic models."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            value: int

        model = TestModel(name="test", value=42)
        result = serialize_event(model)
        assert result["name"] == "test"
        assert result["value"] == "42"  # Serialization converts to string

    def test_serialize_event_langchain_message(self):
        """Test serialization of LangChain messages."""

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

        message = MockLangChainMessage()
        result = serialize_event(message)

        # The result should be a dict with the message properties
        assert isinstance(result, dict)
        assert result["type"] == "HumanMessage"
        assert result["content"] == "Hello"
        assert result["id"] == "msg_123"

    def test_serialize_event_with_exception_handling(self):
        """Test that exceptions during serialization are handled gracefully."""

        class FailingObj:
            def __str__(self):
                raise Exception("Serialization failed")

            def __repr__(self):
                return "<FailingObj>"

        result = serialize_event(FailingObj())
        # The function should handle exceptions gracefully
        # For objects without __dict__, it returns an empty dict
        assert isinstance(result, dict)
        assert result == {}


class TestLangGraphStreamingChunkFiltering:
    """Test LangGraph streaming chunk filtering functions."""

    def test_filter_langgraph_streaming_chunk_message(self):
        """Test filtering of message chunks."""
        # Create a mock message chunk
        message_chunk = Mock()
        message_chunk.content = "Hello world"
        message_chunk.type = "human"
        message_chunk.id = "msg_123"
        message_chunk.tool_calls = None

        result = filter_langgraph_streaming_chunk(message_chunk, "conv_123")

        assert result["content"] == "Hello world"
        assert result["type"] == "human"
        assert result["id"] == "msg_123"
        assert result["conversation"] == "conv_123"

    def test_filter_langgraph_streaming_chunk_with_sensitive_fields(self):
        """Test that sensitive fields are filtered from chunks."""
        # Create a chunk with sensitive fields
        chunk = Mock()
        chunk.__dict__ = {
            "messages": ["hello"],
            "auth_token": "secret",
            "user_id": "user123",
            "thread_id": "thread123",
        }

        result = filter_langgraph_streaming_chunk(chunk, "conv_123")

        assert "messages" in result
        assert "auth_token" not in result
        assert "user_id" not in result
        assert "thread_id" not in result
        assert result["conversation"] == "conv_123"

    def test_filter_langgraph_streaming_chunk_pure_internal_state(self):
        """Test that chunks with only internal state are filtered out."""
        # Create a chunk with only sensitive fields
        chunk = Mock()
        chunk.__dict__ = {
            "auth_token": "secret",
            "user_id": "user123",
            "thread_id": "thread123",
        }

        result = filter_langgraph_streaming_chunk(chunk, "conv_123")
        assert result is None

    def test_filter_langgraph_streaming_chunk_dict(self):
        """Test filtering of dictionary chunks."""
        chunk = {
            "messages": ["hello"],
            "selected_apis": ["api1"],
            "auth_token": "secret",
            "user_id": "user123",
        }

        result = filter_langgraph_streaming_chunk(chunk, "conv_123")

        assert "messages" in result
        assert "selected_apis" in result
        assert "auth_token" not in result
        assert "user_id" not in result
        assert result["conversation"] == "conv_123"

    def test_serialize_langgraph_streaming_chunk(self):
        """Test the combined filter and serialize function."""
        message_chunk = Mock()
        message_chunk.content = "Hello world"
        message_chunk.type = "human"
        message_chunk.id = "msg_123"

        result = serialize_langgraph_streaming_chunk(message_chunk, "conv_123")

        # Should be a serialized dict
        assert isinstance(result, dict)
        assert result["content"] == "Hello world"
        assert result["type"] == "human"
        assert result["conversation"] == "conv_123"

    def test_serialize_langgraph_streaming_chunk_filtered_out(self):
        """Test that chunks filtered out return None."""
        # Create a chunk with only sensitive fields
        chunk = Mock()
        chunk.__dict__ = {
            "auth_token": "secret",
            "user_id": "user123",
        }

        result = serialize_langgraph_streaming_chunk(chunk, "conv_123")
        assert result is None
