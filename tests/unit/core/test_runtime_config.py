"""
Unit tests for runtime configuration functionality.

Tests cover ModelConfig and ConfigSchema validation and behavior.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

import pytest

from nalai.core.runtime_config import (
    DEFAULT_MODEL_CONFIG,
    ConfigSchema,
    ModelConfig,
)


class TestModelConfig:
    """Test suite for ModelConfig."""

    def test_model_config_creation(self):
        """Test ModelConfig creation with valid data."""
        config = ModelConfig(name="test-model", platform="openai")

        assert config.name == "test-model"
        assert config.platform == "openai"

    def test_model_config_validation(self):
        """Test ModelConfig validation."""
        # Should not raise any errors
        config = ModelConfig(name="claude-3.5-sonnet", platform="aws_bedrock")

        assert config.name == "claude-3.5-sonnet"
        assert config.platform == "aws_bedrock"

    def test_model_config_empty_strings(self):
        """Test ModelConfig with empty strings."""
        # This test should expect validation errors for empty strings
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ModelConfig(name="", platform="")

    def test_model_config_special_characters(self):
        """Test ModelConfig with special characters."""
        config = ModelConfig(name="model-v1.2.3", platform="aws_bedrock")

        assert config.name == "model-v1.2.3"
        assert config.platform == "aws_bedrock"


class TestConfigSchema:
    """Test suite for ConfigSchema."""

    def test_config_schema_creation(self):
        """Test ConfigSchema creation with valid data."""
        model_config = ModelConfig(name="test-model", platform="openai")
        config = ConfigSchema(model=model_config)

        assert config.model == model_config
        assert config.model.name == "test-model"
        assert config.model.platform == "openai"

    def test_config_schema_default_model(self):
        """Test ConfigSchema with default model."""
        config = ConfigSchema()

        assert config.model == DEFAULT_MODEL_CONFIG
        assert config.model.name == "gpt-4.1"
        assert config.model.platform == "openai"

    def test_config_schema_to_internal_config(self):
        """Test ConfigSchema conversion to internal config."""
        model_config = ModelConfig(name="test-model", platform="openai")
        config = ConfigSchema(model=model_config)

        internal_config = config.model.to_internal_config()

        assert internal_config == {
            "configurable": {"model": {"name": "test-model", "platform": "openai"}}
        }
