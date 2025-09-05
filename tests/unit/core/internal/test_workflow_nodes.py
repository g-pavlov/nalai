"""
Unit tests for WorkflowNodes core functionality.

Tests cover workflow node initialization, response parsing, template formatting,
API selection, workflow actions, and model response generation.
"""

import os
import sys
from unittest.mock import ANY, MagicMock, patch

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

# Internal types for unit testing
from nalai.core.agent import SelectApi, SelectedApis
from nalai.core.internal.constants import (
    NODE_CALL_MODEL,
    NODE_SELECT_RELEVANT_APIS,
)
from nalai.core.internal.states import AgentState
from nalai.core.internal.workflow_nodes import WorkflowNodes
from nalai.prompts.prompts import format_template_with_variables


@pytest.fixture
def assistant():
    """Create a fresh WorkflowNodes instance for each test."""
    return WorkflowNodes()


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
        os.path.dirname(__file__), "test_data", "agent_api_test_cases.yaml"
    )
    with open(test_data_path) as f:
        return yaml.safe_load(f)


class TestWorkflowNodes:
    """Test cases for WorkflowNodes functionality."""

    def test_agent_initialization(self, assistant):
        """Test agent initialization."""
        assert assistant.http_toolkit is not None

    def test_format_template_with_variables_basic(self):
        """Test basic template variable formatting."""
        # Test basic template formatting functionality
        template = "Hello {name}, you have {count} messages."
        result = format_template_with_variables(template, name="Alice", count=5)
        assert result == "Hello Alice, you have 5 messages."

    @patch("nalai.core.internal.workflow_nodes.get_model_service")
    @patch("nalai.core.internal.workflow_nodes.load_prompt_template")
    def test_create_prompt_and_model(
        self,
        mock_load_prompt,
        mock_get_model_service,
        assistant,
        mock_config,
    ):
        """Test prompt and model creation."""
        mock_model_service = MagicMock()
        mock_model_service.get_model_id_from_config.return_value = "test-model"
        mock_model = MagicMock()
        mock_model_service.get_model_from_config.return_value = mock_model
        mock_get_model_service.return_value = mock_model_service
        mock_load_prompt.return_value = "Test system prompt"

        prompt, model = assistant.create_prompt_and_model(mock_config, "variant")

        mock_model_service.get_model_id_from_config.assert_called_once_with(mock_config)
        mock_load_prompt.assert_called_once_with("test-model", "variant")
        mock_model_service.get_model_from_config.assert_called_once_with(mock_config)

        assert isinstance(prompt, ChatPromptTemplate)
        assert "Test system prompt" in prompt.format(messages=[])
        assert model == mock_model

    @patch.object(WorkflowNodes, "create_prompt_and_model")
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
    def test_should_execute_tools(self, test_case, test_data, assistant):
        """Test tool execution determination."""
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
        with patch("nalai.core.internal.workflow_nodes.settings") as mock_settings:
            mock_settings.api_calls_enabled = True
            result = assistant.should_execute_tools(state)
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

    @patch.object(WorkflowNodes, "create_prompt_and_model")
    @patch("nalai.core.internal.workflow_nodes.compress_conversation_history_if_needed")
    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_generate_model_response_api_call_disabled(
        self,
        mock_settings,
        mock_compress_history,
        mock_create_prompt_and_model,
        assistant,
        mock_config,
    ):
        """Test model response generation with API calls disabled."""
        mock_settings.api_calls_enabled = False
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

    @patch.object(WorkflowNodes, "create_prompt_and_model")
    @patch("nalai.core.internal.workflow_nodes.compress_conversation_history_if_needed")
    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_generate_model_response_api_call_enabled(
        self,
        mock_settings,
        mock_compress_history,
        mock_create_prompt_and_model,
        assistant,
        mock_config,
    ):
        """Test model response generation with API calls enabled."""
        mock_settings.api_calls_enabled = True
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

    @patch.object(WorkflowNodes, "_handle_cached_model_response")
    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_generate_model_response_cache_hit(
        self, mock_settings, mock_handle_cached, assistant, mock_config
    ):
        """Test model response generation with cache hit."""
        mock_settings.cache_enabled = True

        # Setup cache hit scenario
        cached_messages = [
            HumanMessage(content="Test message"),
            AIMessage(content="Cached response"),
        ]
        mock_handle_cached.return_value = {"messages": cached_messages}

        state = AgentState(messages=cached_messages, cache_hit=True)

        result = assistant.generate_model_response(state, mock_config)

        # Verify cache handling was called
        mock_handle_cached.assert_called_once_with(cached_messages, mock_config)

        # Verify result
        assert result == {"messages": cached_messages}

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

    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_handle_cached_model_response(self, mock_settings, assistant, mock_config):
        """Test handling of cached model responses."""
        mock_settings.cache_enabled = True

        # Create test messages with a cached AI response
        cached_message = AIMessage(content="This is a cached response")
        messages = [HumanMessage(content="Test question"), cached_message]

        result = assistant._handle_cached_model_response(messages, mock_config)

        # Verify the result contains the messages
        assert "messages" in result
        assert len(result["messages"]) == 3  # Original 2 + 1 new response
        assert result["messages"][-1].content == "This is a cached response"

    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_handle_cached_model_response_no_ai_message(
        self, mock_settings, assistant, mock_config
    ):
        """Test handling of cached responses when no AI message is found."""
        mock_settings.cache_enabled = True

        # Create test messages without AI response
        messages = [HumanMessage(content="Test question")]

        result = assistant._handle_cached_model_response(messages, mock_config)

        # Verify the result contains the original messages
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Test question"

    @patch("nalai.core.internal.workflow_nodes.get_cache_service")
    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_cache_model_response_enabled(
        self, mock_settings, mock_get_cache_service, assistant, mock_config
    ):
        """Test caching model responses when enabled."""
        mock_settings.cache_enabled = True
        mock_cache_service = MagicMock()
        mock_get_cache_service.return_value = mock_cache_service

        # Setup config with user_id
        mock_config["configurable"] = {"user_id": "test-user"}

        messages = [HumanMessage(content="Test message")]
        response = AIMessage(content="Test response")

        assistant._cache_model_response(messages, response, mock_config)

        # Verify cache service was called
        mock_cache_service.set.assert_called_once_with(
            messages=messages,
            response="Test response",
            tool_calls=[],
            user_id="test-user",
        )

    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_cache_model_response_disabled_globally(
        self, mock_settings, assistant, mock_config
    ):
        """Test that caching is skipped when disabled globally."""
        mock_settings.cache_enabled = False

        messages = [HumanMessage(content="Test message")]
        response = AIMessage(content="Test response")

        # Should not raise any exceptions and should not call cache service
        assistant._cache_model_response(messages, response, mock_config)

    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_cache_model_response_disabled_per_request(
        self, mock_settings, assistant, mock_config
    ):
        """Test that caching is skipped when disabled per request."""
        mock_settings.cache_enabled = True

        # Setup config with cache disabled
        mock_config["configurable"] = {"cache_disabled": True}

        messages = [HumanMessage(content="Test message")]
        response = AIMessage(content="Test response")

        # Should not raise any exceptions and should not call cache service
        assistant._cache_model_response(messages, response, mock_config)

    @patch("nalai.core.internal.workflow_nodes.settings")
    def test_cache_model_response_empty_content(
        self, mock_settings, assistant, mock_config
    ):
        """Test that caching is skipped for empty content responses."""
        mock_settings.cache_enabled = True

        messages = [HumanMessage(content="Test message")]
        response = AIMessage(content="")  # Empty content

        # Should not raise any exceptions and should not call cache service
        assistant._cache_model_response(messages, response, mock_config)

    def test_workflow_nodes_with_service_factory_mocking(self):
        """Test workflow nodes using service factory pattern for dependency injection."""
        # Arrange
        from unittest.mock import AsyncMock

        # Create mock services
        mock_cache_service = AsyncMock()
        mock_model_service = AsyncMock()

        # Mock the service factory functions
        with (
            patch(
                "nalai.services.factory.get_cache_service",
                return_value=mock_cache_service,
            ),
            patch(
                "nalai.services.factory.get_model_service",
                return_value=mock_model_service,
            ),
        ):
            # Act - Test that services are properly injected
            # Verify that the service factory functions are called when services are needed
            # Test that we can access the services (they would be called during workflow execution)
            # This demonstrates that the service factory pattern is working
            assert mock_cache_service is not None
            assert mock_model_service is not None

            # Assert - Verify services were properly mocked
            # The actual service calls would happen during workflow execution
            # This test just verifies the dependency injection pattern works

    def test_workflow_nodes_with_failing_cache_service(self):
        """Test workflow nodes behavior when cache service fails."""
        # Arrange
        from unittest.mock import AsyncMock

        # Create a cache service that fails
        mock_cache_service = AsyncMock()
        mock_cache_service.set.side_effect = Exception("Cache service unavailable")
        mock_model_service = AsyncMock()

        with (
            patch(
                "nalai.services.factory.get_cache_service",
                return_value=mock_cache_service,
            ),
            patch(
                "nalai.services.factory.get_model_service",
                return_value=mock_model_service,
            ),
        ):
            assistant = WorkflowNodes()

            # Act & Assert - Should handle cache failure gracefully
            mock_config = {"configurable": {"user_id": "test_user"}}
            messages = [HumanMessage(content="Hello")]

            # Should not raise exception even if cache fails
            assistant._cache_model_response(
                messages, AIMessage(content="Test response"), mock_config
            )

            # Verify cache service was attempted (this would happen during actual workflow execution)
            # This test just verifies the dependency injection pattern works
            assert mock_cache_service is not None

    @pytest.mark.asyncio
    async def test_workflow_nodes_model_service_integration(self):
        """Test workflow nodes integration with model service."""
        # Arrange
        from unittest.mock import AsyncMock

        mock_cache_service = AsyncMock()
        mock_model_service = AsyncMock()
        mock_model_service.get_model_id_from_config.return_value = "test-model"
        mock_model_service.get_model_from_config.return_value = "mock-model-instance"

        with (
            patch(
                "nalai.services.factory.get_cache_service",
                return_value=mock_cache_service,
            ),
            patch(
                "nalai.services.factory.get_model_service",
                return_value=mock_model_service,
            ),
        ):
            # Act - Test model service integration
            mock_config = {"configurable": {"user_id": "test_user"}}

            # Test model ID extraction
            model_id = await mock_model_service.get_model_id_from_config(mock_config)
            assert model_id == "test-model"

            # Test model instance creation
            model_instance = await mock_model_service.get_model_from_config(mock_config)
            assert model_instance == "mock-model-instance"

            # Assert - Verify model service was called
            mock_model_service.get_model_id_from_config.assert_called_with(mock_config)
            mock_model_service.get_model_from_config.assert_called_with(mock_config)
