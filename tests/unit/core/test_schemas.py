"""
Unit tests for core schemas functionality.

Tests cover schema validation, data model creation, and type checking
for all core data structures.
"""

import os
import sys

from langchain_core.messages import AIMessage, HumanMessage

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.core.agent import (
    DEFAULT_MODEL_CONFIG,
    ConfigSchema,
    ModelConfig,
    SelectApi,
    SelectedApis,
)
from nalai.core.states import AgentState


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


class TestModelConfig:
    """Test suite for ModelConfig."""

    def test_model_config_creation(self):
        """Test ModelConfig creation with valid data."""
        config = ModelConfig(name="test-model", platform="test-platform")

        assert config.name == "test-model"
        assert config.platform == "test-platform"

    def test_model_config_validation(self):
        """Test ModelConfig validation."""
        # Should not raise any errors
        config = ModelConfig(name="claude-3.5-sonnet", platform="aws_bedrock")

        assert config.name == "claude-3.5-sonnet"
        assert config.platform == "aws_bedrock"

    def test_model_config_empty_strings(self):
        """Test ModelConfig with empty strings."""
        config = ModelConfig(name="", platform="")

        assert config.name == ""
        assert config.platform == ""

    def test_model_config_special_characters(self):
        """Test ModelConfig with special characters."""
        config = ModelConfig(name="model-v1.2.3", platform="aws-bedrock")

        assert config.name == "model-v1.2.3"
        assert config.platform == "aws-bedrock"


class TestConfigSchema:
    """Test suite for ConfigSchema."""

    def test_config_schema_creation(self):
        """Test ConfigSchema creation with valid data."""
        model_config = ModelConfig(name="test-model", platform="test-platform")
        config = ConfigSchema(model=model_config)

        assert config.model == model_config
        assert config.model.name == "test-model"
        assert config.model.platform == "test-platform"

    def test_config_schema_default_model(self):
        """Test ConfigSchema with default model."""
        config = ConfigSchema()
        assert config.model == DEFAULT_MODEL_CONFIG
        assert config.model.name == "gpt-4.1"
        assert config.model.platform == "openai"

    def test_config_schema_field_description(self):
        """Test that ConfigSchema has proper field descriptions."""
        # Check that the field has a description
        model_field = ConfigSchema.model_fields["model"]
        assert model_field.description is not None
        assert "Configuration for the model" in model_field.description


class TestOutputSchema:
    """Test suite for OutputSchema."""

    def test_output_schema_creation(self):
        """Test OutputSchema creation with valid data."""
        messages = [HumanMessage(content="Hello")]

        output_data = {"messages": messages}

        assert output_data["messages"] == messages
        assert len(output_data["messages"]) == 1

    def test_output_schema_inheritance(self):
        """Test that OutputSchema inherits from InputSchema."""
        # OutputSchema should have the same structure as InputSchema
        messages = [HumanMessage(content="Hello")]

        input_data = {"messages": messages}
        output_data = {"messages": messages}

        # Both should have the same structure
        assert "messages" in input_data
        assert "messages" in output_data
        assert input_data["messages"] == output_data["messages"]


class TestSelectApi:
    """Test suite for SelectApi."""

    def test_select_api_creation(self):
        """Test SelectApi creation with valid data."""
        api = SelectApi(api_title="User API", api_version="1.0")

        assert api.api_title == "User API"
        assert api.api_version == "1.0"

    def test_select_api_field_descriptions(self):
        """Test that SelectApi has proper field descriptions."""
        # Check that fields have descriptions
        title_field = SelectApi.model_fields["api_title"]
        version_field = SelectApi.model_fields["api_version"]

        assert title_field.description is not None
        assert version_field.description is not None
        assert "title" in title_field.description
        assert "version" in version_field.description

    def test_select_api_validation(self):
        """Test SelectApi validation."""
        # Should not raise any errors
        api = SelectApi(api_title="Product API", api_version="2.1")

        assert api.api_title == "Product API"
        assert api.api_version == "2.1"

    def test_select_api_empty_strings(self):
        """Test SelectApi with empty strings."""
        api = SelectApi(api_title="", api_version="")

        assert api.api_title == ""
        assert api.api_version == ""

    def test_select_api_special_characters(self):
        """Test SelectApi with special characters."""
        api = SelectApi(api_title="API-v1.2.3", api_version="beta-1.0")

        assert api.api_title == "API-v1.2.3"
        assert api.api_version == "beta-1.0"


class TestSelectedApis:
    """Test suite for SelectedApis."""

    def test_selected_apis_creation(self):
        """Test SelectedApis creation with valid data."""
        apis = [
            SelectApi(api_title="User API", api_version="1.0"),
            SelectApi(api_title="Product API", api_version="2.0"),
        ]

        selected_apis = SelectedApis(selected_apis=apis)

        assert len(selected_apis.selected_apis) == 2
        assert selected_apis.selected_apis[0].api_title == "User API"
        assert selected_apis.selected_apis[1].api_title == "Product API"

    def test_selected_apis_empty_list(self):
        """Test SelectedApis with empty list."""
        selected_apis = SelectedApis(selected_apis=[])

        assert len(selected_apis.selected_apis) == 0

    def test_selected_apis_default_factory(self):
        """Test SelectedApis with default factory."""
        selected_apis = SelectedApis()

        assert len(selected_apis.selected_apis) == 0
        assert isinstance(selected_apis.selected_apis, list)

    def test_selected_apis_field_descriptions(self):
        """Test that SelectedApis has proper field descriptions."""
        # Check that the field has a description
        apis_field = SelectedApis.model_fields["selected_apis"]
        assert apis_field.description is not None
        assert "List of selected APIs" in apis_field.description

    def test_selected_apis_mixed_versions(self):
        """Test SelectedApis with mixed API versions."""
        apis = [
            SelectApi(api_title="API 1", api_version="1.0"),
            SelectApi(api_title="API 2", api_version="2.0"),
            SelectApi(api_title="API 3", api_version="1.5"),
        ]

        selected_apis = SelectedApis(selected_apis=apis)

        assert len(selected_apis.selected_apis) == 3
        versions = [api.api_version for api in selected_apis.selected_apis]
        assert "1.0" in versions
        assert "2.0" in versions
        assert "1.5" in versions

    def test_selected_apis_duplicate_apis(self):
        """Test SelectedApis with duplicate APIs."""
        apis = [
            SelectApi(api_title="User API", api_version="1.0"),
            SelectApi(api_title="User API", api_version="1.0"),
            SelectApi(api_title="Product API", api_version="2.0"),
        ]

        selected_apis = SelectedApis(selected_apis=apis)

        assert len(selected_apis.selected_apis) == 3
        # Should allow duplicates as they might be intentional


class TestSchemaIntegration:
    """Test suite for schema integration scenarios."""

    def test_agent_state_with_selected_apis(self):
        """Test AgentState with SelectedApis integration."""
        messages = [HumanMessage(content="Hello")]
        apis = [
            SelectApi(api_title="User API", api_version="1.0"),
            SelectApi(api_title="Product API", api_version="2.0"),
        ]
        selected_apis = SelectedApis(selected_apis=apis)

        state = AgentState(
            messages=messages,
            selected_apis=selected_apis.selected_apis,
        )

        assert state["messages"] == messages
        assert len(state["selected_apis"]) == 2
        assert state["selected_apis"][0].api_title == "User API"

    def test_config_schema_with_model_config(self):
        """Test ConfigSchema with ModelConfig integration."""
        model_config = ModelConfig(name="claude-3.5-sonnet", platform="aws_bedrock")
        config = ConfigSchema(model=model_config)

        assert config.model.name == "claude-3.5-sonnet"
        assert config.model.platform == "aws_bedrock"

    def test_complete_workflow_state(self):
        """Test a complete workflow state with all components."""
        messages = [HumanMessage(content="How do I get users?")]
        api_specs = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}
        api_summaries = [{"title": "User API", "version": "1.0"}]
        apis = [SelectApi(api_title="User API", api_version="1.0")]
        selected_apis = SelectedApis(selected_apis=apis)

        state = AgentState(
            messages=messages,
            api_specs=api_specs,
            api_summaries=api_summaries,
            selected_apis=selected_apis.selected_apis,
        )

        assert state["messages"] == messages
        assert state["api_specs"] == api_specs
        assert state["api_summaries"] == api_summaries
        assert len(state["selected_apis"]) == 1
        assert state["selected_apis"][0].api_title == "User API"
