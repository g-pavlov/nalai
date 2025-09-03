"""
Tests for message serializer utilities.
"""

from unittest.mock import Mock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from nalai.core.lc_transformers import (
    _extract_finish_reason,
    _extract_usage,
    extract_usage_from_messages,
    transform_message,
)
from nalai.core.types.messages import (
    AssistantOutputMessage,
    HumanOutputMessage,
    ToolOutputMessage,
)


class TestMessageSerializer:
    """Test message serialization utilities."""

    def test_extract_finish_reason_direct(self):
        """Test extracting finish_reason from direct attribute."""
        message = Mock()
        message.finish_reason = "stop"

        result = _extract_finish_reason(message)
        assert result == "stop"

    def test_extract_finish_reason_from_response_metadata(self):
        """Test extracting finish_reason from response_metadata."""

        class TestMessage:
            def __init__(self):
                self.finish_reason = None
                self.response_metadata = {"finish_reason": "length"}
                self.additional_kwargs = None

        message = TestMessage()
        result = _extract_finish_reason(message)
        assert result == "length"

    def test_extract_finish_reason_from_additional_kwargs(self):
        """Test extracting finish_reason from additional_kwargs."""

        class TestMessage:
            def __init__(self):
                self.finish_reason = None
                self.response_metadata = None
                self.additional_kwargs = {"finish_reason": "tool_calls"}

        message = TestMessage()
        result = _extract_finish_reason(message)
        assert result == "tool_calls"

    def test_extract_finish_reason_none(self):
        """Test extracting finish_reason when not available."""
        message = Mock()
        message.finish_reason = None
        message.response_metadata = None
        message.additional_kwargs = None

        result = _extract_finish_reason(message)
        assert result is None

    def test_extract_usage_from_usage_metadata(self):
        """Test extracting usage from usage_metadata."""
        message = Mock()
        message.usage_metadata = {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }
        message.usage = None

        result = _extract_usage(message)
        assert result == {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }

    def test_extract_usage_from_usage_attribute(self):
        """Test extracting usage from usage attribute."""
        message = Mock()
        message.usage_metadata = None
        message.usage = {
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40,
        }

        result = _extract_usage(message)
        assert result == {
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40,
        }

    def test_extract_usage_none(self):
        """Test extracting usage when not available."""
        message = Mock()
        message.usage_metadata = None
        message.usage = None

        result = _extract_usage(message)
        assert result is None

    def test_extract_usage_from_messages_multiple(self):
        """Test extracting usage from multiple messages."""

        # Create test messages with different usage formats
        class Message1:
            def __init__(self):
                self.usage_metadata = {
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                }

        class Message2:
            def __init__(self):
                self.usage = {
                    "prompt_tokens": 15,
                    "completion_tokens": 25,
                    "total_tokens": 40,
                }

        class Message3:
            def __init__(self):
                self.usage_metadata = {
                    "input_tokens": 5,
                    "output_tokens": 10,
                    "total_tokens": 15,
                }

        messages = [Message1(), Message2(), Message3()]
        result = extract_usage_from_messages(messages)

        assert result == {
            "prompt_tokens": 30,  # 10 + 15 + 5
            "completion_tokens": 55,  # 20 + 25 + 10
            "total_tokens": 85,  # 30 + 40 + 15
        }

    def test_extract_usage_from_messages_empty(self):
        """Test extracting usage from empty message list."""
        result = extract_usage_from_messages([])
        assert result == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def test_extract_usage_from_messages_mixed_formats(self):
        """Test extracting usage from messages with mixed formats."""

        class Message1:
            def __init__(self):
                self.usage_metadata = {
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                }

        class Message2:
            def __init__(self):
                self.usage = {
                    "prompt_tokens": 15,
                    "completion_tokens": 25,
                    "total_tokens": 40,
                }

        messages = [Message1(), Message2()]
        result = extract_usage_from_messages(messages)

        assert result == {
            "prompt_tokens": 25,  # 10 + 15
            "completion_tokens": 45,  # 20 + 25
            "total_tokens": 70,  # 30 + 40
        }

    def test_transform_message_human(self):
        """Test serializing human message to output format."""

        # Use real LangChain class instead of custom mock
        human_message = HumanMessage(content="Hello", id="human_msg_123")

        result = transform_message(
            human_message, "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert isinstance(result, HumanOutputMessage)
        assert result.content[0].text == "Hello"

    def test_transform_message_ai(self):
        """Test serializing AI message to output format."""

        # Use real LangChain class instead of custom mock
        ai_message = AIMessage(
            content="Hello there",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            id="ai_msg_456",
        )

        result = transform_message(ai_message, "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9")
        assert isinstance(result, AssistantOutputMessage)
        assert result.content[0].text == "Hello there"

    def test_transform_message_tool(self):
        """Test serializing tool message to output format."""

        # Use real LangChain classes instead of custom mocks
        ai_message = AIMessage(
            content="I'll call a tool",
            tool_calls=[
                {"id": "call_123", "name": "test_tool", "args": {"param": "value"}}
            ],
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            id="run_123",
        )

        tool_message = ToolMessage(
            content="Tool result", tool_call_id="call_123", id="tool_msg_123"
        )

        ai_result = transform_message(
            ai_message, "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        tool_result = transform_message(
            tool_message,
            "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9",
            conversation_id="conv_test_123",
        )
        assert isinstance(ai_result, AssistantOutputMessage)
        assert isinstance(tool_result, ToolOutputMessage)
        assert ai_result.content[0].text == "I'll call a tool"
        assert tool_result.content[0].text == "Tool result"
        assert tool_result.tool_call_id == "call_123"

    def test_transform_message_multiple(self):
        """Test serializing multiple messages to output format."""

        # Use real LangChain classes instead of custom mocks
        human_message = HumanMessage(content="Hello", id="human_msg_789")

        ai_message = AIMessage(
            content="Hi there",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            id="ai_msg_789",
        )

        human_result = transform_message(
            human_message, "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        ai_result = transform_message(
            ai_message, "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert isinstance(human_result, HumanOutputMessage)
        assert isinstance(ai_result, AssistantOutputMessage)
        assert human_result.content[0].text == "Hello"
        assert ai_result.content[0].text == "Hi there"

    def test_extract_usage_from_streaming_chunks(self):
        """Test extracting usage from streaming chunks."""
        from nalai.core.types.streaming import extract_usage_from_streaming_chunks

        # Create mock streaming chunks with usage data
        class MockChunk1:
            def __init__(self):
                self.usage = {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                }

        class MockChunk2:
            def __init__(self):
                self.usage = {
                    "prompt_tokens": 15,
                    "completion_tokens": 25,
                    "total_tokens": 40,
                }

        class MockChunk3:
            def __init__(self):
                self.usage = None  # No usage data

        chunks = [MockChunk1(), MockChunk2(), MockChunk3()]
        result = extract_usage_from_streaming_chunks(chunks)

        assert result == {
            "prompt_tokens": 25,  # 10 + 15
            "completion_tokens": 45,  # 20 + 25
            "total_tokens": 70,  # 30 + 40
        }

    def test_extract_usage_from_streaming_chunks_empty(self):
        """Test extracting usage from empty streaming chunks list."""
        from nalai.core.types.streaming import extract_usage_from_streaming_chunks

        result = extract_usage_from_streaming_chunks([])
        assert result == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    # test_serialize_error_response removed - function no longer exists
