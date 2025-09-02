"""
Route handlers for API Assistant server.

This module contains FastAPI route handlers for basic endpoints
and conversation endpoints with access control integration.
"""

import functools
import logging

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ..config import settings
from ..core import Agent
from ..core.agent import (
    AccessDeniedError,
    ClientError,
    ConversationNotFoundError,
    InvocationError,
    ValidationError,
)
from .json_serializer import serialize_conversation
from .runtime_config import create_runtime_config
from .schemas import (
    ConversationIdPathParam,
    ConversationSummary,
    ListConversationsResponse,
    LoadConversationResponse,
)

logger = logging.getLogger("nalai")

# OpenAPI configuration
OPENAPI_TAGS = [
    {
        "name": "Agent",
        "description": "Conversation interaction endpoints for API v1",
    },
    {
        "name": "Server",
        "description": "Server system health and utility endpoints",
    },
    {
        "name": "Conversations",
        "description": "Conversation management endpoints for API v1",
    },
]

# Application metadata
APP_TITLE = "API Assistant"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "AI Agent with API Integration"


class SSEStreamingResponse(StreamingResponse):
    """Custom response class for Server-Sent Events with proper media type."""

    media_type = "text/event-stream"


# Response examples for OpenAPI documentation
streaming_response_examples = {
    "conversation": {
        "example": """data: {"messages": [{"content": "Hello", "type": "ai"}], "selected_apis": [], "cache_miss": null}

data: {"messages": [{"content": "Processing your request...", "type": "ai"}], "selected_apis": [{"title": "Ecommerce API", "version": "1.0"}], "cache_miss": "miss"}

"""
    },
    "resume_decision": {
        "example": """data: {"messages": [{"content": "Resuming...", "type": "ai"}], "selected_apis": [], "cache_miss": null}

data: {"messages": [{"content": "Tool execution completed", "type": "ai"}], "selected_apis": [], "cache_miss": null}

"""
    },
}

# Reusable response components
conversation_id_header = {
    "X-Conversation-ID": {
        "description": "Conversation ID for conversation management and resume capability",
        "schema": {"type": "string"},
    }
}

success_response_description = """
Successful Response.

The response type is determined by the media type in the **Accept** request header:
- **Server-Side Event Streaming**: `text/event-stream`
- **JSON**: `application/json`

The response **X-Conversation-ID** header contains the conversation ID for conversation management and resume capability.
"""


def handle_agent_errors(func):
    """Decorator to handle agent errors and convert to HTTP responses."""

    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.message) from e
        except AccessDeniedError as e:
            raise HTTPException(status_code=403, detail=e.message) from e
        except ConversationNotFoundError as e:
            raise HTTPException(status_code=404, detail=e.message) from e
        except ClientError as e:
            # Client errors (4xx) should be returned with their original status and message
            raise HTTPException(status_code=e.http_status, detail=e.message) from e
        except InvocationError as e:
            logger.error(f"Agent error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    # Preserve the original function signature for FastAPI
    return functools.wraps(func)(wrapper)


def create_conversations_api(app: FastAPI, agent: Agent) -> None:
    """Create conversation state management endpoint routes."""

    # Load conversation endpoint
    @app.get(
        f"{settings.api_prefix}/conversations/{{conversation_id}}",
        response_model=LoadConversationResponse,
        tags=["Conversations"],
        summary="Load Conversation",
        description="Load a previous conversation state by conversation ID. Returns conversation messages and metadata. The conversation_id must be a valid UUID4.",
        responses={
            200: {
                "description": "Conversation loaded successfully",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/LoadConversationResponse"
                        }
                    },
                },
            },
            404: {
                "description": "Conversation not found",
                "content": {
                    "application/json": {
                        "example": {"detail": "Conversation not found"}
                    },
                },
            },
            403: {
                "description": "Access denied to conversation",
                "content": {
                    "application/json": {
                        "example": {"detail": "Access denied to conversation"}
                    },
                },
            },
        },
    )
    @handle_agent_errors
    async def load_conversation(
        conversation_id: str, req: Request
    ) -> LoadConversationResponse:
        """
        Load conversation endpoint that returns conversation state and metadata.
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id format only (access validation done in core)
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        agent_config = create_runtime_config(req, conversation_id)
        messages, conversation_info = await agent.load_conversation(
            conversation_id, agent_config
        )

        # Convert to API output format
        response = serialize_conversation(conversation_info, messages)

        return response

    # List conversations endpoint
    @app.get(
        f"{settings.api_prefix}/conversations",
        response_model=ListConversationsResponse,
        tags=["Conversations"],
        summary="List Conversations",
        description="List all conversations that the current user has access to. Returns conversation IDs, metadata, and previews.",
        responses={
            200: {
                "description": "Conversations listed successfully",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ListConversationsResponse"
                        }
                    },
                },
            },
            401: {
                "description": "Authentication required",
                "content": {
                    "application/json": {
                        "example": {"detail": "Authentication required"}
                    },
                },
            },
        },
    )
    @handle_agent_errors
    async def list_conversations(req: Request) -> ListConversationsResponse:
        """
        List conversations endpoint that returns all conversations accessible to the current user.
        """
        agent_config = create_runtime_config(req)
        conversation_infos = await agent.list_conversations(agent_config)

        conversation_summaries = [
            ConversationSummary(
                conversation_id=info.conversation_id,
                created_at=info.created_at,
                last_updated=info.last_accessed,  # Map last_accessed to last_updated for API
                preview=info.preview[:256]
                if info.preview
                else None,  # Truncate preview to 256 chars
                metadata=getattr(info, "metadata", {}),
            )
            for info in conversation_infos
        ]

        return ListConversationsResponse(
            conversations=conversation_summaries,
            total_count=len(conversation_summaries),
        )

    # Delete conversation endpoint
    @app.delete(
        f"{settings.api_prefix}/conversations/{{conversation_id}}",
        tags=["Conversations"],
        summary="Delete Conversation",
        description="Delete a conversation by ID. This will permanently remove the conversation and all its data. The conversation_id must be a valid UUID4.",
        responses={
            204: {
                "description": "Conversation deleted successfully",
            },
            404: {
                "description": "Conversation not found",
                "content": {
                    "application/json": {
                        "example": {"detail": "Conversation not found"}
                    },
                },
            },
            403: {
                "description": "Access denied to conversation",
                "content": {
                    "application/json": {
                        "example": {"detail": "Access denied to conversation"}
                    },
                },
            },
        },
    )
    @handle_agent_errors
    async def delete_conversation(conversation_id: str, req: Request) -> Response:
        """
        Delete conversation endpoint that removes conversation data and access control records.
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id format only (access validation done in core)
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        agent_config = create_runtime_config(req, conversation_id)
        deleted = await agent.delete_conversation(conversation_id, agent_config)

        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return Response(status_code=204)
