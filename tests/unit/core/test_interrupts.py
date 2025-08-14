"""
Unit tests for interrupt functionality.

Tests cover human review logging, human-in-the-loop tool wrapping, and
interrupt detection from workflow state.
"""

import os
import sys
from unittest.mock import patch

import pytest
from langchain_core.tools import BaseTool
from langgraph.prebuilt.interrupt import HumanInterruptConfig

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
        "id": "call_123",
        "name": "get_http_requests",
        "args": {"method": "GET", "url": "https://api.example.com/users"},
        "type": "tool_call",
    }


class TestLogHumanReviewAction:
    """Test suite for human review action logging."""

    @patch("nalai.core.interrupts.logger")
    def test_log_human_review_action_success(
        self, mock_logger, mock_config, mock_tool_call
    ):
        """Test successful logging of human review action."""
        log_human_review_action("continue", mock_config, mock_tool_call)

        # Verify logger was called
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]

        # Verify key information is in the log message
        assert "continue" in log_message
        assert "test_thread" in log_message
        assert "test_***_org" in log_message  # PII masking replaces org_unit_id
        assert "get_http_requests" in log_message

    @patch("nalai.core.interrupts.logger")
    def test_log_human_review_action_with_none_config(
        self, mock_logger, mock_tool_call
    ):
        """Test logging with None config."""
        log_human_review_action("abort", None, mock_tool_call)

        # Verify logger was called with unknown values
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "unknown" in log_message

    @patch("nalai.core.interrupts.logger")
    def test_log_human_review_action_with_missing_configurable(
        self, mock_logger, mock_tool_call
    ):
        """Test logging with config missing configurable section."""
        config = {"other_section": "value"}
        log_human_review_action("update", config, mock_tool_call)

        # Verify logger was called with unknown values
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "unknown" in log_message


class TestAddHumanInTheLoop:
    """Test suite for human-in-the-loop tool wrapping."""

    def test_add_human_in_the_loop_with_function(self):
        """Test wrapping a function with human-in-the-loop."""

        def test_function(x: int) -> int:
            """Test function that doubles the input."""
            return x * 2

        wrapped_tool = add_human_in_the_loop(test_function)

        assert isinstance(wrapped_tool, BaseTool)
        assert wrapped_tool.name == "test_function"

    def test_add_human_in_the_loop_with_base_tool(self):
        """Test wrapping a BaseTool with human-in-the-loop."""
        from langchain_core.tools import tool

        @tool
        def test_tool(x: int) -> int:
            """A test tool that doubles the input."""
            return x * 2

        wrapped_tool = add_human_in_the_loop(test_tool)

        assert isinstance(wrapped_tool, BaseTool)
        assert wrapped_tool.name == "test_tool"

    def test_add_human_in_the_loop_with_custom_config(self):
        """Test wrapping with custom interrupt configuration."""

        def test_function(x: int) -> int:
            """Test function that doubles the input."""
            return x * 2

        custom_config: HumanInterruptConfig = {
            "allow_accept": True,
            "allow_edit": False,
            "allow_respond": True,
        }

        wrapped_tool = add_human_in_the_loop(
            test_function, interrupt_config=custom_config
        )

        assert isinstance(wrapped_tool, BaseTool)
