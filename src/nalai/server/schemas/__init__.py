"""
API schemas package.

This package contains all API input/output schemas organized by HTTP resources:
- conversations: Conversation resource schemas (/api/v1/conversations/{conversation_id})
- resume_decisions: Resume decision resource schemas (/api/v1/conversations/{conversation_id}/resume-decision)
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
from .messages import (
    BaseOutputMessage,
    ContentBlock,
    HumanInputMessage,
    InputMessage,
    MessageRequest,
    MessageResponse,
    TextContent,
    ToolDecisionInputMessage,
)
from .resume_decisions import ResumeDecisionRequest, ResumeDecisionResponse

__all__ = [
    # Base schemas
    "ConversationIdPathParam",
    "ModelConfig",
    # Conversation resource schemas
    "ConversationResponse",
    "ConversationSummary",
    "LoadConversationResponse",
    "ListConversationsResponse",
    "ToolDecisionInputMessage",
    "InputMessage",
    "HumanInputMessage",
    "BaseOutputMessage",
    "MessageRequest",
    "MessageResponse",
    # Content block schemas
    "ContentBlock",
    "TextContent",
    # Resume decision resource schemas
    "ResumeDecisionRequest",
    "ResumeDecisionResponse",
    # Health resource schemas
    "HealthzResponse",
]
