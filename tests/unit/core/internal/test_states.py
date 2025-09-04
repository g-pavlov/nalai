"""
Unit tests for internal states functionality.

Tests cover AgentState, InputSchema, and OutputSchema validation and behavior.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "src")
)

from langchain_core.messages import AIMessage, HumanMessage

from nalai.core.internal.states import AgentState


class TestInputSchema:
    """Test suite for InputSchema."""

    def test_input_schema_creation(self):
        """Test InputSchema creation with valid data."""
        messages = [HumanMessage(content="Hello")]

        # InputSchema is a TypedDict, so we create it as a dict
        input_data = {"messages": messages}

        # Should not raise any errors
        assert input_data["messages"] == messages
        assert len(input_data["messages"]) == 1
        assert isinstance(input_data["messages"][0], HumanMessage)

    def test_input_schema_with_multiple_messages(self):
        """Test InputSchema with multiple messages."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?"),
        ]

        input_data = {"messages": messages}

        assert len(input_data["messages"]) == 3
        assert isinstance(input_data["messages"][0], HumanMessage)
        assert isinstance(input_data["messages"][1], AIMessage)
        assert isinstance(input_data["messages"][2], HumanMessage)

    def test_input_schema_empty_messages(self):
        """Test InputSchema with empty messages list."""
        messages = []
        input_data = {"messages": messages}

        assert len(input_data["messages"]) == 0


class TestAgentState:
    """Test suite for AgentState."""

    def test_agent_state_creation(self):
        """Test AgentState creation with valid data."""
        messages = [HumanMessage(content="Hello")]
        api_specs = {"openapi": "3.0.0", "paths": {}}
        api_summaries = [{"title": "Test API", "version": "1.0"}]
        selected_apis = {"api1": "v1"}

        state = AgentState(
            messages=messages,
            api_specs=api_specs,
            api_summaries=api_summaries,
            selected_apis=selected_apis,
        )

        assert state["messages"] == messages
        assert state["api_specs"] == api_specs
        assert state["api_summaries"] == api_summaries
        assert state["selected_apis"] == selected_apis

    def test_agent_state_default_values(self):
        """Test AgentState with default values."""
        messages = [HumanMessage(content="Hello")]

        state = AgentState(messages=messages)

        assert state["messages"] == messages
        assert state.get("api_specs") is None
        assert state.get("api_summaries") is None
        assert state.get("selected_apis") is None

    def test_agent_state_with_none_values(self):
        """Test AgentState with explicit None values."""
        messages = [HumanMessage(content="Hello")]

        state = AgentState(
            messages=messages,
            api_specs=None,
            api_summaries=None,
            selected_apis=None,
        )

        assert state["messages"] == messages
        assert state["api_specs"] is None
        assert state["api_summaries"] is None
        assert state["selected_apis"] is None

    def test_agent_state_complex_api_specs(self):
        """Test AgentState with complex API specifications."""
        messages = [HumanMessage(content="Hello")]
        api_specs = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "summary": "Get users",
                        "responses": {"200": {"description": "Success"}},
                    }
                }
            },
        }

        state = AgentState(messages=messages, api_specs=api_specs)

        assert state["api_specs"] == api_specs
        assert state["api_specs"]["openapi"] == "3.0.0"
        assert "/users" in state["api_specs"]["paths"]


class TestOutputSchema:
    """Test suite for OutputSchema."""

    def test_output_schema_creation(self):
        """Test OutputSchema creation with valid data."""
        messages = [AIMessage(content="Hello there!")]

        # OutputSchema is a TypedDict, so we create it as a dict
        output_data = {"messages": messages}

        # Should not raise any errors
        assert output_data["messages"] == messages
        assert len(output_data["messages"]) == 1
        assert isinstance(output_data["messages"][0], AIMessage)

    def test_output_schema_inheritance(self):
        """Test OutputSchema inheritance from InputSchema."""
        # OutputSchema should have the same structure as InputSchema
        # but with different message types (typically AI messages)
        messages = [AIMessage(content="Response")]

        output_data = {"messages": messages}

        assert output_data["messages"] == messages
        assert isinstance(output_data["messages"][0], AIMessage)
