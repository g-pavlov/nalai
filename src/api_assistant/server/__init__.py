"""
Server module for API Assistant.

This module contains the FastAPI application, middleware,
and route handlers for the API Assistant server.
"""


from .middleware import (
    create_log_request_middleware,
    create_user_context_middleware,
    create_auth_middleware,
    create_audit_middleware,
    get_user_context,
    is_request_processable,
)
from .models import (
    AgentInput,
    AgentInvokeRequest,
    AgentInvokeResponse,
    AgentStreamEventsRequest,
    AgentStreamRequest,
    HumanReviewRequest,
    MessageInput,
    convert_api_messages_to_langchain,
    convert_langchain_messages_to_api,
    # Utility functions
    validate_langchain_messages,
)

__all__ = [
    "AgentInvokeRequest",
    "AgentInvokeResponse",
    "AgentStreamRequest",
    "AgentStreamEventsRequest",
    "HumanReviewRequest",
    "MessageInput",
    "AgentInput",
    "validate_langchain_messages",
    "convert_api_messages_to_langchain",
    "convert_langchain_messages_to_api",
    "create_log_request_middleware",
    "create_user_context_middleware",
    "create_auth_middleware",
    "create_audit_middleware",
    "get_user_context",
    "is_request_processable",
]
