"""
Core API Assistant functionality.

This module contains the main agent class, workflow definitions,
core data schemas, and agent interface.
"""

from .agent import (
    AccessDeniedError,
    Agent,
    ClientError,
    ConversationInfo,
    ConversationNotFoundError,
    Error,
    InvocationError,
    ValidationError,
)
from .factory import create_agent
from .internal.lc_agent import create_user_scoped_conversation_id
from .messages import (
    AssistantOutputMessage,
    ContentBlock,
    HumanInputMessage,
    HumanOutputMessage,
    InputMessage,
    OutputMessage,
    TextContent,
    ToolCall,
    ToolCallDecision,
)
from .runtime_config import ConfigSchema, ModelConfig
from .services import (
    APIService,
    AuditService,
    CacheService,
    CheckpointingService,
    ModelService,
)
from .streaming import (
    Event,
    InterruptChunk,
    MessageChunk,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    StreamingChunk,
    ToolCallChunk,
    ToolCallUpdateChunk,
    ToolChunk,
    UpdateChunk,
)

__all__ = [
    "create_agent",
    "Agent",
    # Runtime agent config types
    "ModelConfig",
    "ConfigSchema",
    # I/O types
    "ContentBlock",
    "TextContent",
    "InputMessage",
    "HumanInputMessage",
    "ToolCallDecision",
    "OutputMessage",
    "ConversationInfo",
    "ToolCall",
    "HumanOutputMessage",
    "AssistantOutputMessage",
    # Streaming I/O types
    "Event",
    "ResponseCreatedEvent",
    "ResponseCompletedEvent",
    "ResponseErrorEvent",
    "StreamingChunk",
    "InterruptChunk",
    "MessageChunk",
    "ToolCallChunk",
    "ToolCallUpdateChunk",
    "ToolChunk",
    "UpdateChunk",
    # Error types
    "Error",
    "AccessDeniedError",
    "ClientError",
    "ConversationNotFoundError",
    "ValidationError",
    "InvocationError",
    # Service interfaces
    "CheckpointingService",
    "CacheService",
    "ModelService",
    "APIService",
    "AuditService",
    # Utilities
    "create_user_scoped_conversation_id",
]
