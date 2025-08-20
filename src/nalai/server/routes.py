"""
Route handlers for API Assistant server.

This module contains FastAPI route handlers for basic endpoints
and conversation endpoints with access control integration.
"""

import json
import logging
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ..config import settings
from ..core import Agent
from ..core.agent import (
    AccessDeniedError,
    ConversationNotFoundError,
    InvocationError,
    ResumeDecision,
    ValidationError,
)
from .runtime_config import create_runtime_config
from .schemas import (
    ConversationIdPathParam,
    ConversationRequest,
    ConversationResponse,
    ConversationSummary,
    HealthzResponse,
    ListConversationsResponse,
    LoadConversationResponse,
    ResumeDecisionRequest,
    ResumeDecisionResponse,
)
from .streaming import serialize_event, serialize_to_sse

logger = logging.getLogger("nalai")

# OpenAPI configuration
OPENAPI_TAGS = [
    {
        "name": "Conversation API v1",
        "description": "Conversation interaction endpoints for API v1",
    },
    {
        "name": "System",
        "description": "System health and utility endpoints",
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


def create_basic_routes(app: FastAPI) -> None:
    """Create basic endpoint routes."""

    @app.get("/", include_in_schema=False)
    async def redirect_root_to_docs() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/ui", include_in_schema=False)
    async def redirect_ui_to_index() -> RedirectResponse:
        return RedirectResponse("/ui/index.html")

    @app.get("/healthz", tags=["System"])
    async def healthz() -> HealthzResponse:
        return HealthzResponse(status="Healthy")

    # TODO: Add /metrics endpoint for future metrics collection
    # @app.get("/metrics")
    # async def metrics() -> dict[str, object]:
    #     return {"metrics": "to be implemented"}


def get_conversation_headers(conversation_id: str) -> dict[str, str]:
    """Get standard conversation response headers."""
    return {"X-Conversation-ID": conversation_id}


def is_streaming_request(req: Request) -> bool:
    """Check if the request prefers streaming response."""
    accept_header = req.headers.get("accept", "text/event-stream")
    return "text/event-stream" in accept_header


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
        except InvocationError as e:
            logger.error(f"Agent error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    # Preserve the original function signature for FastAPI
    import functools

    return functools.wraps(func)(wrapper)


def create_conversation_routes(
    app: FastAPI,
    agent: Agent,
    *,
    serialize_event: Callable[[object], object] = serialize_event,
) -> None:
    """Create conversation endpoint routes."""

    # Create new conversation endpoint
    @app.post(
        f"{settings.api_prefix}/conversations",
        response_model=ConversationResponse,
        tags=["Conversation API v1"],
        summary="Create New Conversation",
        description="Create a new conversation. Accepts messages and returns agent response in a conversation.",
        responses={
            200: {
                "description": success_response_description,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ConversationResponse"}
                    },
                    "text/event-stream": streaming_response_examples["conversation"],
                },
                "headers": conversation_id_header,
            },
        },
    )
    @handle_agent_errors
    async def create_conversation(
        request: ConversationRequest, req: Request
    ) -> ConversationResponse | StreamingResponse:
        """
        Create new conversation endpoint that handles both JSON and streaming responses.
        Use Accept: text/event-stream header for streaming response.
        """
        # Convert input to LangChain messages
        messages = request.to_langchain_messages()
        agent_config = create_runtime_config(req)

        if is_streaming_request(req):
            # Get stream and conversation info - let agent handle conversation creation
            stream_gen, conversation_info = await agent.chat_streaming(
                messages,
                None,  # Let agent create new conversation
                agent_config,
            )

            async def generate():
                async for event in stream_gen:
                    yield serialize_to_sse(event, lambda x: x)

            response = SSEStreamingResponse(generate())

            # Set headers after creating the response
            if conversation_info.conversation_id:
                response.headers["X-Conversation-ID"] = (
                    conversation_info.conversation_id
                )
                logger.info(
                    f"Set X-Conversation-ID header: {conversation_info.conversation_id}"
                )
            else:
                logger.warning("No conversation_id generated")

            return response
        else:
            # Get messages and conversation info
            result_messages, conversation_info = await agent.chat(
                messages, None, agent_config
            )
            serialized_result = serialize_event(result_messages)
            return Response(
                content=json.dumps({"output": serialized_result}),
                media_type="application/json",
                headers=get_conversation_headers(conversation_info.conversation_id),
            )

    # Continue existing conversation endpoint
    @app.post(
        f"{settings.api_prefix}/conversations/{{conversation_id}}",
        response_model=ConversationResponse,
        tags=["Conversation API v1"],
        summary="Continue Conversation",
        description="Continue an existing conversation. Accepts messages and returns agent response in a conversation. The conversation_id must be a valid UUID4.",
        responses={
            200: {
                "description": success_response_description,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ConversationResponse"}
                    },
                    "text/event-stream": streaming_response_examples["conversation"],
                },
                "headers": conversation_id_header,
            },
        },
    )
    @handle_agent_errors
    async def continue_conversation(
        conversation_id: str, request: ConversationRequest, req: Request
    ) -> ConversationResponse | StreamingResponse:
        """
        Continue conversation endpoint that handles both streaming and non-streaming responses.
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id format only (access validation done in core)
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        # Convert input to LangChain messages
        messages = request.to_langchain_messages()
        agent_config = create_runtime_config(req, conversation_id)

        if is_streaming_request(req):
            # Get stream and conversation info
            stream_gen, conversation_info = await agent.chat_streaming(
                messages, conversation_id, agent_config
            )

            async def generate():
                async for event in stream_gen:
                    yield serialize_to_sse(event, lambda x: x)

            response = SSEStreamingResponse(generate())
            response.headers["X-Conversation-ID"] = conversation_info.conversation_id
            return response
        else:
            # Get messages and conversation info
            result_messages, conversation_info = await agent.chat(
                messages, conversation_id, agent_config
            )
            serialized_result = serialize_event(result_messages)
            return Response(
                content=json.dumps({"output": serialized_result}),
                media_type="application/json",
                headers=get_conversation_headers(conversation_info.conversation_id),
            )

    # Load conversation endpoint
    @app.get(
        f"{settings.api_prefix}/conversations/{{conversation_id}}",
        response_model=LoadConversationResponse,
        tags=["Conversation API v1"],
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

        # Convert BaseMessage objects to MessageInputUnion for API response
        api_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                api_messages.append({"type": "human", "content": msg.content})
            elif isinstance(msg, AIMessage):
                api_messages.append(
                    {
                        "type": "ai",
                        "content": msg.content,
                        "tool_calls": msg.tool_calls
                        if hasattr(msg, "tool_calls")
                        else None,
                    }
                )
            elif isinstance(msg, ToolMessage):
                api_messages.append(
                    {
                        "type": "tool",
                        "content": msg.content,
                        "name": msg.name,
                        "tool_call_id": msg.tool_call_id,
                    }
                )

        return LoadConversationResponse(
            conversation_id=conversation_info.conversation_id,
            messages=api_messages,
            created_at=conversation_info.created_at,
            last_accessed=conversation_info.last_accessed,
            status=conversation_info.status,
        )

    # List conversations endpoint
    @app.get(
        f"{settings.api_prefix}/conversations",
        response_model=ListConversationsResponse,
        tags=["Conversation API v1"],
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
                preview=info.preview,
                metadata=getattr(info, "metadata", {}),
            )
            for info in conversation_infos
        ]

        return ListConversationsResponse(
            conversations=conversation_summaries,
            total_count=len(conversation_summaries),
        )

    # Resume decision endpoint
    @app.post(
        f"{settings.api_prefix}/conversations/{{conversation_id}}/resume-decision",
        response_model=ResumeDecisionResponse,
        tags=["Conversation API v1"],
        summary="Handle Resume Decision",
        description="""Resume a conversation workflow that was interrupted for tool execution approval with a decision. An interface for implementing human-in-the-loop.
        Use the conversation ID of the interrupted workflow conversation to resume it. The conversation_id must be a valid UUID4.
        """,
        responses={
            200: {
                "description": success_response_description,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ResumeDecisionResponse"
                        }
                    },
                    "text/event-stream": streaming_response_examples["resume_decision"],
                },
                "headers": conversation_id_header,
            },
        },
    )
    @handle_agent_errors
    async def resume_decision(
        conversation_id: str, request: ResumeDecisionRequest, req: Request
    ) -> ResumeDecisionResponse | StreamingResponse:
        """
        Resume decision endpoint that handles both JSON and streaming responses.
        Use Accept: text/event-stream header for streaming response.
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id format only (access validation done in core)
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        streaming = is_streaming_request(req)
        # Convert API request to core ResumeDecision model
        resume_decision = ResumeDecision(**request.to_internal())
        agent_config = create_runtime_config(req, conversation_id)

        if streaming:
            # Get stream and conversation info
            stream_gen, conversation_info = await agent.resume_interrupted_streaming(
                resume_decision,
                conversation_id,
                agent_config,
            )

            async def generate():
                async for event in stream_gen:
                    yield serialize_to_sse(event, lambda x: x)

            response = SSEStreamingResponse(generate())
            response.headers["X-Conversation-ID"] = conversation_info.conversation_id
            return response
        else:
            # Get messages and conversation info
            result_messages, conversation_info = await agent.resume_interrupted(
                resume_decision, conversation_id, agent_config
            )
            serialized_result = serialize_event(result_messages)
            return Response(
                content=json.dumps({"output": serialized_result}),
                media_type="application/json",
                headers=get_conversation_headers(conversation_info.conversation_id),
            )

    # Delete conversation endpoint
    @app.delete(
        f"{settings.api_prefix}/conversations/{{conversation_id}}",
        tags=["Conversation API v1"],
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
