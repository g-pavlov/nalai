"""
Tests for message serializer utilities.
"""

from unittest.mock import Mock

from nalai.core.lc_transformers import (
    _extract_finish_reason,
    _extract_usage,
    extract_usage_from_messages,
)
from nalai.server.message_serializer import convert_messages_to_output
from nalai.server.schemas.messages import (
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

    def test_convert_messages_to_output_human(self):
        """Test converting human message to output format."""

        class HumanMessage:
            def __init__(self):
                self.content = "Hello"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        human_message = HumanMessage()
        human_message.__class__.__name__ = "HumanMessage"

        result = convert_messages_to_output(
            [human_message], "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert len(result) == 1
        assert isinstance(result[0], HumanOutputMessage)
        assert result[0].content[0].text == "Hello"

    def test_convert_messages_to_output_ai(self):
        """Test converting AI message to output format."""

        class AIMessage:
            def __init__(self):
                self.content = "Hello there"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        ai_message = AIMessage()
        ai_message.__class__.__name__ = "AIMessage"

        result = convert_messages_to_output(
            [ai_message], "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert len(result) == 1
        assert isinstance(result[0], AssistantOutputMessage)
        assert result[0].content[0].text == "Hello there"

    def test_convert_messages_to_output_tool(self):
        """Test converting tool message to output format."""

        class ToolMessage:
            def __init__(self):
                self.content = "Tool result"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = "call_123"

        tool_message = ToolMessage()
        tool_message.__class__.__name__ = "ToolMessage"

        result = convert_messages_to_output(
            [tool_message], "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert len(result) == 1
        assert isinstance(result[0], ToolOutputMessage)
        assert result[0].content[0].text == "Tool result"
        assert result[0].tool_call_id == "call_123"

    def test_convert_messages_to_output_multiple(self):
        """Test converting multiple messages to output format."""

        class HumanMessage:
            def __init__(self):
                self.content = "Hello"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        class AIMessage:
            def __init__(self):
                self.content = "Hi there"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        human_message = HumanMessage()
        human_message.__class__.__name__ = "HumanMessage"

        ai_message = AIMessage()
        ai_message.__class__.__name__ = "AIMessage"

        result = convert_messages_to_output(
            [human_message, ai_message], "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert len(result) == 2
        assert isinstance(result[0], HumanOutputMessage)
        assert isinstance(result[1], AssistantOutputMessage)
        assert result[0].content[0].text == "Hello"
        assert result[1].content[0].text == "Hi there"

    def test_extract_usage_from_streaming_chunks(self):
        """Test extracting usage from streaming chunks."""
        from nalai.server.sse_serializer import extract_usage_from_streaming_chunks

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
        from nalai.server.sse_serializer import extract_usage_from_streaming_chunks

        result = extract_usage_from_streaming_chunks([])
        assert result == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
