"""
API schemas package.

This package contains all API input/output schemas organized by HTTP resources:
- conversations: Conversation resource schemas (/api/v1/conversations/{conversation_id})
- health: Health check resource schemas (/healthz)
- common: Shared types and constants used across resources
"""

from .base import ConversationIdPathParam, ModelConfig
from .conversations import (
    ConversationResponse,
    ConversationSummary,
    ListConversationsResponse,
    LoadConversationResponse,
)
from .health import HealthzResponse

__all__ = [
    # Base schemas
    "ConversationIdPathParam",
    "ModelConfig",
    # Conversation resource schemas
    "ConversationResponse",
    "ConversationSummary",
    "LoadConversationResponse",
    "ListConversationsResponse",
    "BaseOutputMessage",
    "MessageRequest",
    "MessageResponse",
    # Health resource schemas
    "HealthzResponse",
]
