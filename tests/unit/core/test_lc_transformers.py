"""
Tests for core lc_transformers module - critical path functionality.
"""

from unittest.mock import Mock

import pytest

from nalai.core.lc_transformers import transform_message, transform_streaming_chunk


class TestLCTransformers:
    """Test critical LangChain transformers functionality."""

    @pytest.mark.parametrize(
        "message_type,content,expected_type",
        [
            ("HumanMessage", "Hello", "human"),
            ("AIMessage", "Hi there!", "ai"),
            ("ToolMessage", "Tool result", "tool"),
        ],
    )
    def test_transform_message_types(self, message_type, content, expected_type):
        """Test message transformation for different message types."""
        mock_message = Mock()
        mock_message.content = content
        mock_message.__class__.__name__ = message_type

        # Add required attributes to prevent errors
        mock_message.tool_calls = []
        mock_message.invalid_tool_calls = []
        mock_message.response_metadata = {}
        mock_message.usage = {}
        mock_message.finish_reason = None
        mock_message.tool_call_id = None
        mock_message.tool_call_chunks = []

        result = transform_message(mock_message)
        assert result.type == expected_type
        assert result.content == content

    def test_transform_streaming_chunk_function_exists(self):
        """Test that transform_streaming_chunk function exists."""
        assert callable(transform_streaming_chunk)
