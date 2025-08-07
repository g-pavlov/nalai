"""
Model service for AI model configuration and management.

Handles model initialization, configuration, and context window
management across multiple providers (AWS Bedrock, Ollama).
Provides rate limiting, retry logic, and metadata management.
"""

import logging
from typing import Any, Literal

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from ..config import BaseRuntimeConfiguration, settings
from .rate_limiting.factory import create_model_rate_limiter

AWS_BEDROCK_PLATFORM = "aws_bedrock"
OLLAMA_PLATFORM = "ollama"
OPENAI_PLATFORM = "openai"
CLAUDE_SONNET_3_5 = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

logger = logging.getLogger(__name__)


class ModelService:
    """Service for AI model operations and configuration management.
    Provides unified interface for model initialization, configuration
    extraction, and context window management across different providers.
    """

    @staticmethod
    def extract_message_content(message: BaseMessage) -> str:
        """Extract text content from a message object.
        Handles different message content formats (string, dict, list)
        and returns unified text representation.
        Args:
            message: LangChain message object
        Returns:
            str: Extracted text content
        """
        content = message.content
        if content is None:
            return ""
        elif isinstance(content, str):
            return content
        elif isinstance(content, dict):
            return content.get("text", "")
        elif isinstance(content, list):
            text_parts = [
                part if isinstance(part, str) else (part.get("text") or "")
                for part in content
            ]
            return "".join(text_parts).strip()
        else:
            return str(content)

    @staticmethod
    def initialize_chat_model(
        model_id: str,
        model_provider: str,
        *,
        configurable_fields: list[str] | Literal[None] = None,
        **kwargs: Any,
    ) -> BaseChatModel:
        """Initialize chat model for specified provider and model ID.
        Convenience adapter around LangChain's init_chat_model with provider-specific
        configurations for AWS Bedrock and Ollama platforms.
        Args:
            model_id: Model identifier (e.g., 'claude-3.5-sonnet')
            model_provider: Provider platform ('aws_bedrock', 'ollama')
            configurable_fields: Fields that can be configured externally (WIP)
            **kwargs: Additional model initialization parameters
        Returns:
            BaseChatModel: Initialized chat model with metadata
        Note:
            Automatically applies rate limiting and retry configurations
            based on provider-specific requirements.
        """
        model_platform = model_provider

        # Create a copy of kwargs for provider-specific modifications
        provider_kwargs = kwargs.copy()

        # AWS Bedrock configuration
        if model_provider == AWS_BEDROCK_PLATFORM:
            model_provider = "bedrock_converse"
            from botocore.config import Config

            provider_kwargs["config"] = Config(
                retries={
                    "max_attempts": settings.aws_bedrock_retry_max_attempts,
                    "mode": "adaptive",
                }
            )
        # Ollama configuration
        elif model_provider == OLLAMA_PLATFORM:
            model_provider = "ollama"
            # Use environment variable for Ollama base URL, fallback to localhost
            ollama_base_url = getattr(
                settings, "ollama_base_url", "http://localhost:11434"
            )
            provider_kwargs["base_url"] = ollama_base_url
        # OpenAI configuration
        elif model_provider == OPENAI_PLATFORM:
            model_provider = "openai"
            # Disable streaming for OpenAI models if requested to prevent tool calling issues
            if kwargs.get("disable_streaming"):
                provider_kwargs["streaming"] = False
                logger.debug(
                    "Disabled streaming for OpenAI model to prevent tool calling issues"
                )

        # Apply rate limiting for API calls
        rate_limiter = create_model_rate_limiter(model_platform, model_id)
        if rate_limiter:
            provider_kwargs["rate_limiter"] = rate_limiter
            logger.debug(f"Applied rate limiting for {model_platform}/{model_id}")

        # Filter out application-specific parameters that shouldn't be passed to model providers
        # These parameters are used by our application logic but not by LangChain model providers
        application_params = {
            "configurable_fields",  # Used by LangChain's _ConfigurableModel wrapper
            "model_provider",  # Used internally by our service
        }

        # Remove application-specific parameters from provider_kwargs
        for param in application_params:
            provider_kwargs.pop(param, None)

        # Use LangChain's init_chat_model for all providers
        initialized_model = init_chat_model(
            model_id,
            model_provider=model_provider,
            configurable_fields=configurable_fields,
            **provider_kwargs,
        )

        context_window_size = ModelService.get_model_context_window_size(
            model_platform, model_name=model_id
        )
        initialized_model.metadata = {
            "context_window": context_window_size,
            "model_id": model_id,
            "model_platform": model_platform,
            "messages_token_count_supported": True,
        }

        return initialized_model

    @staticmethod
    def get_model_context_window_size(
        model_platform: str = settings.default_model_platform,
        model_name: str = settings.default_model_id,
    ) -> int:
        """Get context window size for specified model.
        Returns the token context window size for various model configurations.
        Falls back to default 32K tokens if model not found in mapping.
        Args:
            model_platform: Model provider platform
            model_name: Specific model identifier
        Returns:
            int: Context window size in tokens
        """
        DEFAULT_MODEL_CONTEXT_WINDOW_SIZE = 32000

        model_context_window_sizes = {
            # Mistral Models
            "/mistral-7b-v0.1": 8192,
            "/mistral-7b-instruct-v0.2": 32000,
            "/mistral-nemo-12b": 128000,
            "/mistral-small-24b-instruct": 32000,
            ## Mistral bedrock ids
            "aws_bedrock/mistral.mistral-small-2402-v1:0": 32000,
            "aws_bedrock/mistral.mistral-large-2402-v1:0": 32000,
            "aws_bedrock/mistral.mistral-7b-instruct-v0:2": 32000,
            "aws_bedrock/mistral.mixtral-8x7b-instruct-v0:1": 32000,
            # Claude Models
            ## Bedrock model ids
            "aws_bedrock/claude-3.5-sonnet": 200000,
            "aws_bedrock/anthropic.claude-3-5-haiku-20241022-v1:0": 200000,
            "aws_bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0": 200000,
            "aws_bedrock/anthropic.claude-3-7-sonnet-20250219-v1:0": 200000,
            # Llama Models
            "/llama-2": 4096,
            "/llama-3.2": 128000,
            "/llama-3.1": 128000,
            ## Llama bedrock ids
            "aws_bedrock/meta.llama3-3-70b-instruct-v1:0": 128000,
            "aws_bedrock/meta.llama3-1-70b-instruct-v1:0": 128000,
            "aws_bedrock/meta.llama3-70b-instruct-v1:0": 8000,
            "aws_bedrock/meta.llama3-2-3b-instruct-v1:0": 131000,
            "aws_bedrock/meta.llama3-2-1b-instruct-v1:0": 131000,
            "aws_bedrock/meta.llama3-1-8b-instruct-v1:0": 128000,
            "aws_bedrock/meta.llama3-8b-instruct-v1:0": 8000,
            # Ollama Models
            "ollama/llama3.1:8b": 128000,
            "ollama/llama3-groq-tool-use:8b": 128000,
        }
        # Handle None values
        if model_platform is None or model_name is None:
            return DEFAULT_MODEL_CONTEXT_WINDOW_SIZE

        return model_context_window_sizes.get(
            f"{model_platform.lower()}/{model_name.lower()}",
            DEFAULT_MODEL_CONTEXT_WINDOW_SIZE,
        )

    @staticmethod
    def get_model_config(config: RunnableConfig):
        try:
            runtime_config = BaseRuntimeConfiguration(**(config.get("configurable")))
        except ValidationError as validation_error:
            logger.debug(
                f"validation of the runtime configuration in the client request to the API Assistant agent failed: {validation_error.json()}"
            )
            return {
                "messages": [
                    AIMessage(
                        content=f"Invalid runtime configuration: {validation_error.errors()}",
                    )
                ]
            }
        model_config = runtime_config.model or {}
        return model_config

    @staticmethod
    def get_model_id_from_config(config: RunnableConfig):
        model_config = ModelService.get_model_config(config)
        model_id = model_config.get("name", settings.default_model_id)
        return model_id

    @staticmethod
    def get_model_from_config(config: RunnableConfig, **kwargs: Any):
        model_config = ModelService.get_model_config(config)
        # Use environment variables as defaults instead of hardcoded values
        model_name = model_config.get("name", settings.default_model_id)
        model_provider = model_config.get("platform", settings.default_model_platform)

        # Set default temperature if not provided
        if "temperature" not in kwargs:
            kwargs["temperature"] = 0

        model = ModelService.initialize_chat_model(
            model_id=model_name, model_provider=model_provider, **kwargs
        )
        return model
