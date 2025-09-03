"""
Unit tests for config module.

Tests cover ExecutionContext and ToolCallMetadata models
for tracking tool calls and metadata across the pipeline.
"""

import pytest
from pydantic import ValidationError

from nalai.config import ExecutionContext, ToolCallMetadata


class TestToolCallMetadata:
    """Test ToolCallMetadata model."""

    def test_valid_tool_call_metadata(self):
        """Test creating valid tool call metadata."""
        metadata = ToolCallMetadata(
            name="test_tool",
            args={"param1": "value1"},
            node="test_node",
        )

        assert metadata.name == "test_tool"
        assert metadata.args == {"param1": "value1"}
        assert metadata.node == "test_node"
        assert metadata.original_args is None

    def test_tool_call_metadata_defaults(self):
        """Test tool call metadata with default values."""
        metadata = ToolCallMetadata(name="test_tool")

        assert metadata.name == "test_tool"
        assert metadata.args == {}
        assert metadata.node is None
        assert metadata.original_args is None

    def test_tool_call_metadata_with_original_args(self):
        """Test tool call metadata with original args."""
        metadata = ToolCallMetadata(
            name="test_tool",
            args={"param1": "value1"},
            original_args={"param1": "original_value"},
        )

        assert metadata.original_args == {"param1": "original_value"}

    def test_tool_call_metadata_validation(self):
        """Test that tool call metadata validates required fields."""
        # Test that name is required
        with pytest.raises(ValidationError):
            ToolCallMetadata()


class TestExecutionContext:
    """Test ExecutionContext model."""

    def test_empty_execution_context(self):
        """Test creating empty execution context."""
        context = ExecutionContext()

        assert context.tool_calls == {}
        assert isinstance(context.tool_calls, dict)

    def test_execution_context_with_tool_calls(self):
        """Test execution context with tool calls."""
        tool_call_1 = ToolCallMetadata(name="tool1", args={"param": "value1"})
        tool_call_2 = ToolCallMetadata(name="tool2", args={"param": "value2"})

        context = ExecutionContext(
            tool_calls={"call_1": tool_call_1, "call_2": tool_call_2}
        )

        assert len(context.tool_calls) == 2
        assert context.tool_calls["call_1"].name == "tool1"
        assert context.tool_calls["call_2"].name == "tool2"

    def test_execution_context_extra_fields(self):
        """Test that execution context allows extra fields."""
        context = ExecutionContext(tool_calls={}, extra_field="extra_value")

        # Should not raise validation error due to extra="allow"
        assert hasattr(context, "extra_field")
        assert context.extra_field == "extra_value"


class TestExecutionContextIntegration:
    """Test integration between ExecutionContext and ToolCallMetadata."""

    def test_adding_tool_call_to_context(self):
        """Test adding tool call metadata to execution context."""
        context = ExecutionContext()

        # Add a tool call
        tool_call = ToolCallMetadata(
            name="http_get", args={"url": "https://api.example.com"}, status="pending"
        )

        context.tool_calls["call_123"] = tool_call

        assert "call_123" in context.tool_calls
        assert context.tool_calls["call_123"].name == "http_get"
        assert context.tool_calls["call_123"].args["url"] == "https://api.example.com"

    def test_updating_tool_call_args(self):
        """Test updating tool call args in execution context."""
        context = ExecutionContext()

        # Create initial tool call
        tool_call = ToolCallMetadata(
            name="http_get", args={"url": "https://api.example.com"}
        )

        context.tool_calls["call_123"] = tool_call

        # Update args
        context.tool_calls["call_123"].args = {
            "url": "https://api.example.com",
            "method": "GET",
        }

        assert context.tool_calls["call_123"].args["method"] == "GET"

    def test_tool_call_args_editing_integration(self):
        """Test tool call args editing integration with execution context."""
        context = ExecutionContext()

        # Initial tool call
        tool_call = ToolCallMetadata(
            name="http_post",
            args={"url": "https://api.example.com", "data": "original"},
        )

        context.tool_calls["call_456"] = tool_call

        # Simulate args editing - store original args and update current args
        context.tool_calls["call_456"].original_args = {
            "url": "https://api.example.com",
            "data": "original",
        }
        context.tool_calls["call_456"].args = {
            "url": "https://api.example.com",
            "data": "edited",
        }

        assert context.tool_calls["call_456"].original_args["data"] == "original"
        assert context.tool_calls["call_456"].args["data"] == "edited"
