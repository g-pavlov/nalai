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
            status="pending",
            node="test_node",
        )

        assert metadata.name == "test_tool"
        assert metadata.args == {"param1": "value1"}
        assert metadata.status == "pending"
        assert metadata.node == "test_node"
        assert metadata.interrupt_decision is None
        assert metadata.user_edited_args is None

    def test_tool_call_metadata_defaults(self):
        """Test tool call metadata with default values."""
        metadata = ToolCallMetadata(name="test_tool")

        assert metadata.name == "test_tool"
        assert metadata.args == {}
        assert metadata.status == "pending"
        assert metadata.node is None
        assert metadata.interrupt_decision is None
        assert metadata.user_edited_args is None

    def test_tool_call_metadata_with_interrupt(self):
        """Test tool call metadata with interrupt decision."""
        metadata = ToolCallMetadata(
            name="test_tool",
            args={"param1": "value1"},
            status="running",
            interrupt_decision="accept",
            user_edited_args={"param1": "edited_value"},
        )

        assert metadata.interrupt_decision == "accept"
        assert metadata.user_edited_args == {"param1": "edited_value"}

    def test_invalid_status(self):
        """Test that invalid status raises validation error."""
        with pytest.raises(ValidationError):
            ToolCallMetadata(name="test_tool", status="invalid_status")

    def test_invalid_interrupt_decision(self):
        """Test that invalid interrupt decision raises validation error."""
        with pytest.raises(ValidationError):
            ToolCallMetadata(name="test_tool", interrupt_decision="invalid_decision")


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

    def test_updating_tool_call_status(self):
        """Test updating tool call status in execution context."""
        context = ExecutionContext()

        # Create initial tool call
        tool_call = ToolCallMetadata(
            name="http_get", args={"url": "https://api.example.com"}, status="pending"
        )

        context.tool_calls["call_123"] = tool_call

        # Update status
        context.tool_calls["call_123"].status = "running"

        assert context.tool_calls["call_123"].status == "running"

    def test_interrupt_flow_integration(self):
        """Test interrupt flow integration with execution context."""
        context = ExecutionContext()

        # Initial tool call
        tool_call = ToolCallMetadata(
            name="http_post",
            args={"url": "https://api.example.com", "data": "original"},
            status="pending",
        )

        context.tool_calls["call_456"] = tool_call

        # Simulate user edit decision
        context.tool_calls["call_456"].interrupt_decision = "edit"
        context.tool_calls["call_456"].user_edited_args = {
            "url": "https://api.example.com",
            "data": "edited",
        }
        context.tool_calls["call_456"].args = {
            "url": "https://api.example.com",
            "data": "edited",
        }
        context.tool_calls["call_456"].status = "running"

        assert context.tool_calls["call_456"].interrupt_decision == "edit"
        assert context.tool_calls["call_456"].user_edited_args["data"] == "edited"
        assert context.tool_calls["call_456"].args["data"] == "edited"
        assert context.tool_calls["call_456"].status == "running"
