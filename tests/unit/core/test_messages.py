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
    ToolCall,
    ToolCallDecision,
)


class TestContentBlocks:
    """Test suite for content block validation."""

    def test_text_content_block_creation(self):
        """Test text content block creation."""
        content = {"type": "text", "text": "Hello, world!"}

        # Text content blocks are valid but not validated by is_data_content_block
        # (that function only validates data content blocks like images, audio, files)
        assert content["type"] == "text"
        assert content["text"] == "Hello, world!"

    def test_image_url_content_block_creation(self):
        """Test image URL content block creation."""
        content = {
            "type": "image",
            "source_type": "url",
            "url": "https://example.com/image.jpg",
        }

        from langchain_core.messages.content_blocks import is_data_content_block

        assert is_data_content_block(content)

    def test_image_base64_content_block_creation(self):
        """Test image base64 content block creation."""
        content = {
            "type": "image",
            "source_type": "base64",
            "mime_type": "image/jpeg",
            "data": "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
        }

        from langchain_core.messages.content_blocks import is_data_content_block

        assert is_data_content_block(content)


class TestHumanInputMessage:
    """Test suite for HumanInputMessage."""

    def test_human_input_message_string_content(self):
        """Test HumanInputMessage creation with string content."""
        message = HumanInputMessage(content="Hello, how can you help me?")

        assert message.content == "Hello, how can you help me?"
        assert message.role == "user"
        assert message.text() == "Hello, how can you help me?"

    def test_human_input_message_content_blocks(self):
        """Test HumanInputMessage creation with content blocks."""
        content = [
            {"type": "text", "text": "Hello, how can you help me?"},
            {
                "type": "image",
                "source_type": "url",
                "url": "https://example.com/image.jpg",
            },
        ]
        message = HumanInputMessage(content=content)

        assert message.content == content
        assert message.role == "user"
        assert message.text() == "Hello, how can you help me?"

    def test_human_input_message_validation(self):
        """Test HumanInputMessage validation."""
        # Should not raise any errors
        message = HumanInputMessage(content="Valid message content")

        assert message.content == "Valid message content"

    def test_human_input_message_empty_content(self):
        """Test HumanInputMessage with empty content."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            HumanInputMessage(content="")

    def test_human_input_message_invalid_content_block(self):
        """Test HumanInputMessage with invalid content block."""
        from pydantic import ValidationError

        content = [{"type": "invalid", "data": "test"}]
        with pytest.raises(ValidationError):
            HumanInputMessage(content=content)


class TestHumanOutputMessage:
    """Test suite for HumanOutputMessage."""

    def test_human_output_message_string_content(self):
        """Test HumanOutputMessage creation with string content."""
        message = HumanOutputMessage(
            id="msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ",
            content="I can help you with that!",
        )

        assert message.content == "I can help you with that!"
        assert message.role == "user"
        assert message.id == "msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        assert message.text() == "I can help you with that!"

    def test_human_output_message_content_blocks(self):
        """Test HumanOutputMessage creation with content blocks."""
        content = [{"type": "text", "text": "I can help you with that!"}]
        message = HumanOutputMessage(
            id="msg_456789ABCDEFGHJKLMNPQRSTUVWXYZabcdef", content=content
        )

        assert message.content == content
        assert message.role == "user"
        assert message.id == "msg_456789ABCDEFGHJKLMNPQRSTUVWXYZabcdef"
        assert message.text() == "I can help you with that!"


class TestAssistantOutputMessage:
    """Test suite for AssistantOutputMessage."""

    def test_assistant_output_message_string_content(self):
        """Test AssistantOutputMessage creation with string content."""
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        message = AssistantOutputMessage(
            id="msg_789ABCDEFGHJKLMNPQRSTUVWXYZabcdefgh",
            content="I'll help you with that!",
            usage=usage,
        )

        assert message.content == "I'll help you with that!"
        assert message.role == "assistant"
        assert message.id == "msg_789ABCDEFGHJKLMNPQRSTUVWXYZabcdefgh"
        assert message.usage == usage
        assert message.text() == "I'll help you with that!"

    def test_assistant_output_message_content_blocks(self):
        """Test AssistantOutputMessage creation with content blocks."""
        content = [{"type": "text", "text": "I'll help you with that!"}]
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        message = AssistantOutputMessage(
            id="msg_789ABCDEFGHJKLMNPQRSTUVWXYZabcdefgh",
            content=content,
            usage=usage,
        )

        assert message.content == content
        assert message.role == "assistant"
        assert message.id == "msg_789ABCDEFGHJKLMNPQRSTUVWXYZabcdefgh"
        assert message.usage == usage
        assert message.text() == "I'll help you with that!"

    def test_assistant_output_message_with_tool_calls(self):
        """Test AssistantOutputMessage with tool calls."""
        content = [{"type": "text", "text": "I'll search for that"}]
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        tool_calls = [
            ToolCall(
                id="call_123",
                name="search",
                args={"query": "test query"},
            )
        ]
        message = AssistantOutputMessage(
            id="msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ",
            content=content,
            usage=usage,
            tool_calls=tool_calls,
        )

        assert message.content == content
        assert message.tool_calls == tool_calls
        assert message.text() == "I'll search for that"


class TestToolCallDecision:
    """Test suite for ToolCallDecision."""

    def test_tool_call_decision_accept(self):
        """Test ToolCallDecision with accept decision."""
        decision = ToolCallDecision(
            tool_call_id="call_123",
            decision="accept",
        )

        assert decision.tool_call_id == "call_123"
        assert decision.decision == "accept"
        assert decision.args is None
        assert decision.message is None

    def test_tool_call_decision_feedback(self):
        """Test ToolCallDecision with feedback decision."""
        decision = ToolCallDecision(
            tool_call_id="call_123",
            decision="feedback",
            message="Please provide more details",
        )

        assert decision.tool_call_id == "call_123"
        assert decision.decision == "feedback"
        assert decision.message == "Please provide more details"
        assert decision.args is None

    def test_tool_call_decision_edit(self):
        """Test ToolCallDecision with edit decision."""
        decision = ToolCallDecision(
            tool_call_id="call_123",
            decision="edit",
            args={"query": "updated query"},
        )

        assert decision.tool_call_id == "call_123"
        assert decision.decision == "edit"
        assert decision.args == {"query": "updated query"}
        assert decision.message is None

    def test_tool_call_decision_reject(self):
        """Test ToolCallDecision with reject decision."""
        decision = ToolCallDecision(
            tool_call_id="call_123",
            decision="reject",
            message="This tool call is not appropriate",
        )

        assert decision.tool_call_id == "call_123"
        assert decision.decision == "reject"
        assert decision.message == "This tool call is not appropriate"
        assert decision.args is None


class TestToolCall:
    """Test suite for ToolCall."""

    def test_tool_call_creation(self):
        """Test ToolCall creation with valid data."""
        tool_call = ToolCall(
            id="call_123",
            name="search",
            args={"query": "test query"},
        )

        assert tool_call.id == "call_123"
        assert tool_call.name == "search"
        assert tool_call.args == {"query": "test query"}

    def test_tool_call_validation(self):
        """Test ToolCall validation."""
        # Should not raise any errors
        tool_call = ToolCall(
            id="call_456",
            name="get_weather",
            args={"location": "New York"},
        )

        assert tool_call.id == "call_456"
        assert tool_call.name == "get_weather"
        assert tool_call.args == {"location": "New York"}


class TestTextExtraction:
    """Test suite for text extraction functionality."""

    def test_text_extraction_string_content(self):
        """Test text extraction from string content."""
        message = HumanOutputMessage(
            id="msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ", content="Hello world"
        )

        assert message.text() == "Hello world"

    def test_text_extraction_content_blocks(self):
        """Test text extraction from content blocks."""
        content = [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world"},
        ]
        message = HumanOutputMessage(
            id="msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ", content=content
        )

        assert message.text() == "Hello world"

    def test_text_extraction_mixed_content(self):
        """Test text extraction from mixed content blocks."""
        content = [
            "Hello ",
            {"type": "text", "text": "world"},
            {
                "type": "image",
                "source_type": "url",
                "url": "https://example.com/image.jpg",
            },
        ]
        message = HumanOutputMessage(
            id="msg_123456789ABCDEFGHJKLMNPQRSTUVWXYZ", content=content
        )

        assert message.text() == "Hello world"
