"""
Tests for core states module - critical path functionality.
"""

import pytest

from nalai.core.states import AgentState, InputSchema, OutputSchema


class TestStates:
    """Test critical State functionality."""

    @pytest.mark.parametrize(
        "state_class,initial_data,expected_attrs",
        [
            (InputSchema, {"messages": []}, {"messages": []}),
            (
                AgentState,
                {"messages": [], "api_specs": None},
                {"messages": [], "api_specs": None},
            ),
            (OutputSchema, {"messages": []}, {"messages": []}),
        ],
    )
    def test_state_creation_and_access(self, state_class, initial_data, expected_attrs):
        """Test state creation and attribute access with various data types."""
        state = state_class(**initial_data)

        for key, expected_value in expected_attrs.items():
            assert state[key] == expected_value

    def test_agent_state_with_api_data(self):
        """Test AgentState with API-related data."""
        messages = [{"type": "human", "content": "Hello"}]
        api_specs = [{"openapi": "3.0.0"}]
        selected_apis = {"api1": "v1"}

        state = AgentState(
            messages=messages, api_specs=api_specs, selected_apis=selected_apis
        )

        assert state["messages"] == messages
        assert state["api_specs"] == api_specs
        assert state["selected_apis"] == selected_apis
