"""
Unit tests for ModelService functionality.

Tests cover model initialization, configuration extraction, context window
management, and message content extraction across different providers.
"""

import os
import sys
from unittest.mock import MagicMock, patch, ANY

import pytest
import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from api_assistant.services.model_service import ModelService


@pytest.fixture
def test_data():
    """Load test data from YAML file."""
    test_data_path = os.path.join(
        os.path.dirname(__file__), "..", "test_data", "model_service_test_cases.yaml"
    )
    with open(test_data_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return RunnableConfig(
        configurable={"model": {"name": "test-model", "platform": "test-platform"}}
    )


class TestModelService:
    """Test suite for ModelService class."""

    @pytest.mark.parametrize(
        "test_case", ["string_content", "dict_content", "list_content", "mixed_content"]
    )
    def test_extract_message_content(self, test_case, test_data):
        """Test message content extraction from different formats."""
        case_data = next(
            c for c in test_data["extract_message_content"] if c["name"] == test_case
        )

        # Create a mock message with the test content
        mock_message = MagicMock(spec=BaseMessage)
        mock_message.content = case_data["input"]["content"]

        result = ModelService.extract_message_content(mock_message)
        assert result == case_data["expected"]

    @pytest.mark.parametrize(
        "test_case",
        ["claude_3_5_sonnet", "llama_3_2", "mistral_small", "unknown_model"],
    )
    def test_get_model_context_window_size(self, test_case, test_data):
        """Test context window size retrieval for different models."""
        case_data = next(
            c
            for c in test_data["get_model_context_window_size"]
            if c["name"] == test_case
        )

        result = ModelService.get_model_context_window_size(
            case_data["input"]["model_platform"], case_data["input"]["model_name"]
        )
        assert result == case_data["expected"]

    @patch("api_assistant.services.model_service.create_model_rate_limiter")
    @patch("api_assistant.services.model_service.init_chat_model")
    @patch("api_assistant.services.model_service.settings")
    @pytest.mark.parametrize(
        "test_case", ["aws_bedrock_model", "ollama_model", "unknown_provider"]
    )
    def test_initialize_chat_model(
        self,
        mock_settings,
        mock_init_chat_model,
        mock_create_rate_limiter,
        test_case,
        test_data,
    ):
        """Test chat model initialization for different providers."""
        case_data = next(
            c for c in test_data["model_initialization"] if c["name"] == test_case
        )

        # Setup mocks
        mock_settings.aws_bedrock_retry_max_attempts = 3
        mock_settings.default_model_platform = "aws_bedrock"
        mock_settings.default_model_id = "claude-3.5-sonnet"

        mock_model = MagicMock(spec=BaseChatModel)
        mock_model.metadata = {}
        mock_init_chat_model.return_value = mock_model

        mock_rate_limiter = MagicMock()
        mock_create_rate_limiter.return_value = mock_rate_limiter

        # Test AWS Bedrock specific behavior
        if case_data["input"]["model_provider"] == "aws_bedrock":
            with patch("botocore.config.Config") as mock_boto_config:
                mock_config_instance = MagicMock()
                mock_boto_config.return_value = mock_config_instance

                result = ModelService.initialize_chat_model(
                    case_data["input"]["model_id"],
                    case_data["input"]["model_provider"],
                    configurable_fields=case_data["input"].get("configurable_fields"),
                )

                # Verify AWS Bedrock specific calls
                mock_boto_config.assert_called_once()
                mock_init_chat_model.assert_called_once_with(
                    case_data["input"]["model_id"],
                    model_provider="bedrock_converse",
                    config=mock_config_instance,
                    rate_limiter=mock_rate_limiter,
                    configurable_fields=case_data["input"].get("configurable_fields"),
                )

        # Test Ollama specific behavior
        elif case_data["input"]["model_provider"] == "ollama":
            result = ModelService.initialize_chat_model(
                case_data["input"]["model_id"], case_data["input"]["model_provider"]
            )

            # Verify Ollama specific calls - init_chat_model should be called with ollama provider
            mock_init_chat_model.assert_called_once_with(
                case_data["input"]["model_id"],
                model_provider="ollama",
                configurable_fields=None,
                rate_limiter=mock_rate_limiter,
                base_url=ANY,
            )
            assert result.metadata["model_id"] == case_data["input"]["model_id"]
            assert (
                result.metadata["model_platform"]
                == case_data["input"]["model_provider"]
            )

        # Test generic provider behavior
        else:
            result = ModelService.initialize_chat_model(
                case_data["input"]["model_id"], case_data["input"]["model_provider"]
            )

            mock_init_chat_model.assert_called_once_with(
                case_data["input"]["model_id"],
                model_provider=case_data["input"]["model_provider"],
                configurable_fields=None,
                rate_limiter=mock_rate_limiter,
            )

        # Verify common metadata
        assert result.metadata["context_window"] is not None
        assert result.metadata["model_id"] == case_data["input"]["model_id"]
        assert result.metadata["model_platform"] == case_data["input"]["model_provider"]

    def test_get_model_config(self, mock_config):
        """Test model configuration extraction from RunnableConfig."""
        result = ModelService.get_model_config(mock_config)

        assert result is not None
        assert result.get("name") == "test-model"
        assert result.get("platform") == "test-platform"

    def test_get_model_id_from_config(self, mock_config):
        """Test model ID extraction from RunnableConfig."""
        result = ModelService.get_model_id_from_config(mock_config)
        assert result == "test-model"

    @patch("api_assistant.services.model_service.ModelService.get_model_config")
    @patch("api_assistant.services.model_service.ModelService.initialize_chat_model")
    def test_get_model_from_config(
        self, mock_initialize_model, mock_get_config, mock_config
    ):
        """Test model retrieval from configuration."""
        mock_model_config = {"name": "test-model", "platform": "test-platform"}
        mock_get_config.return_value = mock_model_config

        mock_model = MagicMock(spec=BaseChatModel)
        mock_initialize_model.return_value = mock_model

        result = ModelService.get_model_from_config(mock_config, temperature=0.7)

        mock_get_config.assert_called_once_with(mock_config)
        mock_initialize_model.assert_called_once_with(
            model_id="test-model", model_provider="test-platform", temperature=0.7
        )
        assert result == mock_model

    def test_extract_message_content_edge_cases(self):
        """Test message content extraction with edge cases."""
        # Test with None content
        mock_message = MagicMock(spec=BaseMessage)
        mock_message.content = None
        result = ModelService.extract_message_content(mock_message)
        assert result == ""

        # Test with empty string content
        mock_message.content = ""
        result = ModelService.extract_message_content(mock_message)
        assert result == ""

        # Test with complex nested content
        mock_message.content = [
            {"text": "Hello"},
            " ",
            {"text": "world", "type": "text"},
            {"type": "image", "url": "test.jpg"},
        ]
        result = ModelService.extract_message_content(mock_message)
        assert result == "Hello world"

    def test_context_window_size_edge_cases(self):
        """Test context window size with edge cases."""
        # Test with None values
        result = ModelService.get_model_context_window_size(None, None)
        assert result == 32000  # Default value

        # Test with empty strings
        result = ModelService.get_model_context_window_size("", "")
        assert result == 32000  # Default value

        # Test with unknown model
        result = ModelService.get_model_context_window_size("unknown", "unknown-model")
        assert result == 32000  # Default value

    @patch("api_assistant.services.model_service.settings")
    def test_model_initialization_with_rate_limiting(self, mock_settings):
        """Test model initialization with rate limiting."""
        mock_settings.aws_bedrock_retry_max_attempts = 3
        mock_settings.default_model_platform = "aws_bedrock"
        mock_settings.default_model_id = "claude-3.5-sonnet"

        with (
            patch(
                "api_assistant.services.model_service.create_model_rate_limiter"
            ) as mock_create_limiter,
            patch(
                "api_assistant.services.model_service.init_chat_model"
            ) as mock_init_model,
        ):
            mock_rate_limiter = MagicMock()
            mock_create_limiter.return_value = mock_rate_limiter

            mock_model = MagicMock(spec=BaseChatModel)
            mock_model.metadata = {}
            mock_init_model.return_value = mock_model

            ModelService.initialize_chat_model("test-model", "aws_bedrock")

            mock_create_limiter.assert_called_once_with("aws_bedrock", "test-model")
            mock_init_model.assert_called_once()

            # Verify rate limiter was passed to model initialization
            call_args = mock_init_model.call_args
            assert "rate_limiter" in call_args[1]
            assert call_args[1]["rate_limiter"] == mock_rate_limiter

    def test_model_metadata_consistency(self):
        """Test that model metadata is consistent across different providers."""
        with (
            patch(
                "api_assistant.services.model_service.create_model_rate_limiter"
            ) as mock_create_limiter,
            patch(
                "api_assistant.services.model_service.init_chat_model"
            ) as mock_init_model,
            patch("api_assistant.services.model_service.settings") as mock_settings,
        ):
            mock_settings.aws_bedrock_retry_max_attempts = 3
            mock_settings.default_model_platform = "aws_bedrock"
            mock_settings.default_model_id = "claude-3.5-sonnet"

            mock_rate_limiter = MagicMock()
            mock_create_limiter.return_value = mock_rate_limiter

            mock_model = MagicMock(spec=BaseChatModel)
            mock_model.metadata = {}
            mock_init_model.return_value = mock_model

            result = ModelService.initialize_chat_model("test-model", "aws_bedrock")

            # Verify metadata structure
            assert "context_window" in result.metadata
            assert "model_id" in result.metadata
            assert "model_platform" in result.metadata
            assert "messages_token_count_supported" in result.metadata

            assert result.metadata["model_id"] == "test-model"
            assert result.metadata["model_platform"] == "aws_bedrock"
            assert isinstance(result.metadata["context_window"], int)
            assert isinstance(result.metadata["messages_token_count_supported"], bool)
