"""
API agent endpoints for the server package.

This module contains the FastAPI route handlers for agent message exchange.
"""

import logging
from collections.abc import AsyncGenerator

from fastapi import Request

from ..config import settings
from ..core.types.agent import Agent, ClientError
from ..core.types.messages import (
    HumanInputMessage,
    InputMessage,
    MessageRequest,
    MessageResponse,
    ToolCallDecision,
)
from ..core.types.streaming import Event, StreamingChunk
from ..utils.id_generator import generate_run_id
from .api_conversations import SSEStreamingResponse, handle_agent_errors
from .json_serializer import (
    serialize_message_response,
)
from .runtime_config import create_runtime_config
from .schemas.sse import serialize_to_sse
from .sse_serializer import transform_chunk_to_sse

logger = logging.getLogger("nalai")


def validate_streaming_compatibility(stream: str, accept_header: str) -> None:
    """Validate streaming compatibility according to truth matrix."""
    if stream in ["full", "events"] and "text/event-stream" not in accept_header:
        raise ClientError(
            f"Incompatible transport: stream={stream} requires Accept: text/event-stream",
            http_status=406,
        )
    elif stream == "off" and "application/json" not in accept_header:
        raise ClientError(
            "Incompatible transport: stream=off requires Accept: application/json",
            http_status=406,
        )


def create_agent_api(app, agent: Agent) -> None:
    """Create agent message exchange endpoint routes."""

    @app.post(
        f"{settings.api_prefix}/messages",
        response_model=MessageResponse,
        tags=["Agent"],
        summary="Agent Messages Exchange",
        description="""An agent message exchange endpoint for all **conversation flows**:  
        - Start new conversation: no `conversation_id` in request body.  
        - Continue existing conversation: `conversation_id` in request body.  
        - Branch from response: `previous_response_id` in request body (framework ready, implementation pending).  
        - Resume with tool decisions: `tool_decision` in request body.
        <br>
        **Input Formats:**
        - String input: `"input": "Hello"` (implicit human message)  
        - Structured input: `"input": [{"type": "message", "role": "user", "content": [{"type": "text", "text": "Hello"}]}]` (type field is optional, defaults to "message")
        <br>
        **Content Delivery Mode:**  
        - **Streaming (default):** optional `"stream"` parameter in request body, and an `Accept: text/event-stream` header for SSE streaming.  
        - **Non-streaming:** "stream": "off" and `Accept: application/json` header for non-streaming mode.
        """,  # noqa: W291
        responses={
            200: {
                "description": "Successful Response",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/MessageResponse"}
                    },
                    "text/event-stream": {
                        "example": """event: response.created
data: {"id": "run_2b1c3d4e5f6g7h8", "conversation": "conv_2b1c3d4e5f6g7h8"}

event: response.output_text.delta
data: {"id": "run_2b1c3d4e5f6g7h8", "conversation": "conv_2b1c3d4e5f6g7h8", "content": "Hello"}

event: response.completed
data: {"id": "run_2b1c3d4e5f6g7h8", "conversation": "conv_2b1c3d4e5f6g7h8", "usage": {...}}"""
                    },
                },
                "headers": {
                    "X-Conversation-ID": {
                        "description": "Conversation ID for conversation management",
                        "schema": {"type": "string"},
                    }
                },
            },
            400: {
                "description": "Bad Request - Invalid input format or client error",
                "content": {
                    "application/json": {
                        "example": {
                            "detail": "An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'"
                        }
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
            404: {
                "description": "Conversation not found",
                "content": {
                    "application/json": {
                        "example": {"detail": "Conversation not found"}
                    },
                },
            },
            422: {
                "description": "Validation error",
                "content": {
                    "application/json": {
                        "example": {"detail": "Invalid conversation format"}
                    },
                },
            },
            406: {
                "description": "Incompatible transport - streaming requested with JSON Accept or vice versa",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "detail": {
                                    "type": "string",
                                    "example": "Incompatible transport: stream=full requires Accept: text/event-stream",
                                }
                            },
                        }
                    }
                },
            },
            500: {
                "description": "Internal server error",
                "content": {
                    "application/json": {
                        "example": {"detail": "Internal server error"}
                    },
                },
            },
        },
    )
    @handle_agent_errors
    async def handle_messages(
        request: MessageRequest, req: Request
    ) -> MessageResponse | SSEStreamingResponse:
        """
        Unified agent message exchange endpoint for conversation operations.

        Supports:
        - New conversations (no conversation_id)
        - Continue conversations (with conversation_id)
        - Branch from responses (with previous_response_id) - framework ready, implementation pending
        - Tool decisions (with tool_decision input)
        - String input (implicit human message) or structured message arrays
        """
        # Validate streaming compatibility according to truth matrix
        accept_header = req.headers.get("accept", "")
        validate_streaming_compatibility(request.stream, accept_header)

        if type(request.input) is str:
            request.input = [HumanInputMessage(content=request.input)]

        messages = request.input

        # Handle conversation_id: None for new conversations, actual ID for existing ones
        conversation_id = request.conversation_id  # Can be None for new conversations

        # Handle previous_response_id for response-level branching
        previous_response_id = (
            request.previous_response_id
        )  # Can be None for new responses

        # Create base runtime config (server-side: auth, user context, thread_id, etc.)
        base_config = create_runtime_config(req, conversation_id)

        # Apply user-provided runtime configuration overrides
        user_overrides = request.to_runtime_overrides()
        if user_overrides:
            # Merge user overrides into the configurable section
            if "configurable" not in base_config:
                base_config["configurable"] = {}
            base_config["configurable"].update(user_overrides)

        agent_config = base_config

        # Check if this is a tool decision request
        tool_call_decision = None

        for message in messages:
            if isinstance(message, ToolCallDecision):
                tool_call_decision = message
                break

        # Determine if we should stream based on the stream parameter
        should_stream = request.stream in ["full", "events"]

        # Handle tool decisions using resume functionality
        if tool_call_decision and conversation_id:
            if should_stream:
                return await _handle_resume_streaming_response(
                    agent, tool_call_decision, conversation_id, agent_config
                )
            else:
                return await _handle_resume_json_response(
                    agent, tool_call_decision, conversation_id, agent_config
                )

        # Handle regular chat requests
        if should_stream:
            return await _handle_streaming_response(
                agent,
                messages,
                conversation_id,
                agent_config,
                previous_response_id,
            )
        else:
            return await _handle_json_response(
                agent,
                messages,
                conversation_id,
                agent_config,
                previous_response_id,
            )


async def _handle_json_response(
    agent: Agent,
    messages: list[InputMessage],
    conversation_id: str | None,
    agent_config: dict,
    previous_response_id: str | None = None,
) -> MessageResponse:
    """Handle REST response for agent message exchange endpoint."""
    # Invoke agent
    result_messages, conversation_info = await agent.chat(
        messages, conversation_id, agent_config, previous_response_id
    )

    response = serialize_message_response(
        messages=result_messages,
        conversation_info=conversation_info,
        previous_response_id=previous_response_id,
        status="completed",
    )

    return response


async def _handle_resume_json_response(
    agent: Agent,
    resume_decision: ToolCallDecision,
    conversation_id: str,
    agent_config: dict,
) -> MessageResponse:
    """Handle resume JSON response for agent message exchange endpoint."""
    # Use the agent's resume functionality
    result_messages, conversation_info = await agent.resume_interrupted(
        resume_decision, conversation_id, agent_config
    )
    response = serialize_message_response(
        messages=result_messages,
        conversation_info=conversation_info,
        previous_response_id=None,
        status="completed",
    )

    return response


async def _handle_streaming_response(
    agent: Agent,
    messages: list,
    conversation_id: str | None,
    agent_config: dict,
    previous_response_id: str | None = None,
) -> SSEStreamingResponse:
    """Handle streaming response for agent message exchange endpoint."""
    # Get streaming response
    stream_gen, conversation_info = await agent.chat_streaming(
        messages, conversation_id, agent_config, previous_response_id
    )

    response = await _generate_streaming_response(
        stream_gen, conversation_info.conversation_id
    )
    return response


async def _handle_resume_streaming_response(
    agent: Agent,
    resume_decision: ToolCallDecision,
    conversation_id: str,
    agent_config: dict,
) -> SSEStreamingResponse:
    """Handle resume streaming response for agent message exchange endpoint."""
    # Use the agent's streaming resume functionality
    stream_gen, conversation_info = await agent.resume_interrupted_streaming(
        resume_decision, conversation_id, agent_config
    )

    response = await _generate_streaming_response(
        stream_gen, conversation_info.conversation_id
    )
    return response


async def _generate_streaming_response(
    stream_generator: AsyncGenerator[Event | StreamingChunk, None], conversation_id: str
) -> SSEStreamingResponse:
    # Generate a single run ID for this response cycle
    run_id = generate_run_id()

    async def generate():
        async for event in stream_generator:
            if isinstance(event, Event):
                sse_event = serialize_to_sse(event.model_dump())
                if sse_event:
                    yield sse_event
            elif isinstance(event, StreamingChunk):
                # Use the existing streaming event creation function for chunks
                sse_data_event = transform_chunk_to_sse(
                    chunk=event,
                    conversation_id=conversation_id,
                    context=None,
                    run_id=run_id,
                )
                if sse_data_event:
                    yield sse_data_event

    return SSEStreamingResponse(generate())
