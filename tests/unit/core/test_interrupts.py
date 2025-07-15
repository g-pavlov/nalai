"""
Unit tests for interrupt functionality.

Tests cover human review processing, interrupt handling, and workflow
command generation for different action types.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

import logging

from api_assistant.core.constants import NODE_CALL_API, NODE_CALL_MODEL
from api_assistant.core.interrupts import ABORT_MESSAGE, process_human_review


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return MagicMock(
        get=lambda key, default=None: {
            "configurable": {
                "thread_id": "test_thread",
                "org_unit_id": "test_org",
                "user_email": "test@example.com",
            }
        }
    )


@pytest.fixture
def mock_tool_call():
    """Create a mock tool call for testing."""
    return {
        "id": "call_123",
        "name": "get_http_requests",
        "args": {"method": "GET", "url": "https://api.example.com/users"},
        "type": "tool_call",
    }


@pytest.fixture
def mock_ai_message(mock_tool_call):
    """Create a mock AI message with tool calls."""
    return AIMessage(
        content="Here is a tool call", id="ai-msg-123", tool_calls=[mock_tool_call]
    )


@pytest.fixture
def mock_state(mock_ai_message):
    """Create a mock state with AI message."""
    return {"messages": [mock_ai_message]}


class TestProcessHumanReview:
    """Test suite for human review processing."""

    @patch("api_assistant.core.interrupts.interrupt")
    def test_continue_action(
        self, mock_interrupt, mock_state, mock_config, mock_tool_call
    ):
        """Test continue action processing."""
        mock_interrupt.return_value = {"action": "continue"}

        result = process_human_review(mock_state, mock_config)

        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_API
        assert result.update == {}

        # Verify interrupt was called with correct parameters
        mock_interrupt.assert_called_once()
        call_args = mock_interrupt.call_args[0]
        expected_interrupt_data = {
            "question": "Is this correct?",
            "tool_call": mock_tool_call,
        }
        assert call_args[0] == expected_interrupt_data

    @patch("api_assistant.core.interrupts.interrupt")
    def test_abort_action(
        self, mock_interrupt, mock_state, mock_config, mock_tool_call
    ):
        """Test abort action processing."""
        mock_interrupt.return_value = {"action": "abort"}

        result = process_human_review(mock_state, mock_config)

        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_MODEL
        assert "messages" in result.update

        # Verify tool message was added
        messages = result.update["messages"]
        assert len(messages) == 2

        tool_msg = messages[0]
        assert isinstance(tool_msg, ToolMessage)
        assert tool_msg.tool_call_id == mock_tool_call["id"]
        assert tool_msg.content == ABORT_MESSAGE

    @patch("api_assistant.core.interrupts.interrupt")
    def test_update_action(
        self, mock_interrupt, mock_state, mock_config, mock_tool_call
    ):
        """Test update action processing."""
        updated_args = {"method": "POST", "url": "https://api.example.com/users"}
        mock_interrupt.return_value = {"action": "update", "data": updated_args}

        result = process_human_review(mock_state, mock_config)

        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_API
        assert "messages" in result.update

        # Verify message was updated
        messages = result.update["messages"]
        assert len(messages) == 1

        updated_msg = messages[0]
        assert updated_msg["id"] == mock_state["messages"][0].id
        assert updated_msg["tool_calls"][0]["args"] == updated_args

    @patch("api_assistant.core.interrupts.interrupt")
    def test_feedback_action(
        self, mock_interrupt, mock_state, mock_config, mock_tool_call
    ):
        """Test feedback action processing."""
        feedback_message = "Incorrect call, try again."
        mock_interrupt.return_value = {"action": "feedback", "data": feedback_message}

        result = process_human_review(mock_state, mock_config)

        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_MODEL
        assert "messages" in result.update

        # Verify feedback message was added
        messages = result.update["messages"]
        assert len(messages) == 1

        tool_msg = messages[0]
        assert isinstance(tool_msg, ToolMessage)
        assert tool_msg.tool_call_id == mock_tool_call["id"]
        assert tool_msg.content == feedback_message

    @patch("api_assistant.core.interrupts.interrupt")
    def test_unknown_action(self, mock_interrupt, mock_state, mock_config):
        """Test handling of unknown action - should default to continue."""
        mock_interrupt.return_value = {"action": "unknown_action"}

        result = process_human_review(mock_state, mock_config)

        # Should not raise exception, but default to continue action
        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_API
        assert result.update == {}

    @patch("api_assistant.core.interrupts.interrupt")
    def test_unknown_action_logging(
        self, mock_interrupt, mock_state, mock_config, caplog
    ):
        """Test that unknown actions are logged as warnings."""
        mock_interrupt.return_value = {"action": "unknown_action"}

        with caplog.at_level(logging.WARNING):
            result = process_human_review(mock_state, mock_config)

        # Verify warning was logged
        warning_found = any(
            "unknown review action" in record.message.lower()
            and record.levelname == "WARNING"
            for record in caplog.records
        )
        assert warning_found, (
            f"No warning found for unknown action. Log records: {[r.message for r in caplog.records]}"
        )

        # Should still return continue action
        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_API

    def test_no_ai_message(self, mock_config):
        """Test error when no AI message is found."""
        state = {"messages": [HumanMessage(content="Hi")]}

        with pytest.raises(ValueError, match="No AIMessage found"):
            process_human_review(state, mock_config)

    def test_no_tool_calls(self, mock_config):
        """Test handling when AI message has no tool calls."""
        ai_message = AIMessage(content="No tool calls here")
        state = {"messages": [ai_message]}

        result = process_human_review(state, mock_config)

        # Should return to model when no tool calls to review
        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_MODEL
        assert result.update == {}

    def test_empty_messages(self, mock_config):
        """Test error when messages list is empty."""
        state = {"messages": []}

        with pytest.raises(ValueError, match="No AIMessage found"):
            process_human_review(state, mock_config)

    @patch("api_assistant.core.interrupts.interrupt")
    def test_multiple_tool_calls(self, mock_interrupt, mock_state, mock_config):
        """Test processing with multiple tool calls."""
        # Create AI message with multiple tool calls
        tool_calls = [
            {
                "id": "call_1",
                "name": "get_http_requests",
                "args": {"method": "GET", "url": "https://api.example.com/users"},
            },
            {
                "id": "call_2",
                "name": "post_http_requests",
                "args": {"method": "POST", "url": "https://api.example.com/users"},
            },
        ]

        ai_message = AIMessage(
            content="Multiple tool calls", id="ai-msg-456", tool_calls=tool_calls
        )
        state = {"messages": [ai_message]}

        mock_interrupt.return_value = {"action": "continue"}

        result = process_human_review(state, mock_config)

        assert isinstance(result, Command)
        assert result.goto == NODE_CALL_API

    @patch("api_assistant.core.interrupts.interrupt")
    def test_interrupt_error_handling(self, mock_interrupt, mock_state, mock_config):
        """Test error handling when interrupt function fails."""
        mock_interrupt.side_effect = Exception("Interrupt failed")

        with pytest.raises(Exception, match="Interrupt failed"):
            process_human_review(mock_state, mock_config)

    @patch("api_assistant.core.interrupts.interrupt")
    def test_config_extraction(self, mock_interrupt, mock_state, mock_config):
        """Test that configuration is properly extracted and passed."""
        mock_interrupt.return_value = {"action": "continue"}

        # Create config with specific values
        config = MagicMock()
        config.get.return_value = {
            "configurable": {
                "thread_id": "test-thread-123",
                "org_unit_id": "test-org-456",
                "user_email": "test@example.com",
            }
        }

        process_human_review(mock_state, config)

        # Verify interrupt was called with correct data structure
        mock_interrupt.assert_called_once()
        call_args = mock_interrupt.call_args[0]
        expected_interrupt_data = {
            "question": "Is this correct?",
            "tool_call": mock_state["messages"][0].tool_calls[-1],
        }
        assert call_args[0] == expected_interrupt_data

    @patch("api_assistant.core.interrupts.interrupt")
    def test_state_preservation(self, mock_interrupt, mock_state, mock_config):
        """Test that state is properly preserved and passed."""
        mock_interrupt.return_value = {"action": "continue"}

        result = process_human_review(mock_state, mock_config)

        # Verify interrupt was called with correct data structure
        mock_interrupt.assert_called_once()
        call_args = mock_interrupt.call_args[0]
        expected_interrupt_data = {
            "question": "Is this correct?",
            "tool_call": mock_state["messages"][0].tool_calls[-1],
        }
        assert call_args[0] == expected_interrupt_data

        # Verify state is not modified for continue action
        assert result.update == {}

    @patch("api_assistant.core.interrupts.interrupt")
    def test_tool_message_creation(
        self, mock_interrupt, mock_state, mock_config, mock_tool_call
    ):
        """Test proper tool message creation for different actions."""
        # Test abort action
        mock_interrupt.return_value = {"action": "abort"}
        result = process_human_review(mock_state, mock_config)

        tool_msg = result.update["messages"][0]
        assert isinstance(tool_msg, ToolMessage)
        assert tool_msg.tool_call_id == mock_tool_call["id"]
        assert tool_msg.content is not None

        # Test feedback action
        feedback = "Try a different approach"
        mock_interrupt.return_value = {"action": "feedback", "data": feedback}
        result = process_human_review(mock_state, mock_config)

        tool_msg = result.update["messages"][0]
        assert isinstance(tool_msg, ToolMessage)
        assert tool_msg.tool_call_id == mock_tool_call["id"]
        assert tool_msg.content == feedback
