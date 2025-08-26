"""
Agent Message Exchange Routes for API Assistant server.

This module contains FastAPI route handlers for the agent message exchange endpoint
that provides unified conversation operations.
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request

from ..config import settings
from ..core import (
    AccessDeniedError,
    Agent,
    ClientError,
    ConversationNotFoundError,
    InvocationError,
    ValidationError,
)
from .api_conversations import SSEStreamingResponse, handle_agent_errors
from .message_serializer import convert_messages_to_output, extract_usage_from_messages
from .runtime_config import create_runtime_config
from .schemas.messages import (
    Interrupt,
    MessageRequest,
    MessageResponse,
    ResponseMetadata,
)
from .sse_serializer import (
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    ResponseMessageEvent,
    ResponseResumedEvent,
    create_event,
    create_streaming_event,
)

logger = logging.getLogger("nalai")


def validate_streaming_compatibility(stream: str, accept_header: str) -> None:
    """Validate streaming mode compatibility with Accept header according to truth matrix."""
    if stream in ["full", "events"] and "text/event-stream" not in accept_header:
        raise HTTPException(
            status_code=406,
            detail=f"Incompatible transport: stream={stream} requires Accept: text/event-stream",
        )
    if stream == "off" and "text/event-stream" in accept_header:
        raise HTTPException(
            status_code=406,
            detail="Incompatible transport: stream=off requires Accept: application/json",
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
data: {"id": "resp_789", "conversation": "conv_123"}

event: response.output_text.delta
data: {"id": "resp_789", "conversation": "conv_123", "content": "Hello"}

event: response.completed
data: {"id": "resp_789", "conversation": "conv_123", "usage": {...}}"""
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

        # Convert input to LangChain messages
        messages = request.to_langchain_messages()

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
        is_tool_decision = False
        tool_decision_data = None

        for message in messages:
            if hasattr(message, "additional_kwargs") and message.additional_kwargs:
                if "tool_decision" in message.additional_kwargs:
                    is_tool_decision = True
                    tool_decision_data = message.additional_kwargs["tool_decision"]
                    break

        # Determine if we should stream based on the stream parameter
        should_stream = request.stream in ["full", "events"]

        # Handle tool decisions using resume functionality
        if is_tool_decision and conversation_id:
            from ..core import ResumeDecision

            resume_decision = ResumeDecision(
                action=tool_decision_data["decision"],
                args=tool_decision_data.get("args"),
                tool_call_id=tool_decision_data["tool_call_id"],
            )

            if should_stream:
                return await _handle_resume_streaming_response(
                    agent, resume_decision, conversation_id, agent_config, request
                )
            else:
                return await _handle_resume_json_response(
                    agent, resume_decision, conversation_id, agent_config, request
                )

        # Handle regular chat requests
        if should_stream:
            return await _handle_streaming_response(
                agent,
                messages,
                conversation_id,
                agent_config,
                request,
                previous_response_id,
            )
        else:
            return await _handle_json_response(
                agent,
                messages,
                conversation_id,
                agent_config,
                request,
                previous_response_id,
            )


async def _handle_json_response(
    agent: Agent,
    messages: list,
    conversation_id: str | None,
    agent_config: dict,
    request: MessageRequest,
    previous_response_id: str | None = None,
) -> MessageResponse:
    """Handle REST response for agent message exchange endpoint."""
    try:
        # Invoke agent
        result_messages, conversation_info = await agent.chat(
            messages, conversation_id, agent_config, previous_response_id
        )

        # Get conversation_id from agent response (for new conversations)
        actual_conversation_id = conversation_info.conversation_id

        # Check for interrupts in the conversation_info
        status = "completed"
        interrupts_list = None

        if conversation_info.interrupt_info:
            interrupt_info = conversation_info.interrupt_info
            # Handle new multiple interrupts structure
            if "interrupts" in interrupt_info:
                # New structure with multiple interrupts
                interrupt_infos = []
                for single_interrupt in interrupt_info["interrupts"]:
                    interrupt_infos.append(
                        Interrupt(
                            type=single_interrupt.get("type", "tool_call"),
                            tool_call_id=single_interrupt.get(
                                "tool_call_id", "unknown"
                            ),
                            action=single_interrupt.get("action", "unknown"),
                            args=single_interrupt.get("args", {}),
                        )
                    )
                interrupts_list = interrupt_infos
            else:
                # Legacy single interrupt structure - convert to new format
                interrupt_infos = [
                    Interrupt(
                        type=interrupt_info.get("type", "tool_call"),
                        tool_call_id=interrupt_info.get("tool_call_id", "unknown"),
                        action=interrupt_info.get("action", "unknown"),
                        args=interrupt_info.get("args", {}),
                    )
                ]
                interrupts_list = interrupt_infos
            status = "interrupted"

        # Create response output
        output_messages = convert_messages_to_output(result_messages)

        response_data = {
            "id": str(uuid.uuid4()),
            "conversation_id": actual_conversation_id,
            "previous_response_id": previous_response_id,
            "output": output_messages,
            "created_at": datetime.now(UTC).isoformat(),
            "status": status,
            "interrupts": interrupts_list if interrupts_list else None,
            "metadata": None,
            "usage": extract_usage_from_messages(result_messages),
        }

        return MessageResponse(**response_data)

    except (
        ValidationError,
        AccessDeniedError,
        ConversationNotFoundError,
        InvocationError,
        ClientError,
    ):
        # Let specific agent errors bubble up to be handled by @handle_agent_errors decorator
        raise
    except Exception as e:
        logger.error(f"Unexpected agent response error: {e}")
        # Create error response for unexpected errors
        response_data = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id or "unknown",
            "previous_response_id": previous_response_id,
            "output": [],
            "created_at": datetime.now(UTC).isoformat(),
            "status": "error",
            "interrupts": None,
            "metadata": ResponseMetadata(error=str(e)),
            "usage": extract_usage_from_messages([]),  # Empty usage for error responses
        }

        return MessageResponse(**response_data)


async def _handle_resume_json_response(
    agent: Agent,
    resume_decision,
    conversation_id: str,
    agent_config: dict,
    request: MessageRequest,
) -> MessageResponse:
    """Handle REST response for resume operations."""
    try:
        # Use the agent's resume functionality
        result_messages, conversation_info = await agent.resume_interrupted(
            resume_decision, conversation_id, agent_config
        )

        # Create response output
        response_data = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_info.conversation_id,
            "previous_response_id": None,  # Resume responses don't branch from previous responses
            "output": convert_messages_to_output(result_messages),
            "created_at": datetime.now(UTC).isoformat(),
            "status": "completed",
            "interrupts": None,
            "metadata": None,
            "usage": extract_usage_from_messages(result_messages),
        }

        return MessageResponse(**response_data)

    except (
        ValidationError,
        AccessDeniedError,
        ConversationNotFoundError,
        InvocationError,
        ClientError,
    ):
        # Let specific agent errors bubble up to be handled by @handle_agent_errors decorator
        raise
    except Exception as e:
        logger.error(f"Unexpected agent resume response error: {e}")
        # Create error response for unexpected errors
        response_data = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "previous_response_id": None,  # Resume error responses don't branch from previous responses
            "output": [],
            "created_at": datetime.now(UTC).isoformat(),
            "status": "error",
            "interrupts": None,
            "metadata": ResponseMetadata(error=str(e)),
            "usage": extract_usage_from_messages([]),  # Empty usage for error responses
        }

        return MessageResponse(**response_data)


async def _handle_resume_streaming_response(
    agent: Agent,
    resume_decision,
    conversation_id: str,
    agent_config: dict,
    request: MessageRequest,
) -> SSEStreamingResponse:
    """Handle resume streaming response for agent message exchange endpoint."""
    try:
        # Use the agent's resume streaming functionality
        stream_gen, conversation_info = await agent.resume_interrupted_streaming(
            resume_decision, conversation_id, agent_config
        )

        async def generate():
            # Send response resumed event
            yield create_event(ResponseResumedEvent, conversation_info.conversation_id)

            # Handle different streaming modes
            if request.stream == "events":
                # Collect all content for single message event
                full_content = ""
                async for event in stream_gen:
                    if hasattr(event, "content") and event.content:
                        full_content += str(event.content)
                    # Still emit other events (interrupts, etc.)
                    if not hasattr(event, "content") or not event.content:
                        # Agent events are already serialized objects, format them as SSE
                        yield create_streaming_event(event, lambda x: x)

                # Emit single message event with full content
                if full_content:
                    yield create_event(ResponseMessageEvent, conversation_id, content=full_content)
            else:
                # "full" mode - emit all events including token deltas
                async for event in stream_gen:
                    # Agent events are already serialized objects, format them as SSE
                    yield create_streaming_event(event, lambda x: x)

            # Send completion event
            yield create_event(
                ResponseCompletedEvent,
                conversation_info.conversation_id,
                usage=extract_usage_from_messages([]),  # TODO: Extract from stream
            )

        response = SSEStreamingResponse(generate())
        if conversation_id:
            response.headers["X-Conversation-ID"] = conversation_id
        return response

    except Exception as e:
        logger.error(f"Agent resume streaming error: {e}")
        error_message = str(e)

        # Return error event
        async def generate_error():
            yield create_event(
                ResponseErrorEvent, conversation_info.conversation_id, error=error_message
            )

        return SSEStreamingResponse(generate_error())


async def _handle_streaming_response(
    agent: Agent,
    messages: list,
    conversation_id: str | None,
    agent_config: dict,
    request: MessageRequest,
    previous_response_id: str | None = None,
) -> SSEStreamingResponse:
    """Handle streaming response for agent message exchange endpoint."""
    try:
        # Get streaming response
        stream_gen, conversation_info = await agent.chat_streaming(
            messages, conversation_id, agent_config, previous_response_id
        )

        # Get the actual conversation ID from the agent response
        actual_conversation_id = conversation_info.conversation_id

        async def generate():
            # Send response created event
            yield create_event(ResponseCreatedEvent, actual_conversation_id)

            # Handle different streaming modes
            if request.stream == "events":
                # Collect all content for single message event
                full_content = ""
                async for event in stream_gen:
                    if hasattr(event, "content") and event.content:
                        full_content += str(event.content)
                    # Still emit other events (interrupts, etc.)
                    if not hasattr(event, "content") or not event.content:
                        yield create_streaming_event(event, lambda x: x)

                # Emit single message event with full content
                if full_content:
                    yield create_event(
                        ResponseMessageEvent, actual_conversation_id, content=full_content
                    )
            else:
                # "full" mode - emit all events including token deltas
                async for event in stream_gen:
                    yield create_streaming_event(event, lambda x: x)

            # Send completion event
            yield create_event(
                ResponseCompletedEvent,
                actual_conversation_id,
                usage=extract_usage_from_messages([]),  # TODO: Extract from stream
            )

        response = SSEStreamingResponse(generate())
        if conversation_id:
            response.headers["X-Conversation-ID"] = conversation_id
        return response

    except Exception as e:
        logger.error(f"Agent streaming error: {e}")
        error_message = str(e)

        # Return error event
        async def generate_error():
            yield create_event(ResponseErrorEvent, actual_conversation_id, error=error_message)

        return SSEStreamingResponse(generate_error())
