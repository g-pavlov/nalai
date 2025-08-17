"""
API schemas package.

This package contains all API input/output schemas organized by HTTP resources:
- conversations: Conversation resource schemas (/api/v1/conversations/{conversation_id})
- resume_decisions: Resume decision resource schemas (/api/v1/conversations/{conversation_id}/resume-decision)
- health: Health check resource schemas (/healthz)
- common: Shared types and constants used across resources
"""

from .conversations import (
    AIMessageInput,
    ConversationRequest,
    ConversationResponse,
    ConversationSummary,
    HumanMessageInput,
    ListConversationsResponse,
    LoadConversationResponse,
    MessageInput,
    MessageInputUnion,
    ToolMessageInput,
)
from .health import HealthzResponse
from .resume_decisions import ResumeDecisionRequest, ResumeDecisionResponse

__all__ = [
    # Conversation resource schemas
    "ConversationRequest",
    "ConversationResponse",
    "ConversationSummary",
    "LoadConversationResponse",
    "ListConversationsResponse",
    "MessageInput",
    "HumanMessageInput",
    "AIMessageInput",
    "ToolMessageInput",
    "MessageInputUnion",
    # Resume decision resource schemas
    "ResumeDecisionRequest",
    "ResumeDecisionResponse",
    # Health resource schemas
    "HealthzResponse",
]
