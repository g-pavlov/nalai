"""
API agent endpoints for the server package.

This module contains the FastAPI route handlers for agent message exchange.
"""

import logging
from datetime import UTC, datetime

from fastapi import Request

from ..config import settings
from ..core.agent import (
    AccessDeniedError,
    Agent,
    ClientError,
    ConversationNotFoundError,
    InvocationError,
)
from ..core.agent import (
    ValidationError as AgentValidationError,
)
from ..server.schemas.messages import (
    Interrupt,
    MessageRequest,
    MessageResponse,
    ResponseMetadata,
)
from ..utils.id_generator import generate_run_id
from .api_conversations import SSEStreamingResponse, handle_agent_errors
from .message_serializer import (
    convert_messages_to_output,
    extract_usage_from_core_messages,
)
from .runtime_config import create_runtime_config
from .sse_serializer import (
    create_response_completed_event,
    create_response_created_event,
    create_response_error_event,
    create_streaming_event_from_chunk,
    extract_usage_from_streaming_chunks,
)

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
        # Generate a single run ID for this response cycle
        run_id = generate_run_id()

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

        # Create response output with run-scoped IDs
        output_messages = convert_messages_to_output(result_messages, run_id)

        response_data = {
            "id": run_id,  # Use run_id as the response ID
            "conversation_id": actual_conversation_id,
            "previous_response_id": previous_response_id,
            "output": output_messages,
            "created_at": datetime.now(UTC).isoformat(),
            "status": status,
            "interrupts": interrupts_list if interrupts_list else None,
            "metadata": None,
            "usage": extract_usage_from_core_messages(result_messages),
        }

        return MessageResponse(**response_data)

    except (
        AgentValidationError,
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
        error_run_id = generate_run_id()
        # Create a placeholder error message to satisfy the schema requirement
        error_message = {
            "id": f"msg_{error_run_id.replace('run_', '')}",
            "role": "assistant",
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        response_data = {
            "id": error_run_id,  # Use run_id as the response ID
            "conversation_id": conversation_id,
            "previous_response_id": previous_response_id,
            "output": [error_message],
            "created_at": datetime.now(UTC).isoformat(),
            "status": "error",
            "interrupts": None,
            "metadata": ResponseMetadata(error=str(e)),
            "usage": extract_usage_from_core_messages(
                []
            ),  # Empty usage for error responses
        }

        return MessageResponse(**response_data)


async def _handle_resume_json_response(
    agent: Agent,
    resume_decision,
    conversation_id: str,
    agent_config: dict,
    request: MessageRequest,
) -> MessageResponse:
    """Handle resume JSON response for agent message exchange endpoint."""
    try:
        # Generate a single run ID for this response cycle
        run_id = generate_run_id()

        # Use the agent's resume functionality
        result_messages, conversation_info = await agent.resume_interrupted(
            resume_decision, conversation_id, agent_config
        )

        # Create response output with run-scoped IDs
        response_data = {
            "id": run_id,  # Use run_id as the response ID
            "conversation_id": conversation_info.conversation_id,
            "previous_response_id": None,  # Resume responses don't branch from previous responses
            "output": convert_messages_to_output(result_messages, run_id),
            "created_at": datetime.now(UTC).isoformat(),
            "status": "completed",
            "interrupts": None,
            "metadata": None,
            "usage": extract_usage_from_core_messages(result_messages),
        }

        return MessageResponse(**response_data)

    except (
        AgentValidationError,
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
        error_run_id = generate_run_id()
        # Create a placeholder error message to satisfy the schema requirement
        error_message = {
            "id": f"msg_{error_run_id.replace('run_', '')}",
            "role": "assistant",
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

        response_data = {
            "id": error_run_id,  # Use run_id as the response ID
            "conversation_id": conversation_id,
            "previous_response_id": None,  # Resume error responses don't branch from previous responses
            "output": [error_message],
            "created_at": datetime.now(UTC).isoformat(),
            "status": "error",
            "interrupts": None,
            "metadata": ResponseMetadata(error=str(e)),
            "usage": extract_usage_from_core_messages(
                []
            ),  # Empty usage for error responses
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
        # Generate a single run ID for this response cycle
        run_id = generate_run_id()

        # Use the agent's streaming resume functionality
        stream_gen, conversation_info = await agent.resume_interrupted_streaming(
            resume_decision, conversation_id, agent_config
        )

        # Get the actual conversation ID from the agent response
        actual_conversation_id = conversation_info.conversation_id

        async def generate():
            # Send response created event with run ID
            yield create_response_created_event(
                conversation_id=actual_conversation_id, run_id=run_id
            )

            # Collect messages and usage from the stream
            collected_messages = []

            # Process all events through the stream
            async for event in stream_gen:
                # Use the existing streaming event creation function for chunks
                sse_event = create_streaming_event_from_chunk(
                    chunk=event,
                    conversation_id=actual_conversation_id,
                    context=None,
                    run_id=run_id,
                )
                if sse_event:
                    yield sse_event

                # Collect messages for usage extraction from the original chunk
                if hasattr(event, "usage") and event.usage:
                    collected_messages.append(event)

            # Send completion event with actual usage
            usage_data = extract_usage_from_streaming_chunks(collected_messages)
            yield create_response_completed_event(
                conversation_id=actual_conversation_id, run_id=run_id, usage=usage_data
            )

        return SSEStreamingResponse(generate())

    except Exception as e:
        logger.error(f"Unexpected agent resume streaming response error: {e}")
        error_run_id = generate_run_id()
        error_message = str(e)

        async def generate_error():
            yield create_response_created_event(
                conversation_id=conversation_id, run_id=error_run_id
            )
            yield create_response_error_event(
                conversation_id=conversation_id,
                run_id=error_run_id,
                error=error_message,
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
        # Generate a single run ID for this response cycle
        run_id = generate_run_id()

        # Get streaming response
        stream_gen, conversation_info = await agent.chat_streaming(
            messages, conversation_id, agent_config, previous_response_id
        )

        # Get the actual conversation ID from the agent response
        actual_conversation_id = conversation_info.conversation_id

        async def generate():
            # Send response created event with run ID
            yield create_response_created_event(
                conversation_id=actual_conversation_id, run_id=run_id
            )

            # Collect messages and usage from the stream
            collected_messages = []

            # Process all events through the stream
            async for event in stream_gen:
                # Use the existing streaming event creation function for chunks
                sse_event = create_streaming_event_from_chunk(
                    chunk=event,
                    conversation_id=actual_conversation_id,
                    context=None,
                    run_id=run_id,
                )
                if sse_event:
                    yield sse_event

                # Collect messages for usage extraction from the original chunk
                if hasattr(event, "usage") and event.usage:
                    collected_messages.append(event)

            # Send completion event with actual usage
            usage_data = extract_usage_from_streaming_chunks(collected_messages)
            yield create_response_completed_event(
                conversation_id=actual_conversation_id, run_id=run_id, usage=usage_data
            )

        response = SSEStreamingResponse(generate())
        return response

    except Exception as e:
        logger.error(f"Unexpected agent streaming response error: {e}")
        error_run_id = generate_run_id()
        error_message = str(e)

        async def generate_error():
            yield create_response_created_event(
                conversation_id=conversation_id or "unknown", run_id=error_run_id
            )
            yield create_response_error_event(
                conversation_id=conversation_id or "unknown",
                run_id=error_run_id,
                error=error_message,
            )

        return SSEStreamingResponse(generate_error())
