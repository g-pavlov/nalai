"""
Shared test configuration and fixtures for unit tests.

This module provides common fixtures, test data loading utilities,
and configuration that can be used across all unit tests.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))


@pytest.fixture(scope="session")
def test_data_dir():
    """Get the test data directory path."""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def load_test_data(test_data_dir):
    """Load test data from YAML files."""

    def _load_test_data(filename):
        file_path = test_data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Test data file not found: {file_path}")

        with open(file_path) as f:
            return yaml.safe_load(f)

    return _load_test_data


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return RunnableConfig(
        configurable={
            "thread_id": "test-thread-123",
            "model": "test-model",
            "org_unit_id": "test-org",
            "user_email": "test@example.com",
            "auth_token": "test-token",
        }
    )


@pytest.fixture
def mock_run_manager():
    """Create a mock run manager for testing."""
    return MagicMock()


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        HumanMessage(content="Hello, how can you help me?"),
        AIMessage(content="I can help you with API-related questions and tasks."),
        HumanMessage(content="How do I get a list of users?"),
    ]


@pytest.fixture
def sample_api_summaries():
    """Create sample API summaries for testing."""
    return [
        {
            "title": "User API",
            "description": "API for user management operations",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "version": "1.0",
            "openapi_file": "core_services_v_1_0_0.yaml",
        },
        {
            "title": "Product API",
            "description": "API for product management operations",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "version": "2.0",
            "openapi_file": "storage_v_1_0_0.yaml",
        },
    ]


@pytest.fixture
def sample_api_specs():
    """Create sample API specifications for testing."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0",
            "description": "Test API for unit testing",
        },
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get users",
                    "description": "Retrieve a list of users",
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "name": {"type": "string"},
                                                "email": {"type": "string"},
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "summary": "Create user",
                    "description": "Create a new user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "User created successfully"}},
                },
            }
        },
    }


@pytest.fixture
def mock_model():
    """Create a mock language model for testing."""
    model = MagicMock()
    model.metadata = {
        "context_window": 32000,
        "model_id": "test-model",
        "model_platform": "test-platform",
        "messages_token_count_supported": True,
    }
    model.get_num_tokens_from_messages.return_value = 100
    model.invoke.return_value = AIMessage(content="Test response")
    return model


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response for testing."""
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = {"result": "success", "data": []}
    response.text = '{"result": "success", "data": []}'
    return response


@pytest.fixture
def mock_http_error_response():
    """Create a mock HTTP error response for testing."""
    response = MagicMock()
    response.ok = False
    response.status_code = 404
    response.raise_for_status.side_effect = Exception("HTTP Error")
    response.text = '{"error": "Not found"}'
    return response


@pytest.fixture
def temp_yaml_file():
    """Create a temporary YAML file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml_content = {
            "test_data": [
                {"key": "value1", "number": 1},
                {"key": "value2", "number": 2},
            ]
        }
        yaml.dump(yaml_content, f)
        temp_file = f.name

    yield temp_file

    # Cleanup
    try:
        os.unlink(temp_file)
    except OSError:
        pass


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.api_calls_base_url = "https://api.example.com"
    settings.aws_bedrock_retry_max_attempts = 3
    settings.default_model_platform = "aws_bedrock"
    settings.default_model_id = "claude-3.5-sonnet"
    settings.enable_api_calls = True
    return settings


@pytest.fixture
def mock_tool_call():
    """Create a mock tool call for testing."""
    return {
        "id": "call_123",
        "name": "get_http_requests",
        "args": {"method": "GET", "url": "https://api.example.com/users"},
    }


@pytest.fixture
def mock_ai_message_with_tool_calls(mock_tool_call):
    """Create a mock AI message with tool calls."""
    return AIMessage(
        content="Here is a tool call", id="ai-msg-123", tool_calls=[mock_tool_call]
    )


@pytest.fixture
def mock_agent():
    """Create a mock APIAssistant agent for testing."""
    agent = MagicMock()
    agent.http_toolkit = MagicMock()
    agent.http_toolkit.get_tools.return_value = [MagicMock(), MagicMock()]
    agent.select_relevant_apis = MagicMock()
    agent.generate_model_response = MagicMock()
    agent.determine_workflow_action = MagicMock()
    agent.determine_next_step = MagicMock()
    return agent


@pytest.fixture
def mock_memory_store():
    """Create a mock memory store for testing."""
    return MagicMock()


@pytest.fixture
def mock_available_tools():
    """Create mock available tools for testing."""
    return {"call_api": MagicMock()}


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Mark tests in unit directory as unit tests
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Mark tests that take longer than 1 second as slow
        if hasattr(item, "func") and "slow" in item.func.__name__:
            item.add_marker(pytest.mark.slow)


# Test utilities
class TestDataHelper:
    """Helper class for working with test data."""

    @staticmethod
    def create_messages(*contents):
        """Create a list of messages from content strings."""
        messages = []
        for i, content in enumerate(contents):
            if i % 2 == 0:
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
        return messages

    @staticmethod
    def create_api_summary(title, version="1.0", methods=None):
        """Create an API summary dictionary."""
        if methods is None:
            methods = ["GET", "POST"]

        return {
            "title": title,
            "description": f"API for {title.lower()} operations",
            "methods": methods,
            "version": version,
            "openapi_file": f"{title.lower().replace(' ', '_')}_v_{version.replace('.', '_')}_0.yaml",
        }

    @staticmethod
    def create_tool_call(tool_name, **args):
        """Create a tool call dictionary."""
        return {
            "id": f"call_{tool_name}_{hash(str(args)) % 1000}",
            "name": tool_name,
            "args": args,
        }


@pytest.fixture
def test_data_helper():
    """Provide access to TestDataHelper utilities."""
    return TestDataHelper
