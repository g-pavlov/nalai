"""
Unit tests for interrupt functionality.

Tests cover human review logging, human-in-the-loop tool wrapping, and
interrupt detection from workflow state.
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.core.interrupts import (
    add_human_in_the_loop,
    log_human_review_action,
)


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return {
        "configurable": {
            "thread_id": "test_thread",
            "org_unit_id": "test_org",
            "user_id": "test_user",
        }
    }


@pytest.fixture
def mock_tool_call():
    """Create a mock tool call for testing."""
    return {
        "name": "test_tool",
        "args": {"param1": "value1"},
        "description": "Test tool call",
    }


class TestLogHumanReviewAction:
    """Test human review action logging."""

    @patch("nalai.core.interrupts.logger")
    def test_log_human_review_action_with_user_scoped_thread_id(self, mock_logger):
        """Test logging with user-scoped thread ID."""
        config = {
            "configurable": {
                "thread_id": "user:test_user:550e8400-e29b-41d4-a716-446655440000",
                "org_unit_id": "test_org",
                "user_id": "test_user",
            }
        }
        tool_call = {"name": "test_tool", "args": {"param": "value"}}

        log_human_review_action("accept", config, tool_call)

        # Verify that the base UUID is extracted and logged
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "550e8400-e29b-41d4-a716-446655440000" in log_message
        assert "user:test_user:550e8400-e29b-41d4-a716-446655440000" not in log_message

    @patch("nalai.core.interrupts.logger")
    def test_log_human_review_action_with_base_uuid(self, mock_logger):
        """Test logging with base UUID thread ID."""
        config = {
            "configurable": {
                "thread_id": "550e8400-e29b-41d4-a716-446655440000",
                "org_unit_id": "test_org",
                "user_id": "test_user",
            }
        }
        tool_call = {"name": "test_tool", "args": {"param": "value"}}

        log_human_review_action("accept", config, tool_call)

        # Verify that the base UUID is logged as-is
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "550e8400-e29b-41d4-a716-446655440000" in log_message

    @patch("nalai.core.interrupts.logger")
    def test_log_human_review_action_with_invalid_user_scoped_id(self, mock_logger):
        """Test logging with invalid user-scoped thread ID format."""
        config = {
            "configurable": {
                "thread_id": "user:invalid_format",
                "org_unit_id": "test_org",
                "user_id": "test_user",
            }
        }
        tool_call = {"name": "test_tool", "args": {"param": "value"}}

        log_human_review_action("accept", config, tool_call)

        # Verify warning is logged for invalid format
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid user-scoped thread_id format" in warning_message

        # Verify info is still logged with original thread_id
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "user:invalid_format" in log_message

    @patch("nalai.core.interrupts.logger")
    def test_log_human_review_action_with_unknown_thread_id(self, mock_logger):
        """Test logging with unknown thread ID."""
        config = {
            "configurable": {
                "thread_id": "unknown",
                "org_unit_id": "test_org",
                "user_id": "test_user",
            }
        }
        tool_call = {"name": "test_tool", "args": {"param": "value"}}

        log_human_review_action("accept", config, tool_call)

        # Verify that "unknown" is logged as-is
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "threadId: unknown" in log_message


class TestAddHumanInTheLoop:
    """Test human-in-the-loop tool wrapping."""

    def test_add_human_in_the_loop_with_callable(self):
        """Test wrapping a callable with human-in-the-loop."""

        def test_tool(param: str) -> str:
            """Test tool that returns a result."""
            return f"Result: {param}"

        wrapped_tool = add_human_in_the_loop(test_tool)

        assert wrapped_tool.name == "test_tool"
        assert wrapped_tool.description is not None

    def test_add_human_in_the_loop_with_base_tool(self):
        """Test wrapping a BaseTool with human-in-the-loop."""
        from langchain_core.tools import tool

        @tool
        def test_tool(x: str) -> str:
            """Test tool that returns a result."""
            return f"Result: {x}"

        wrapped_tool = add_human_in_the_loop(test_tool)

        assert wrapped_tool.name == "test_tool"
        assert wrapped_tool.description == "Test tool that returns a result."

    def test_add_human_in_the_loop_with_custom_config(self):
        """Test wrapping with custom interrupt configuration."""

        def test_tool(param: str) -> str:
            """Test tool that returns a result."""
            return f"Result: {param}"

        custom_config = {
            "allow_accept": True,
            "allow_edit": False,
            "allow_respond": True,
        }

        wrapped_tool = add_human_in_the_loop(test_tool, interrupt_config=custom_config)

        assert wrapped_tool.name == "test_tool"
