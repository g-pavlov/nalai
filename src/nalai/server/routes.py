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
from langgraph.graph.state import CompiledStateGraph

from ..config import BaseRuntimeConfiguration, settings
from ..services.thread_access_control import validate_conversation_access_and_scope
from ..utils.validation import validate_thread_id_format
from .runtime_config import (
    default_modify_runtime_config,
    validate_runtime_config,
)
from .schemas import (
    ConversationRequest,
    ConversationResponse,
    HealthzResponse,
    ResumeDecisionRequest,
    ResumeDecisionResponse,
)
from .streaming import (
    serialize_event_default,
    stream_events,
)

logger = logging.getLogger("nalai")


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

    @app.get("/healthz", tags=["System"])
    async def healthz() -> HealthzResponse:
        return HealthzResponse(status="Healthy")

    # TODO: Add /metrics endpoint for future metrics collection
    # @app.get("/metrics")
    # async def metrics() -> dict[str, object]:
    #     return {"metrics": "to be implemented"}


def create_conversation_routes(
    app: FastAPI,
    agent: CompiledStateGraph,
    *,
    serialize_event: Callable[[object], object] = serialize_event_default,
    modify_runtime_config: Callable[
        [dict, Request], dict
    ] = default_modify_runtime_config,
) -> None:
    """Create conversation endpoint routes."""

    def get_conversation_headers(conversation_id: str) -> dict[str, str]:
        """Get standard conversation response headers."""
        return {"X-Conversation-ID": conversation_id}

    def is_streaming_request(req: Request) -> bool:
        """Check if the request prefers streaming response."""
        accept_header = req.headers.get("accept", "text/event-stream")
        return "text/event-stream" in accept_header

    async def setup_runtime_config(
        config: BaseRuntimeConfiguration, req: Request, is_initial_request: bool = True
    ) -> tuple[dict, str]:
        """
        Lean runtime configuration setup.

        Args:
            config: Configuration dictionary
            req: FastAPI request object
            is_initial_request: True for initial chat requests, False for resume operations
        """
        if is_initial_request:
            # For initial requests: create user-scoped conversation ID if needed
            (
                config,
                user_scoped_conversation_id,
            ) = await validate_conversation_access_and_scope(config, req)
            validate_runtime_config(config)
            return config, user_scoped_conversation_id
        else:
            # For resume operations: validate existing conversation ID format only
            agent_config = modify_runtime_config(config, req)
            validate_runtime_config(agent_config)
            conversation_id = agent_config.get("configurable", {}).get(
                "thread_id", "unknown"
            )
            # Validate the conversation ID format without re-scoping
            try:
                validate_thread_id_format(conversation_id)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            return agent_config, conversation_id

    async def _handle_resume_decision_internal(
        request: ResumeDecisionRequest,
        req: Request,
        conversation_id: str,
        streaming: bool = True,
    ) -> StreamingResponse | Response:
        """Handle resume decision requests with access control (internal)."""
        logger.info(
            f"Resume decision: {request.input.decision} for conversation: {conversation_id}"
        )

        # Convert the request to internal format expected by LangGraph
        interrupt_response = request.to_internal()

        # Convert request to dict for configuration setup
        configurable = {"configurable": {"thread_id": conversation_id}}

        # For resume operations: validate existing conversation ID format without re-scoping
        agent_config, conversation_id = await setup_runtime_config(
            configurable, req, is_initial_request=False
        )

        if streaming:
            return SSEStreamingResponse(
                stream_events(
                    agent,
                    agent_config,
                    agent_input=None,  # No initial input for resume
                    resume_input=interrupt_response,
                    serialize_event=serialize_event,
                ),
                headers=get_conversation_headers(conversation_id),
            )
        else:
            # For synchronous resume, invoke the agent directly
            from langgraph.types import Command

            result = await agent.ainvoke(
                Command(resume=[interrupt_response]), config=agent_config
            )

            # Serialize the result using the same function as streaming
            serialized_result = serialize_event(result)

            # Return the result with conversation_id header
            return Response(
                content=json.dumps({"output": serialized_result}),
                media_type="application/json",
                headers=get_conversation_headers(conversation_id),
            )

    # Create new conversation endpoint
    @app.post(
        f"{settings.api_prefix}/conversations",
        response_model=ConversationResponse,  # Add response model for schema generation
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
    async def create_conversation(
        request: ConversationRequest, req: Request
    ) -> ConversationResponse | StreamingResponse:
        """
        Create new conversation endpoint that handles both JSON and streaming responses.
        Use Accept: text/event-stream header for streaming response.
        """
        streaming = is_streaming_request(req)

        return await _handle_conversation_internal(request, req, streaming=streaming)

    # Continue existing conversation endpoint
    @app.post(
        f"{settings.api_prefix}/conversations/{{conversation_id}}",
        response_model=ConversationResponse,  # Add response model for schema generation
        tags=["Conversation API v1"],
        summary="Continue Conversation",
        description="Continue an existing conversation. Accepts messages and returns agent response in a conversation.",
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
    async def continue_conversation(
        conversation_id: str, request: ConversationRequest, req: Request
    ) -> ConversationResponse | StreamingResponse:
        """
        Continue existing conversation endpoint that handles both JSON and streaming responses.
        Use Accept: text/event-stream header for streaming response.
        """
        streaming = is_streaming_request(req)

        return await _handle_conversation_internal(
            request, req, streaming=streaming, conversation_id=conversation_id
        )

    # Resume decision endpoint
    @app.post(
        f"{settings.api_prefix}/conversations/{{conversation_id}}/resume-decision",
        response_model=ResumeDecisionResponse,  # Add response model for schema generation
        tags=["Conversation API v1"],
        summary="Handle Resume Decision",
        description="""Resume a conversation workflow that was interrupted for tool execution approval with a decision. An interface for implementing human-in-the-loop.  
        Use the conversation ID of the interrupted workflow conversation to resume it.
        """,  # noqa: W291
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
    async def resume_decision(
        conversation_id: str, request: ResumeDecisionRequest, req: Request
    ) -> ResumeDecisionResponse | StreamingResponse:
        """
        Resume decision endpoint that handles both JSON and streaming responses.
        Use Accept: text/event-stream header for streaming response.
        """
        streaming = is_streaming_request(req)

        return await _handle_resume_decision_internal(
            request, req, conversation_id, streaming=streaming
        )

    async def _handle_conversation_internal(
        request: ConversationRequest,
        req: Request,
        streaming: bool = False,
        conversation_id: str = None,
    ) -> ConversationResponse | StreamingResponse:
        """
        Internal handler for conversation operations.
        """

        # Set up runtime configuration
        if conversation_id:
            # For continue conversation: use provided conversation_id
            config = {"configurable": {"thread_id": conversation_id}}
            agent_config, conversation_id = await setup_runtime_config(
                config, req, is_initial_request=False
            )
        else:
            # For create conversation: auto-create conversation_id
            agent_config, conversation_id = await setup_runtime_config(
                request.to_internal_config(), req, is_initial_request=True
            )

        # Convert structured input to dict for agent (using LangGraph format)
        agent_input = request.to_internal_messages()

        if streaming:
            # Return streaming response
            async def generate():
                async for event in stream_events(
                    agent,
                    agent_config,
                    agent_input,
                    resume_input=None,  # No resume input for initial request
                    serialize_event=serialize_event,
                ):
                    yield event

            return SSEStreamingResponse(
                generate(), headers=get_conversation_headers(conversation_id)
            )
        else:
            # Return JSON response
            try:
                result = await agent.ainvoke(agent_input, config=agent_config)
                serialized_result = serialize_event(result)
                return Response(
                    content=json.dumps({"output": serialized_result}),
                    media_type="application/json",
                    headers=get_conversation_headers(conversation_id),
                )
            except Exception as e:
                logger.error(f"Agent invocation failed: {e}")
                raise HTTPException(
                    status_code=500, detail="Agent invocation failed"
                ) from e

    # TODO: Add conversation management endpoints (list, get, delete)
    # These will be implemented in the next phase
