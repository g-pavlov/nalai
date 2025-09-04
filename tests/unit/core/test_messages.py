"""
Unit tests for message functionality.

Tests cover message types, content blocks, and validation.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

import pytest

from nalai.core.messages import (
    AssistantOutputMessage,
    HumanInputMessage,
    HumanOutputMessage,
    InputMessage,
    OutputMessage,
    TextContent,
    ToolCall,
    ToolCallDecision,
)


class TestTextContent:
    """Test suite for TextContent."""

    def test_text_content_creation(self):
        """Test TextContent creation with valid data."""
        content = TextContent(text="Hello, world!")

        assert content.type == "text"
        assert content.text == "Hello, world!"

    def test_text_content_validation(self):
        """Test TextContent validation."""
        # Should not raise any errors
        content = TextContent(text="Valid text content")

        assert content.text == "Valid text content"

    def test_text_content_empty_string(self):
        """Test TextContent with empty string."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TextContent(text="")

    def test_text_content_whitespace_validation(self):
        """Test TextContent whitespace validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TextContent(text="  Leading whitespace")

        with pytest.raises(ValidationError):
            TextContent(text="Trailing whitespace  ")


class TestHumanInputMessage:
    """Test suite for HumanInputMessage."""

    def test_human_input_message_creation(self):
        """Test HumanInputMessage creation with valid data."""
        message = HumanInputMessage(content="Hello, how can you help me?")

        assert message.content == "Hello, how can you help me?"
        assert message.role == "user"

    def test_human_input_message_validation(self):
        """Test HumanInputMessage validation."""
        # Should not raise any errors
        message = HumanInputMessage(content="Valid message content")

        assert message.content == "Valid message content"


class TestHumanOutputMessage:
    """Test suite for HumanOutputMessage."""

    def test_human_output_message_creation(self):
        """Test HumanOutputMessage creation with valid data."""
        content_blocks = [TextContent(text="I can help you with that!")]
        message = HumanOutputMessage(
            id="msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ", content=content_blocks
        )

        assert message.content == content_blocks
        assert message.role == "user"
        assert message.id == "msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ"

    def test_human_output_message_validation(self):
        """Test HumanOutputMessage validation."""
        content_blocks = [TextContent(text="Response")]
        message = HumanOutputMessage(
            id="msg_456789ABCDEFGHJKLMNPQRSTUVWXYZabcdef", content=content_blocks
        )

        assert message.content == content_blocks
        assert message.id == "msg_456789ABCDEFGHJKLMNPQRSTUVWXYZabcdef"


class TestAssistantOutputMessage:
    """Test suite for AssistantOutputMessage."""

    def test_assistant_output_message_creation(self):
        """Test AssistantOutputMessage creation with valid data."""
        content_blocks = [TextContent(text="I'll help you with that!")]
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        message = AssistantOutputMessage(
            id="msg_789ABCDEFGHJKLMNPQRSTUVWXYZabcdefgh",
            content=content_blocks,
            usage=usage,
        )

        assert message.content == content_blocks
        assert message.role == "assistant"
        assert message.id == "msg_789ABCDEFGHJKLMNPQRSTUVWXYZabcdefgh"
        assert message.usage == usage

    def test_assistant_output_message_with_tool_calls(self):
        """Test AssistantOutputMessage with tool calls."""
        content_blocks = [TextContent(text="I'll search for that")]
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        tool_calls = [ToolCall(id="call_1", name="search_api", args={"query": "test"})]
        message = AssistantOutputMessage(
            id="msg_123456789abcdefghijk",
            content=content_blocks,
            tool_calls=tool_calls,
            usage=usage,
        )

        assert len(message.tool_calls) == 1
        assert message.tool_calls[0].name == "search_api"
        assert message.id == "msg_123456789abcdefghijk"


class TestToolCall:
    """Test suite for ToolCall."""

    def test_tool_call_creation(self):
        """Test ToolCall creation with valid data."""
        tool_call = ToolCall(
            id="call_123", name="search_function", args={"query": "test query"}
        )

        assert tool_call.id == "call_123"
        assert tool_call.name == "search_function"
        assert tool_call.args == {"query": "test query"}

    def test_tool_call_validation(self):
        """Test ToolCall validation."""
        # Should not raise any errors
        tool_call = ToolCall(
            id="call_456", name="another_function", args={"param": "value"}
        )

        assert tool_call.id == "call_456"
        assert tool_call.name == "another_function"
        assert tool_call.args == {"param": "value"}


class TestToolCallDecision:
    """Test suite for ToolCallDecision."""

    def test_tool_call_decision_creation(self):
        """Test ToolCallDecision creation with valid data."""
        decision = ToolCallDecision(tool_call_id="call_123", decision="accept")

        assert decision.tool_call_id == "call_123"
        assert decision.decision == "accept"

    def test_tool_call_decision_validation(self):
        """Test ToolCallDecision validation."""
        # Should not raise any errors
        decision = ToolCallDecision(
            tool_call_id="call_456",
            decision="reject",
            message="This operation is not allowed",
        )

        assert decision.tool_call_id == "call_456"
        assert decision.decision == "reject"
        assert decision.message == "This operation is not allowed"


class TestMessageIntegration:
    """Test suite for message integration."""

    def test_message_type_hierarchy(self):
        """Test that message types follow proper hierarchy."""
        # Input messages
        human_input = HumanInputMessage(content="Hello")
        assert isinstance(human_input, InputMessage)

        # Output messages
        content_blocks = [TextContent(text="Hi")]
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        human_output = HumanOutputMessage(
            id="msg_hierarchy123456789abcdef", content=content_blocks
        )
        assistant_output = AssistantOutputMessage(
            id="msg_assistant123456789abcdef", content=content_blocks, usage=usage
        )

        assert isinstance(human_output, OutputMessage)
        assert isinstance(assistant_output, OutputMessage)

    def test_content_block_integration(self):
        """Test content block integration with messages."""
        content = TextContent(text="Test content")
        message = HumanInputMessage(content="Test content")

        # Both should work with the same content
        assert content.text == message.content
