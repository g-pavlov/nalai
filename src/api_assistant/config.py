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

    # ===== ACCESS CONTROL CONFIGURATION =====
    
    # Auth settings
    auth_enabled: bool = Field(
        alias="AUTH_ENABLED", 
        default=True,
        description="Enable authentication and access control"
    )
    auth_provider: str = Field(
        alias="AUTH_PROVIDER", 
        default="standard",
        description="Authentication provider (standard, auth0, keycloak, etc.)"
    )
    auth_mode: str = Field(
        alias="AUTH_MODE", 
        default="client_credentials",
        description="Authentication mode (client_credentials or delegation)"
    )
    auth_validate_tokens: bool = Field(
        alias="AUTH_VALIDATE_TOKENS", 
        default=True,
        description="Enable token validation (can be disabled for externalized auth)"
    )
    auth_audit_enabled: bool = Field(
        alias="AUTH_AUDIT_ENABLED", 
        default=True,
        description="Enable access audit logging"
    )
    
    # OIDC settings
    auth_oidc_issuer: str = Field(
        alias="AUTH_OIDC_ISSUER", 
        default="",
        description="OIDC issuer URL (e.g., https://your-domain.auth0.com/)"
    )
    auth_oidc_audience: str = Field(
        alias="AUTH_OIDC_AUDIENCE", 
        default="",
        description="OIDC audience (API identifier)"
    )
    
    # Client credentials (individual environment variables)
    auth_cc_service_a_client_id: str = Field(
        alias="AUTH_CC_SERVICE_A_CLIENT_ID", 
        default="",
        description="Client ID for service A"
    )
    auth_cc_service_a_client_secret: str = Field(
        alias="AUTH_CC_SERVICE_A_CLIENT_SECRET", 
        default="",
        description="Client secret for service A"
    )
    auth_cc_service_b_client_id: str = Field(
        alias="AUTH_CC_SERVICE_B_CLIENT_ID", 
        default="",
        description="Client ID for service B"
    )
    auth_cc_service_b_client_secret: str = Field(
        alias="AUTH_CC_SERVICE_B_CLIENT_SECRET", 
        default="",
        description="Client secret for service B"
    )
    
    # Cache settings
    cache_backend: str = Field(
        alias="CACHE_BACKEND", 
        default="memory",
        description="Cache backend (memory, redis)"
    )
    cache_max_size: int = Field(
        alias="CACHE_MAX_SIZE", 
        default=1000,
        description="Maximum number of cache entries"
    )
    cache_ttl_hours: int = Field(
        alias="CACHE_TTL_HOURS", 
        default=1,
        description="Cache TTL in hours"
    )
    cache_redis_url: str = Field(
        alias="CACHE_REDIS_URL", 
        default="",
        description="Redis URL for cache backend"
    )
    
    # Checkpointing settings
    checkpointing_backend: str = Field(
        alias="CHECKPOINTING_BACKEND", 
        default="memory",
        description="Checkpointing backend (memory, file, postgres, redis)"
    )
    checkpointing_file_path: str = Field(
        alias="CHECKPOINTING_FILE_PATH", 
        default="./checkpoints",
        description="File path for file-based checkpointing"
    )
    checkpointing_postgres_url: str = Field(
        alias="CHECKPOINTING_POSTGRES_URL", 
        default="",
        description="PostgreSQL URL for checkpointing backend"
    )
    checkpointing_redis_url: str = Field(
        alias="CHECKPOINTING_REDIS_URL", 
        default="",
        description="Redis URL for checkpointing backend"
    )
    
    # Audit settings
    audit_backend: str = Field(
        alias="AUDIT_BACKEND", 
        default="memory",
        description="Audit backend (memory, external)"
    )
    audit_max_entries: int = Field(
        alias="AUDIT_MAX_ENTRIES", 
        default=10000,
        description="Maximum number of audit log entries"
    )
    audit_external_url: str = Field(
        alias="AUDIT_EXTERNAL_URL", 
        default="",
        description="External audit service URL"
    )
    
    # PII Protection settings
    audit_mask_pii: bool = Field(
        alias="AUDIT_MASK_PII", 
        default=True,
        description="Enable PII masking in audit logs"
    )
    audit_mask_emails: bool = Field(
        alias="AUDIT_MASK_EMAILS", 
        default=True,
        description="Mask email addresses in audit logs"
    )
    audit_mask_names: bool = Field(
        alias="AUDIT_MASK_NAMES", 
        default=True,
        description="Mask personal names in audit logs"
    )
    audit_mask_ip_addresses: bool = Field(
        alias="AUDIT_MASK_IP_ADDRESSES", 
        default=False,
        description="Mask IP addresses in audit logs (disabled by default for security)"
    )
    
    # Thread access control settings
    thread_access_control_backend: str = Field(
        alias="THREAD_ACCESS_CONTROL_BACKEND", 
        default="memory",
        description="Thread access control backend (memory, redis)"
    )

    class Config:
        env_file = dotenv.find_dotenv()
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra environment variables

    @property
    def client_credentials(self) -> dict[str, dict]:
        """Build client credentials from individual env vars (transparent configuration)"""
        creds = {}
        if self.auth_cc_service_a_client_id:
            creds["service_a"] = {
                "client_id": self.auth_cc_service_a_client_id,
                "client_secret": self.auth_cc_service_a_client_secret
            }
        if self.auth_cc_service_b_client_id:
            creds["service_b"] = {
                "client_id": self.auth_cc_service_b_client_id,
                "client_secret": self.auth_cc_service_b_client_secret
            }
        return creds


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
