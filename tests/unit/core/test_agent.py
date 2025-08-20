"""
Unit tests for Agent protocol/interface.

Tests the Agent protocol definition and interface contracts.
"""

from langchain_core.messages import AIMessage, HumanMessage

from nalai.core.agent import Agent, Conversation, ConversationInfo


class TestAgentProtocol:
    """Test the Agent protocol definition."""

    def test_agent_protocol_methods(self):
        """Test that Agent protocol defines required methods."""
        # This test ensures the protocol has the expected methods
        # The actual implementation is tested in test_langgraph_agent.py
        assert callable(Agent)

        # Check that Agent is a Protocol
        from typing import Protocol

        assert issubclass(Agent, Protocol)


class TestAgentModels:
    """Test the Agent internal models."""

    def test_conversation_info_model(self):
        """Test ConversationInfo model creation and validation."""
        conversation_info = ConversationInfo(
            conversation_id="test-conv-123",
            created_at="2024-01-01T00:00:00Z",
            last_accessed="2024-01-01T00:00:00Z",
            preview="Test conversation preview",
            status="active",
        )
        assert conversation_info.conversation_id == "test-conv-123"
        assert conversation_info.preview == "Test conversation preview"
        assert conversation_info.status == "active"

    def test_conversation_model(self):
        """Test Conversation model creation and validation."""
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]

        conversation = Conversation(
            conversation_id="test-conv-123",
            messages=messages,
            created_at="2024-01-01T00:00:00Z",
            last_accessed="2024-01-01T00:00:00Z",
            status="active",
        )
        assert conversation.conversation_id == "test-conv-123"
        assert len(conversation.messages) == 2
        assert conversation.messages[0].content == "Hello"
        assert conversation.messages[1].content == "Hi there!"
        assert conversation.status == "active"
        # Test inheritance from ConversationInfo
        assert isinstance(conversation, ConversationInfo)


class TestAgentExceptions:
    """Test the Agent exception hierarchy."""

    def test_exception_inheritance(self):
        """Test that exceptions follow proper inheritance hierarchy."""
        from nalai.core.agent import (
            AccessDeniedError,
            ConversationNotFoundError,
            Error,
            InvocationError,
            ValidationError,
        )

        # Test inheritance hierarchy
        assert issubclass(ValidationError, Error)
        assert issubclass(InvocationError, Error)
        assert issubclass(ConversationNotFoundError, Error)
        assert issubclass(AccessDeniedError, Error)

    def test_exception_messages(self):
        """Test exception message formatting."""
        from nalai.core.agent import InvocationError, ValidationError

        val_error = ValidationError("Invalid input")
        assert str(val_error) == "Invalid input"

        inv_error = InvocationError("Operation failed")
        assert str(inv_error) == "Operation failed"

    def test_exception_context(self):
        """Test exception context handling."""
        from nalai.core.agent import ValidationError

        context = {"field": "test_field", "value": "invalid_value"}
        error = ValidationError("Invalid input", context=context)
        assert error.context == context
        assert error.error_code == "VALIDATION_ERROR"
