"""Factory methods and configurations for rate limiters."""

import logging

from langchain_core.rate_limiters import BaseRateLimiter
from pydantic import ValidationError

from ...config import settings
from .interfaces import (
    RateLimiterConfig,
    RateLimiterFactoryInterface,
    RateLimiterInterface,
)
from .utils import get_default_rate_limiter_class

logger = logging.getLogger(__name__)


class DefaultRateLimiterFactory(RateLimiterFactoryInterface):
    """Default implementation of the rate limiter factory."""

    def __init__(
        self,
        rate_limiter_class: type[BaseRateLimiter] | None = None,
        config_overrides: dict[str, RateLimiterConfig] | None = None,
    ):
        # Use FileLockRateLimiter if explicitly enabled or in test environment
        if settings.enable_cross_process_rate_limiter:
            from .rate_limiters import FileLockRateLimiter

            self.rate_limiter_class = FileLockRateLimiter
        else:
            self.rate_limiter_class = (
                rate_limiter_class or get_default_rate_limiter_class()
            )
        self.config_overrides = config_overrides or {}

    def create_rate_limiter(
        self, model_platform: str, model: str, config: RateLimiterConfig
    ) -> RateLimiterInterface | None:
        """
        Create a rate limiter instance for a specific model.

        Args:
            model_platform: The platform (e.g., aws_bedrock, ollama)
            model: The model identifier
            config: Rate limiter configuration

        Returns:
            Optional[RateLimiterInterface]: Rate limiter instance or None if creation fails
        """
        try:
            # Apply any configuration overrides
            model_config_key = f"{model_platform}/{model}"
            if model_config_key in self.config_overrides:
                config = self.config_overrides[model_config_key]

            # Remove limiter_type from the config before passing to rate limiter
            rate_limiter_config = config.model_dump(exclude_unset=True)
            rate_limiter_config.pop("limiter_type", None)

            rate_limiter_instance = self.rate_limiter_class(**rate_limiter_config)
            logger.debug(
                f"Created {self.rate_limiter_class.__name__} for {model_platform}/{model} "
                f"with config: {config}"
            )
            return rate_limiter_instance
        except ValidationError as validation_error:
            logger.error(
                f"Invalid rate limiter configuration for {model_platform}/{model}: {str(validation_error)}"
            )
            return None
        except Exception as error:
            logger.error(
                f"Failed to create rate limiter for {model_platform}/{model}: {str(error)}"
            )
            return None


# Default factory instance
default_factory = DefaultRateLimiterFactory()

# Model-specific rate limiting configurations
RATE_LIMITERS_CONFIG: dict[str, RateLimiterConfig] = {
    # Claude models
    "aws_bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0": RateLimiterConfig(
        requests_per_second=1.5,  # 100 RPM (~1.67 RPS)
        check_every_n_seconds=0.1,  # 10 times / second
        max_bucket_size=10,  # 2 requests at burst
    ),
    "aws_bedrock/anthropic.claude-sonnet-20240620-v1:0": RateLimiterConfig(
        requests_per_second=1.5,  # 100 RPM (~1.67 RPS)
        check_every_n_seconds=0.1,  # 10 times / second
        max_bucket_size=10,  # 2 requests at burst
    ),
    # Ollama Models
    # Removed: "ollama/cnjack/mistral-samll-3.1:24b-it-q4_k_s": RateLimiterConfig(
    #     requests_per_second=2.0,  # 120 RPM for local Ollama
    #     check_every_n_seconds=0.1,  # 10 times / second
    #     max_bucket_size=5,  # 5 requests at burst
    # ),  # Model doesn't support tool calling
    "ollama/llama3.1:8b": RateLimiterConfig(
        requests_per_second=3.0,  # 180 RPM for local Ollama (higher for smaller model)
        check_every_n_seconds=0.1,  # 10 times / second
        max_bucket_size=10,  # 10 requests at burst
    ),

    # Add more model configurations as needed
    "default": RateLimiterConfig(
        requests_per_second=1.0, max_bucket_size=1, check_every_n_seconds=1.0
    ),
}


def get_rate_limiter_config(model_platform: str, model: str) -> RateLimiterConfig:
    """
    Get rate limiter configuration for a specific model.
    Falls back to default configuration if model-specific config not found.

    Args:
        model_platform: The platform (e.g., aws_bedrock, ollama)
        model: The model identifier

    Returns:
        RateLimiterConfig containing rate limiter configuration
    """
    model_config_key = f"{model_platform}/{model}"
    config = RATE_LIMITERS_CONFIG.get(model_config_key)

    if not config:
        logger.info(
            f"No specific rate limit config found for {model_config_key}. "
            "Using default configuration."
        )
        config = RATE_LIMITERS_CONFIG["default"]

    return config


def create_model_rate_limiter(
    model_platform: str, model: str, factory: RateLimiterFactoryInterface | None = None
) -> RateLimiterInterface | None:
    """
    Create a rate limiter for the specified model.

    Args:
        model_platform: The platform (e.g., aws_bedrock, ollama)
        model: The model identifier
        factory: Optional rate limiter factory to use

    Returns:
        Optional[RateLimiterInterface]: Rate limiter instance or None if creation fails
    """
    config = get_rate_limiter_config(model_platform, model)
    factory = factory or default_factory
    return factory.create_rate_limiter(model_platform, model, config)
