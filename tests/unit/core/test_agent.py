"""
Unit tests for APIAssistant core agent functionality.

Tests cover agent initialization, response parsing, template formatting,
API selection, workflow actions, and model response generation.
"""

import os
import sys
import json
import logging
from unittest.mock import ANY, MagicMock, mock_open, patch

import pytest
import yaml
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from api_assistant.core.agent import APIAssistant
from api_assistant.core.constants import (
    NODE_CALL_API,
    NODE_CALL_MODEL,
    NODE_HUMAN_REVIEW,
    NODE_LOAD_API_SPECS,
    NODE_SELECT_RELEVANT_APIS,
)
from api_assistant.core.schemas import AgentState, SelectApi, SelectedApis
from api_assistant.prompts.prompts import format_template_with_variables
from api_assistant.services.model_service import ModelService


@pytest.fixture
def assistant():
    """Create a fresh APIAssistant instance for each test."""
    return APIAssistant()


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return RunnableConfig(
        configurable={
            "thread_id": "test-thread",
            "model": "test-model",
            "org_unit_id": "test-org",
            "user_email": "test@example.com",
        }
    )


@pytest.fixture
def test_data():
    """Load test data from YAML file."""
    test_data_path = os.path.join(
        os.path.dirname(__file__), "..", "test_data", "agent_test_cases.yaml"
    )
    with open(test_data_path) as f:
        return yaml.safe_load(f)


class TestAPIAssistant:
    """Test cases for APIAssistant functionality."""

    def test_agent_initialization(self, assistant):
        """Test agent initialization."""
        assert assistant.http_toolkit is not None

    @pytest.mark.parametrize(
        "test_case", ["simple_replacement", "multiple_replacements", "no_variables"]
    )
    def test_format_template_with_variables(self, test_case, test_data):
        """Test template variable formatting."""
        case_data = next(
            c
            for c in test_data["format_template_with_variables"]
            if c["name"] == test_case
        )

        result = format_template_with_variables(
            case_data["input"]["template"], **case_data["input"]["variables"]
        )
        assert result == case_data["expected"]

    @patch.object(ModelService, "get_model_id_from_config")
    @patch("api_assistant.core.agent.load_prompt_template")
    @patch.object(ModelService, "get_model_from_config")
    def test_create_prompt_and_model(
        self,
        mock_get_model,
        mock_load_prompt,
        mock_get_model_id,
        assistant,
        mock_config,
    ):
        """Test prompt and model creation."""
        mock_get_model_id.return_value = "test-model"
        mock_load_prompt.return_value = "Test system prompt"
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model

        prompt, model = assistant.create_prompt_and_model(mock_config, "variant")

        mock_get_model_id.assert_called_once_with(mock_config)
        mock_load_prompt.assert_called_once_with("test-model", "variant")
        mock_get_model.assert_called_once_with(mock_config)

        assert isinstance(prompt, ChatPromptTemplate)
        assert "Test system prompt" in prompt.format(messages=[])
        assert model == mock_model

    @patch.object(APIAssistant, "create_prompt_and_model")
    @pytest.mark.parametrize("test_case", ["single_api_selection", "no_relevant_apis"])
    def test_select_relevant_apis(
        self, mock_create_prompt_and_model, test_case, test_data, assistant, mock_config
    ):
        """Test API selection functionality."""
        case_data = next(
            c for c in test_data["select_relevant_apis"] if c["name"] == test_case
        )

        # Setup mocks
        mock_prompt = MagicMock()
        mock_prompt.invoke.return_value = "test prompt"
        mock_model = MagicMock()
        mock_structured_model = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured_model
        mock_create_prompt_and_model.return_value = (mock_prompt, mock_model)

        # Create expected response
        expected_apis = [
            SelectApi(**api) for api in case_data["expected"]["selected_apis"]
        ]
        mock_message = SelectedApis(selected_apis=expected_apis)
        mock_structured_model.invoke.return_value = mock_message

        # Create state
        state = AgentState(
            messages=[
                HumanMessage(content=case_data["input"]["messages"][0]["content"])
            ],
            api_summaries=case_data["input"]["api_summaries"],
        )

        result = assistant.select_relevant_apis(state, mock_config)

        # Verify calls
        mock_create_prompt_and_model.assert_called_once_with(
            mock_config, NODE_SELECT_RELEVANT_APIS, disable_streaming=True
        )
        mock_model.with_structured_output.assert_called_once_with(SelectedApis)
        mock_prompt.invoke.assert_called_once()

        # Verify result structure
        assert "selected_apis" in result
        assert len(result["selected_apis"]) == len(
            case_data["expected"]["selected_apis"]
        )
        assert "messages" in result
        assert len(result["messages"]) == case_data["expected"]["messages_count"]

    @pytest.mark.parametrize(
        "test_case", ["tool_calls_present", "no_tool_calls", "empty_messages"]
    )
    def test_determine_workflow_action(self, test_case, test_data, assistant):
        """Test workflow action determination."""
        case_data = next(
            c for c in test_data["determine_workflow_action"] if c["name"] == test_case
        )

        # Create state with messages
        messages = []
        for msg_data in case_data["input"]["messages"]:
            if "tool_calls" in msg_data:
                messages.append(
                    AIMessage(
                        content=msg_data["content"], tool_calls=msg_data["tool_calls"]
                    )
                )
            else:
                messages.append(AIMessage(content=msg_data["content"]))

        state = AgentState(messages=messages)

        # Mock settings for tool recognition
        with patch("api_assistant.core.agent.settings") as mock_settings:
            mock_settings.enable_api_calls = True
            result = assistant.determine_workflow_action(state)
            expected = (
                END if case_data["expected"] == "__end__" else case_data["expected"]
            )
            assert result == expected

    @pytest.mark.parametrize(
        "test_case", ["with_selected_apis", "no_selected_apis", "none_selected_apis"]
    )
    def test_determine_next_step(self, test_case, test_data, assistant):
        """Test next step determination."""
        case_data = next(
            c for c in test_data["determine_next_step"] if c["name"] == test_case
        )

        # Create state
        selected_apis = case_data["input"]["selected_apis"]
        if selected_apis:
            selected_apis = [SelectApi(**api) for api in selected_apis]

        state = AgentState(selected_apis=selected_apis)
        result = assistant.determine_next_step(state)
        assert result == case_data["expected"]

    @patch.object(APIAssistant, "create_prompt_and_model")
    @patch("api_assistant.core.agent.compress_conversation_history_if_needed")
    @patch("api_assistant.core.agent.settings")
    def test_generate_model_response_api_call_disabled(
        self,
        mock_settings,
        mock_compress_history,
        mock_create_prompt_and_model,
        assistant,
        mock_config,
    ):
        """Test model response generation with API calls disabled."""
        mock_settings.enable_api_calls = False
        mock_prompt = MagicMock()
        mock_prompt.invoke.return_value = "test prompt"

        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="This is the AI response")
        mock_create_prompt_and_model.return_value = (mock_prompt, mock_model)
        mock_compress_history.return_value = (
            [HumanMessage(content="Test message")],
            None,
        )

        state = AgentState(
            messages=[HumanMessage(content="Test message")],
            api_specs={"openapi": "3.0.0", "paths": {"/test": {"get": {}}}},
        )

        result = assistant.generate_model_response(state, mock_config)

        # Verify calls
        mock_create_prompt_and_model.assert_called_once_with(
            mock_config, NODE_CALL_MODEL
        )
        mock_prompt.invoke.assert_called_once()
        mock_compress_history.assert_called_once_with(
            state["messages"], mock_model, ANY
        )
        mock_model.invoke.assert_called_once_with("test prompt", mock_config)

        # Verify result
        assert "messages" in result
        assert len(result["messages"]) == 2
        assert result["messages"][0].content == "Test message"
        assert result["messages"][1].content == "This is the AI response"

    @patch.object(APIAssistant, "create_prompt_and_model")
    @patch("api_assistant.core.agent.compress_conversation_history_if_needed")
    @patch("api_assistant.core.agent.settings")
    def test_generate_model_response_api_call_enabled(
        self,
        mock_settings,
        mock_compress_history,
        mock_create_prompt_and_model,
        assistant,
        mock_config,
    ):
        """Test model response generation with API calls enabled."""
        mock_settings.enable_api_calls = True
        mock_prompt = MagicMock()
        mock_prompt.invoke.return_value = "test prompt"

        mock_model = MagicMock()
        mock_model.invoke.return_value = AIMessage(content="This is the AI response")
        mock_create_prompt_and_model.return_value = (mock_prompt, mock_model)
        mock_compress_history.return_value = (
            [HumanMessage(content="Test message")],
            None,
        )

        state = AgentState(
            messages=[HumanMessage(content="Test message")],
            api_specs={"openapi": "3.0.0", "paths": {"/test": {"get": {}}}},
        )

        assistant.generate_model_response(state, mock_config)

        # Verify calls
        mock_create_prompt_and_model.assert_called_once_with(
            mock_config, NODE_CALL_MODEL
        )
        mock_prompt.invoke.assert_called_once()
        mock_compress_history.assert_called_once_with(
            state["messages"], mock_model, ANY
        )
        mock_model.bind_tools.assert_called_once()

    def test_agent_state_creation(self):
        """Test AgentState creation and validation."""
        messages = [HumanMessage(content="Test message")]
        api_specs = {"openapi": "3.0.0", "paths": {}}
        api_summaries = [{"title": "Test API", "version": "1.0"}]

        state = AgentState(
            messages=messages,
            api_specs=api_specs,
            api_summaries=api_summaries,
        )

        assert state["messages"] == messages
        assert state["api_specs"] == api_specs
        assert state["api_summaries"] == api_summaries
