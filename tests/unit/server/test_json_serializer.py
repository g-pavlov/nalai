"""
Tests for message serializer utilities.
"""

from unittest.mock import Mock

from nalai.core.lc_transformers import (
    _extract_finish_reason,
    _extract_usage,
    extract_usage_from_messages,
)
from nalai.server.json_serializer import serialize_messages
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

    def test_serialize_messages_human(self):
        """Test serializing human message to output format."""

        class HumanMessage:
            def __init__(self):
                self.content = "Hello"
                self.type = "human"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        human_message = HumanMessage()
        human_message.__class__.__name__ = "HumanMessage"

        result = serialize_messages(
            [human_message], "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert len(result) == 1
        assert isinstance(result[0], HumanOutputMessage)
        assert result[0].content[0].text == "Hello"

    def test_serialize_messages_ai(self):
        """Test serializing AI message to output format."""

        class AIMessage:
            def __init__(self):
                self.content = "Hello there"
                self.type = "ai"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        ai_message = AIMessage()
        ai_message.__class__.__name__ = "AIMessage"

        result = serialize_messages(
            [ai_message], "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert len(result) == 1
        assert isinstance(result[0], AssistantOutputMessage)
        assert result[0].content[0].text == "Hello there"

    def test_serialize_messages_tool(self):
        """Test serializing tool message to output format."""

        class ToolCall:
            def __init__(self, id, name, args):
                self.id = id
                self.name = name
                self.args = args

        class AIMessage:
            def __init__(self):
                self.content = "I'll call a tool"
                self.type = "ai"
                self.tool_calls = [
                    ToolCall("call_123", "test_tool", {"param": "value"})
                ]
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        class ToolMessage:
            def __init__(self):
                self.content = "Tool result"
                self.type = "tool"
                self.tool_calls = [
                    ToolCall("call_123", "test_tool", {"param": "value"})
                ]
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = "call_123"
                self.status = "completed"

        ai_message = AIMessage()
        ai_message.__class__.__name__ = "AIMessage"
        tool_message = ToolMessage()
        tool_message.__class__.__name__ = "ToolMessage"

        result = serialize_messages(
            [ai_message, tool_message], "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        )
        assert len(result) == 2
        assert isinstance(result[0], AssistantOutputMessage)
        assert isinstance(result[1], ToolOutputMessage)
        assert result[0].content[0].text == "I'll call a tool"
        assert result[1].content[0].text == "Tool result"
        assert result[1].tool_call_id == "call_123"

    def test_serialize_messages_multiple(self):
        """Test serializing multiple messages to output format."""

        class HumanMessage:
            def __init__(self):
                self.content = "Hello"
                self.type = "human"
                self.tool_calls = None
                self.invalid_tool_calls = None
                self.response_metadata = None
                self.usage = None
                self.finish_reason = None
                self.tool_call_id = None

        class AIMessage:
            def __init__(self):
                self.content = "Hi there"
                self.type = "ai"
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

        result = serialize_messages(
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

    def test_serialize_error_response(self):
        """Test serializing error response to output format."""
        from nalai.server.json_serializer import serialize_error_response

        # Create a test exception
        test_error = Exception("Test error message")
        run_id = "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        conversation_id = "conv_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"
        previous_response_id = "run_2b1c3d4e5f6g7h8i9j2k3m4n5p6q7r8s9"

        result = serialize_error_response(
            error=test_error,
            run_id=run_id,
            conversation_id=conversation_id,
            previous_response_id=previous_response_id,
        )

        # Verify the response structure
        assert result.id == run_id
        assert result.conversation_id == conversation_id
        assert result.previous_response_id == previous_response_id
        assert result.status == "error"
        assert result.interrupts is None
        assert result.metadata is not None
        assert result.metadata.error == "Test error message"

        # Verify the output message
        assert len(result.output) == 1
        output_message = result.output[0]
        assert output_message.id == f"msg_{run_id.replace('run_', '')}"
        assert output_message.role == "assistant"
        assert output_message.content[0].text == "Error: Test error message"
        assert output_message.finish_reason == "stop"
        assert output_message.usage == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        # Verify usage
        assert result.usage == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
