import os
import dotenv
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings

CLAUDE_SONNET_3_5 = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
AWS_BEDROCK_PLATFORM = "aws_bedrock"

class Settings(BaseSettings):
    """Global application settings loaded from environment variables.
    Provides centralized configuration management with sensible defaults
    for model settings, AWS credentials, API behavior, and logging.
    """

    # Model configuration
    default_model_max_tokens: int | None = Field(
        alias="MODEL_MAX_TOKENS",
        default=None,
        description="Maximum tokens for model responses (optional)",
    )

    # AWS credentials (optional - can use AWS profile instead)
    aws_access_key_id: str | None = Field(
        alias="AWS_ACCESS_KEY_ID",
        default=None,
        description="AWS access key ID (optional if using AWS profile)",
    )
    aws_secret_access_key: str | None = Field(
        alias="AWS_SECRET_ACCESS_KEY",
        default=None,
        description="AWS secret access key (optional if using AWS profile)",
    )

    # Model defaults
    default_model_id: str = Field(
        alias="MODEL_ID",
        default=CLAUDE_SONNET_3_5,
        description=f"Default model ID for API calls (default: {CLAUDE_SONNET_3_5})",
    )
    default_model_platform: str = Field(
        alias="MODEL_PLATFORM",
        default=AWS_BEDROCK_PLATFORM,
        description=f"Default model platform (default: {AWS_BEDROCK_PLATFORM})",
        examples=["aws_bedrock", "ollama"],
    )
    default_model_temperature: float = Field(
        alias="MODEL_TEMPERATURE",
        default=0.0,
        description="Default model temperature for response generation",
    )

    # AWS configuration
    aws_default_region: str = Field(
        alias="AWS_DEFAULT_REGION",
        default="us-east-1",
        description="AWS default region for Bedrock services",
    )
    aws_bedrock_retry_max_attempts: int = Field(
        alias="AWS_BEDROCK_RETRY_MAX_ATTEMPTS",
        default=4,
        description="Maximum retry attempts for AWS Bedrock API calls",
    )
    
    # Ollama configuration
    ollama_base_url: str = Field(
        alias="OLLAMA_BASE_URL",
        default="http://localhost:11434",
        description="Base URL for Ollama service",
    )

    # API behavior settings
    enable_api_calls: bool = Field(
        alias="ENABLE_API_CALLS",
        default=False,
        description="Enable actual HTTP API calls (default: False for safety)",
    )
    api_calls_base_url: str = Field(
        alias="API_CALLS_BASE_URL",
        default="example.com",
        description="Base URL for API calls when enabled",
    )
    history_compression_trigger_percentage: int = Field(
        alias="HISTORY_COMPRESSION_TRIGGER_PERCENTAGE",
        default=95,
        description="Context window saturation percentage that triggers conversation history compression",
    )
    enable_cross_process_rate_limiter: bool = Field(
        alias="ENABLE_CROSS_PROCESS_RATE_LIMITER",
        default=False,
        description="Enable cross-process rate limiting for LLM API calls (useful for parallel testing)",
    )

    # Cache settings
    enable_caching: bool = Field(
        alias="ENABLE_CACHING",
        default=True,
        description="Enable response caching to reduce LLM calls (default: True)",
    )
    cache_max_size: int = Field(
        alias="CACHE_MAX_SIZE",
        default=1000,
        description="Maximum number of cache entries (default: 1000)",
    )
    cache_ttl_hours: int = Field(
        alias="CACHE_TTL_HOURS",
        default=1,
        description="Cache time-to-live in hours (default: 1)",
    )

    # Development settings
    disable_auth: bool = Field(
        alias="DISABLE_AUTH",
        default=False,
        description="Disable authentication for development (use with caution)",
    )

    # Data paths
    api_specs_path: str = Field(
        alias="API_SPECS_PATH",
        default="data/api_specs",
        description="Directory containing API specification files",
    )
    
    # Logging configuration
    logging_config_path: str = Field(
        alias="LOGGING_CONFIG_PATH",
        default="logging.yaml",
        description="Path to YAML logging configuration file",
    )
    logging_level: str = Field(
        alias="LOGGING_LEVEL",
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    logging_directory: str = Field(
        alias="LOGGING_DIRECTORY",
        default="logs",
        description="Directory for log file output",
    )

    class Config:
        env_file = dotenv.find_dotenv()
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra environment variables


settings = Settings()

class BaseRuntimeConfiguration(BaseModel):
    """Runtime configuration for agent execution.
    Handles model configuration and runtime settings that can be
    modified per request without affecting global settings.
    """

    @model_validator(mode="before")
    @classmethod
    def exclude_none_values(cls, values: dict) -> dict:
        """Remove None values from configuration input.
        Ensures clean configuration data by filtering out None values
        before validation, preventing issues with optional fields.
        """
        return {k: v for k, v in values.items() if v is not None}

    model: dict[str, str] | None = Field(
        default_factory=lambda: {
            "name": os.getenv("MODEL_ID", settings.default_model_id),
            "provider": os.getenv("MODEL_PLATFORM", settings.default_model_platform),
        },
        metadata={
            "description": "The model configuration, including the model's name and platform. "
            "Example: {'name': 'llama3.1:8b', 'platform': 'ollama'}."
        },
    )


if __name__ == "__main__":
    load_dotenv()

    try:
        settings = Settings()
        print(settings.dict())
    except ValidationError as e:
        print(f"Configuration error: {e}")
