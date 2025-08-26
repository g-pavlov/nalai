"""
Tests for message serializer utilities.
"""

import pytest
from unittest.mock import Mock

from nalai.server.message_serializer import (
    convert_messages_to_output,
    extract_usage_from_messages,
    _extract_finish_reason,
    _extract_usage,
    _convert_tool_calls,
    _create_content_blocks,
    _create_output_message,
)
from nalai.server.schemas.messages import (
    AssistantOutputMessage,
    HumanOutputMessage,
    TextContent,
    ToolCall,
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

    def test_extract_usage_default(self):
        """Test extracting usage when not available."""
        message = Mock()
        message.usage_metadata = None
        message.usage = None
        
        result = _extract_usage(message)
        assert result == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def test_convert_tool_calls_valid(self):
        """Test converting valid tool calls."""
        raw_tool_calls = [
            {"id": "call_1", "name": "test_tool", "args": {"param": "value"}},
            {"id": "call_2", "name": "another_tool", "args": {}},
        ]
        
        result = _convert_tool_calls(raw_tool_calls)
        assert len(result) == 2
        assert result[0].id == "call_1"
        assert result[0].name == "test_tool"
        assert result[0].args == {"param": "value"}
        assert result[1].id == "call_2"
        assert result[1].name == "another_tool"
        assert result[1].args == {}

    def test_convert_tool_calls_none(self):
        """Test converting None tool calls."""
        result = _convert_tool_calls(None)
        assert result is None

    def test_convert_tool_calls_empty(self):
        """Test converting empty tool calls."""
        result = _convert_tool_calls([])
        assert result is None

    def test_create_content_blocks_with_content(self):
        """Test creating content blocks with content."""
        message = Mock()
        message.content = "Hello, world!"
        
        result = _create_content_blocks(message)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert result[0].text == "Hello, world!"

    def test_create_content_blocks_no_content(self):
        """Test creating content blocks without content."""
        message = Mock()
        message.content = None
        
        result = _create_content_blocks(message)
        assert result == []

    def test_create_output_message_human(self):
        """Test creating human output message."""
        content_blocks = [TextContent(text="Hello")]
        
        result = _create_output_message(
            "human", content_blocks, None, None, None, {}, None
        )
        
        assert isinstance(result, HumanOutputMessage)
        assert result.content == content_blocks
        assert result.id is not None

    def test_create_output_message_ai(self):
        """Test creating AI output message."""
        content_blocks = [TextContent(text="Hello")]
        tool_calls = [ToolCall(id="call_1", name="test", args={})]
        invalid_tool_calls = [{"error": "test"}]
        
        result = _create_output_message(
            "ai", content_blocks, tool_calls, invalid_tool_calls, "stop", {"total_tokens": 10}, None
        )
        
        assert isinstance(result, AssistantOutputMessage)
        assert result.content == content_blocks
        assert result.tool_calls == tool_calls
        assert result.invalid_tool_calls == invalid_tool_calls
        assert result.finish_reason == "stop"
        assert result.usage == {"total_tokens": 10}
        assert result.id is not None

    def test_create_output_message_tool(self):
        """Test creating tool output message."""
        content_blocks = [TextContent(text="Tool result")]
        message = Mock()
        message.tool_call_id = "call_1"
        
        result = _create_output_message(
            "tool", content_blocks, None, None, None, {}, message
        )
        
        assert isinstance(result, ToolOutputMessage)
        assert result.content == content_blocks
        assert result.tool_call_id == "call_1"
        assert result.id is not None

    def test_create_output_message_unknown_type(self):
        """Test creating output message for unknown type."""
        content_blocks = [TextContent(text="Unknown")]
        
        result = _create_output_message(
            "unknown", content_blocks, None, None, None, {}, None
        )
        
        # Should fallback to human message
        assert isinstance(result, HumanOutputMessage)
        assert result.content == content_blocks
        assert result.id is not None

    def test_convert_messages_to_output_human(self):
        """Test converting human messages to output."""
        human_message = Mock()
        human_message.__class__.__name__ = "HumanMessage"
        human_message.content = "Hello"
        human_message.tool_calls = None
        human_message.invalid_tool_calls = None
        
        result = convert_messages_to_output([human_message])
        
        assert len(result) == 1
        assert isinstance(result[0], HumanOutputMessage)
        assert result[0].content[0].text == "Hello"

    def test_convert_messages_to_output_ai(self):
        """Test converting AI messages to output."""
        ai_message = Mock()
        ai_message.__class__.__name__ = "AIMessage"
        ai_message.content = "AI response"
        ai_message.tool_calls = [{"id": "call_1", "name": "test", "args": {}}]
        ai_message.invalid_tool_calls = None
        ai_message.finish_reason = "stop"
        ai_message.usage_metadata = {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }
        
        result = convert_messages_to_output([ai_message])
        
        assert len(result) == 1
        assert isinstance(result[0], AssistantOutputMessage)
        assert result[0].content[0].text == "AI response"
        assert len(result[0].tool_calls) == 1
        assert result[0].tool_calls[0].id == "call_1"
        assert result[0].finish_reason == "stop"
        assert result[0].usage["total_tokens"] == 30

    def test_convert_messages_to_output_tool(self):
        """Test converting tool messages to output."""
        tool_message = Mock()
        tool_message.__class__.__name__ = "ToolMessage"
        tool_message.content = "Tool result"
        tool_message.tool_call_id = "call_1"
        tool_message.tool_calls = None
        tool_message.invalid_tool_calls = None
        
        result = convert_messages_to_output([tool_message])
        
        assert len(result) == 1
        assert isinstance(result[0], ToolOutputMessage)
        assert result[0].content[0].text == "Tool result"
        assert result[0].tool_call_id == "call_1"

    def test_extract_usage_from_messages_multiple(self):
        """Test extracting usage from multiple messages."""
        class Message1:
            def __init__(self):
                self.usage_metadata = {
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                }
                self.usage = None
        
        class Message2:
            def __init__(self):
                self.usage_metadata = None
                self.usage = {
                    "prompt_tokens": 15,
                    "completion_tokens": 25,
                    "total_tokens": 40,
                }
        
        class Message3:
            def __init__(self):
                self.usage_metadata = None
                self.usage = None
        
        message1 = Message1()
        message2 = Message2()
        message3 = Message3()
        
        result = extract_usage_from_messages([message1, message2, message3])
        
        assert result == {
            "prompt_tokens": 25,  # 10 + 15
            "completion_tokens": 45,  # 20 + 25
            "total_tokens": 70,  # 30 + 40
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
        message1 = Mock()
        message1.usage_metadata = {
            "input_tokens": 5,
            "output_tokens": 10,
            "total_tokens": 15,
        }
        
        message2 = Mock()
        message2.usage_metadata = None
        message2.usage = {
            "prompt_tokens": 8,
            "completion_tokens": 12,
            "total_tokens": 20,
        }
        
        result = extract_usage_from_messages([message1, message2])
        
        assert result == {
            "prompt_tokens": 13,  # 5 + 8
            "completion_tokens": 22,  # 10 + 12
            "total_tokens": 35,  # 15 + 20
        }


