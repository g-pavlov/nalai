import os
from typing import Any

import dotenv
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings

OPENAI_GPT_41 = "gpt-4.1"
OPENAI_PLATFORM = "openai"


class Settings(BaseSettings):
    """Global application settings loaded from environment variables.
    Provides centralized configuration management with sensible defaults
    for model settings, AWS credentials, API behavior, and logging.
    """

    # ===== SERVER CONFIGURATION =====
    cors_allow_origins: str = Field(
        alias="CORS_ALLOW_ORIGINS",
        default="http://localhost:3001,http://127.0.0.1:3001",
        description="Comma-separated list of allowed CORS origins for the API Assistant UI.",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        if not self.cors_allow_origins.strip():
            return []
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]

    # ===== LOGGING CONFIGURATION =====
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

    # ===== AUDIT TRAIL CONFIGURATION =====
    audit_backend: str = Field(
        alias="AUDIT_BACKEND",
        default="memory",
        description="Audit backend (memory, external)",
    )
    audit_max_entries: int = Field(
        alias="AUDIT_MAX_ENTRIES",
        default=10000,
        description="Maximum number of audit log entries",
    )
    audit_external_url: str = Field(
        alias="AUDIT_EXTERNAL_URL", default="", description="External audit service URL"
    )
    # PII Protection settings
    audit_mask_pii: bool = Field(
        alias="AUDIT_MASK_PII",
        default=True,
        description="Enable PII masking in audit logs",
    )
    audit_mask_emails: bool = Field(
        alias="AUDIT_MASK_EMAILS",
        default=True,
        description="Mask email addresses in audit logs",
    )
    audit_mask_names: bool = Field(
        alias="AUDIT_MASK_NAMES",
        default=True,
        description="Mask personal names in audit logs",
    )
    audit_mask_ip_addresses: bool = Field(
        alias="AUDIT_MASK_IP_ADDRESSES",
        default=False,
        description="Mask IP addresses in audit logs (disabled by default for security)",
    )

    # ===== AUTH CONFIGURATION =====
    auth_enabled: bool = Field(
        alias="AUTH_ENABLED",
        default=True,
        description="Enable authentication and access control",
    )
    auth_provider: str = Field(
        alias="AUTH_PROVIDER",
        default="standard",
        description="Authentication provider (standard, auth0, keycloak, etc.)",
    )
    auth_mode: str = Field(
        alias="AUTH_MODE",
        default="client_credentials",
        description="Authentication mode (client_credentials or delegation)",
    )
    auth_validate_tokens: bool = Field(
        alias="AUTH_VALIDATE_TOKENS",
        default=True,
        description="Enable token validation (can be disabled for externalized auth)",
    )
    auth_audit_enabled: bool = Field(
        alias="AUTH_AUDIT_ENABLED",
        default=True,
        description="Enable access audit logging",
    )
    # OIDC settings
    auth_oidc_issuer: str = Field(
        alias="AUTH_OIDC_ISSUER",
        default="",
        description="OIDC issuer URL (e.g., https://your-domain.auth0.com/)",
    )
    auth_oidc_audience: str = Field(
        alias="AUTH_OIDC_AUDIENCE",
        default="",
        description="OIDC audience (API identifier)",
    )

    # Client credentials configuration
    auth_client_credentials: dict[str, Any] = Field(
        alias="AUTH_CLIENT_CREDENTIALS",
        default={},
        description="Client credentials for API services",
    )

    # ===== PROMPT CACHE CONFIGURATION =====
    cache_enabled: bool = Field(
        alias="CACHE_ENABLED",
        default=True,
        description="Enable response caching to reduce LLM calls (default: True)",
    )
    cache_max_size: int = Field(
        alias="CACHE_MAX_SIZE",
        default=1000,
        description="Maximum number of cache entries (default: 1000)",
    )
    cache_ttl_seconds: int = Field(
        alias="CACHE_TTL_SECONDS",
        default=1800,
        description="Cache time-to-live in seconds (default: 1800 = 30 minutes)",
    )
    cache_backend: str = Field(
        alias="CACHE_BACKEND",
        default="memory",
        description="Cache backend (memory only)",
    )
    cache_tool_calls: bool = Field(
        alias="CACHE_TOOL_CALLS",
        default=False,
        description="Cache tool calls (default: False - tool results may change over time)",
    )
    cache_similarity_threshold: float = Field(
        alias="CACHE_SIMILARITY_THRESHOLD",
        default=0.8,
        description="Similarity threshold for semantic cache matching (0.0-1.0)",
    )
    cache_similarity_enabled: bool = Field(
        alias="CACHE_SIMILARITY_ENABLED",
        default=True,
        description="Enable similarity-based cache matching (default: True)",
    )

    # ===== CHECKPOINTING CONFIGURATION =====
    checkpointing_backend: str = Field(
        alias="CHECKPOINTING_BACKEND",
        default="memory",
        description="Checkpointing backend (memory, file, postgres, redis)",
    )
    checkpointing_file_path: str = Field(
        alias="CHECKPOINTING_FILE_PATH",
        default="./checkpoints",
        description="File path for file-based checkpointing",
    )
    checkpointing_postgres_url: str = Field(
        alias="CHECKPOINTING_POSTGRES_URL",
        default="",
        description="PostgreSQL URL for checkpointing backend",
    )
    checkpointing_redis_url: str = Field(
        alias="CHECKPOINTING_REDIS_URL",
        default="",
        description="Redis URL for checkpointing backend",
    )

    # ===== MODEL CONFIGURATION =====
    default_model_id: str = Field(
        alias="MODEL_ID",
        default=OPENAI_GPT_41,
        description=f"Default model ID for API calls (default: {OPENAI_GPT_41})",
    )
    default_model_platform: str = Field(
        alias="MODEL_PLATFORM",
        default=OPENAI_PLATFORM,
        description=f"Default model platform (default: {OPENAI_PLATFORM})",
        examples=["aws_bedrock", "ollama"],
    )
    default_model_temperature: float = Field(
        alias="MODEL_TEMPERATURE",
        default=0.0,
        description="Default model temperature for response generation",
    )
    default_model_max_tokens: int | None = Field(
        alias="MODEL_MAX_TOKENS",
        default=None,
        description="Maximum tokens for model responses (optional)",
    )
    cross_process_rate_limiter_enabled: bool = Field(
        alias="CROSS_PROCESS_RATE_LIMITER_ENABLED",
        default=False,
        description="Enable cross-process rate limiting for LLM API calls (useful for parallel testing)",
    )

    # Ollama configuration
    ollama_base_url: str = Field(
        alias="NALAI_OLLAMA_BASE_URL",
        default="http://localhost:11434",
        description="Base URL for Ollama service",
    )

    # AWS Bedrock configuration
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

    # ===== CONVERSATION CONFIGURATION =====
    chat_thread_compression_trigger_percentage: int = Field(
        alias="CHAT_THREAD_COMPRESSION_TRIGGER_PERCENTAGE",
        default=95,
        description="Context window saturation percentage that triggers conversation history compression",
    )

    # ===== THREAD ACCESS CONTROL CONFIGURATION =====
    chat_thread_access_control_backend: str = Field(
        alias="CHAT_THREAD_ACCESS_CONTROL_BACKEND",
        default="memory",
        description="Thread access control backend (memory, redis)",
    )

    # ===== API DOCS CONFIGURATION =====
    api_specs_path: str = Field(
        alias="API_SPECS_PATH",
        default="data/api_specs",
        description="Directory containing API specification files",
    )

    # ===== API VERSION CONFIGURATION =====
    api_version: str = Field(
        alias="API_VERSION",
        default="v1",
        description="API version for endpoint prefixing",
    )

    @property
    def api_prefix(self) -> str:
        """Get API prefix based on version."""
        return f"/api/{self.api_version}"

    # ===== TOOLS CONFIGURATION =====
    api_calls_enabled: bool = Field(
        alias="API_CALLS_ENABLED",
        default=False,
        description="Enable actual HTTP API calls (default: False for safety)",
    )
    api_calls_allowed_urls: str = Field(
        alias="API_CALLS_ALLOWED_URLS",
        default="http://ecommerce-mock:8000,http://localhost:8000,http://localhost:8001",
        description="Comma-separated list of allowed base URLs for API calls when enabled",
    )

    @property
    def api_calls_allowed_urls_list(self) -> list[str]:
        """Get allowed API URLs as a list."""
        if not self.api_calls_allowed_urls.strip():
            return []
        return [
            url.strip() for url in self.api_calls_allowed_urls.split(",") if url.strip()
        ]

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
        print(settings.model_dump_json(indent=4))
    except ValidationError as e:
        print(f"Configuration error: {e}")
