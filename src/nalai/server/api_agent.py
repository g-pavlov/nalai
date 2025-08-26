"""
Agent Message Exchange Routes for API Assistant server.

This module contains FastAPI route handlers for the agent message exchange endpoint
that provides unified conversation operations.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

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
from .runtime_config import create_runtime_config
from .schemas.messages import (
    AssistantOutputMessage,
    HumanOutputMessage,
    Interrupt,
    MessageRequest,
    MessageResponse,
    OutputMessage,
    ResponseMetadata,
    TextContent,
    ToolCall,
    ToolOutputMessage,
)
from .streaming import serialize_to_sse

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
    async def agent_responses(
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
                return await _handle_resume_rest_response(
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
            return await _handle_rest_response(
                agent,
                messages,
                conversation_id,
                agent_config,
                request,
                previous_response_id,
            )


async def _handle_rest_response(
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
        output_messages = _convert_messages_to_output(result_messages)

        response_data = {
            "id": str(uuid.uuid4()),
            "conversation_id": actual_conversation_id,
            "previous_response_id": previous_response_id,
            "output": output_messages,
            "created_at": datetime.now(UTC).isoformat(),
            "status": status,
            "interrupts": interrupts_list if interrupts_list else None,
            "metadata": None,
            "usage": _extract_usage(result_messages),
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
            "usage": _extract_usage([]),  # Empty usage for error responses
        }

        return MessageResponse(**response_data)


async def _handle_resume_rest_response(
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
            "output": _convert_messages_to_output(result_messages),
            "created_at": datetime.now(UTC).isoformat(),
            "status": "completed",
            "interrupts": None,
            "metadata": None,
            "usage": _extract_usage(result_messages),
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
            "usage": _extract_usage([]),  # Empty usage for error responses
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
            yield serialize_to_sse(
                {
                    "event": "response.resumed",
                    "id": str(uuid.uuid4()),
                    "conversation": conversation_info.conversation_id,  # Use conversation info
                },
                lambda x: x,
            )

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
                        yield serialize_to_sse(event, lambda x: x)

                # Emit single message event with full content
                if full_content:
                    yield serialize_to_sse(
                        {
                            "event": "response.message",
                            "id": str(uuid.uuid4()),
                            "conversation": conversation_id,
                            "content": full_content,
                            "role": "assistant",
                        },
                        lambda x: x,
                    )
            else:
                # "full" mode - emit all events including token deltas
                async for event in stream_gen:
                    # Agent events are already serialized objects, format them as SSE
                    yield serialize_to_sse(event, lambda x: x)

            # Send completion event
            yield serialize_to_sse(
                {
                    "event": "response.completed",
                    "id": str(uuid.uuid4()),
                    "conversation": conversation_info.conversation_id,
                    "usage": _extract_usage([]),  # TODO: Extract from stream
                },
                lambda x: x,
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
            yield serialize_to_sse(
                {
                    "event": "response.error",
                    "id": str(uuid.uuid4()),
                    "conversation": conversation_info.conversation_id,  # Use conversation info
                    "error": error_message,
                },
                lambda x: x,
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
            yield serialize_to_sse(
                {
                    "event": "response.created",
                    "id": str(uuid.uuid4()),
                    "conversation": actual_conversation_id,
                },
                lambda x: x,
            )

            # Handle different streaming modes
            if request.stream == "events":
                # Collect all content for single message event
                full_content = ""
                async for event in stream_gen:
                    if hasattr(event, "content") and event.content:
                        full_content += str(event.content)
                    # Still emit other events (interrupts, etc.)
                    if not hasattr(event, "content") or not event.content:
                        yield serialize_to_sse(event, lambda x: x)

                # Emit single message event with full content
                if full_content:
                    yield serialize_to_sse(
                        {
                            "event": "response.message",
                            "id": str(uuid.uuid4()),
                            "conversation": actual_conversation_id,
                            "content": full_content,
                            "role": "assistant",
                        },
                        lambda x: x,
                    )
            else:
                # "full" mode - emit all events including token deltas
                async for event in stream_gen:
                    yield serialize_to_sse(event, lambda x: x)

            # Send completion event
            yield serialize_to_sse(
                {
                    "event": "response.completed",
                    "id": str(uuid.uuid4()),
                    "conversation": actual_conversation_id,
                    "usage": _extract_usage([]),  # TODO: Extract from stream
                },
                lambda x: x,
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
            yield serialize_to_sse(
                {
                    "event": "response.error",
                    "id": str(uuid.uuid4()),
                    "conversation": actual_conversation_id,
                    "error": error_message,
                },
                lambda x: x,
            )

        return SSEStreamingResponse(generate_error())


def _convert_messages_to_output(messages: list) -> list[OutputMessage]:
    """Convert LangChain messages to output format."""

    output_messages = []
    for message in messages:
        # Extract metadata fields
        raw_tool_calls = getattr(message, "tool_calls", None)
        invalid_tool_calls = getattr(message, "invalid_tool_calls", None)

        # Extract finish_reason from various possible locations (only for assistant messages)
        finish_reason = None
        if hasattr(message, "finish_reason"):
            finish_reason = message.finish_reason
        elif hasattr(message, "response_metadata") and message.response_metadata:
            finish_reason = message.response_metadata.get("finish_reason")
        elif hasattr(message, "additional_kwargs") and message.additional_kwargs:
            finish_reason = message.additional_kwargs.get("finish_reason")

        # Extract usage information from message (only for assistant messages)
        usage = None
        if hasattr(message, "usage_metadata") and message.usage_metadata:
            # Convert usage format to standard format
            usage_metadata = message.usage_metadata
            if isinstance(usage_metadata, dict):
                usage = {
                    "prompt_tokens": usage_metadata.get("input_tokens", 0),
                    "completion_tokens": usage_metadata.get("output_tokens", 0),
                    "total_tokens": usage_metadata.get("total_tokens", 0),
                }
        elif hasattr(message, "usage") and message.usage:
            usage = message.usage
        else:
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Convert raw tool calls to ToolCall objects
        tool_calls = None
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id"), name=tc.get("name"), args=tc.get("args", {})
                    )
                )

        # Create content blocks
        content_blocks = []
        if hasattr(message, "content") and message.content:
            content_blocks.append(TextContent(text=str(message.content)))

        # Determine message type and create appropriate output
        message_type = message.__class__.__name__.lower().replace("message", "")

        if message_type == "human":
            output_message = HumanOutputMessage(
                id=str(uuid.uuid4()),
                content=content_blocks,
            )
        elif message_type == "ai":
            output_message = AssistantOutputMessage(
                id=str(uuid.uuid4()),
                content=content_blocks,
                tool_calls=tool_calls,
                invalid_tool_calls=invalid_tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )
        elif message_type == "tool":
            # Extract tool_call_id for tool messages
            tool_call_id = None
            if hasattr(message, "tool_call_id"):
                tool_call_id = message.tool_call_id

            output_message = ToolOutputMessage(
                id=str(uuid.uuid4()),
                content=content_blocks,
                tool_call_id=tool_call_id,
            )
        else:
            # Fallback for unknown message types
            output_message = HumanOutputMessage(
                id=str(uuid.uuid4()),
                content=content_blocks,
            )

        output_messages.append(output_message)

    return output_messages


def _extract_usage(messages: list) -> dict[str, Any]:
    """Extract usage information from messages."""
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for message in messages:
        # Check for usage_metadata first (LangChain format)
        usage = None
        if hasattr(message, "usage_metadata") and message.usage_metadata:
            usage_metadata = message.usage_metadata
            if isinstance(usage_metadata, dict):
                usage = {
                    "prompt_tokens": usage_metadata.get("input_tokens", 0),
                    "completion_tokens": usage_metadata.get("output_tokens", 0),
                    "total_tokens": usage_metadata.get("total_tokens", 0),
                }
        elif hasattr(message, "usage") and message.usage:
            usage = message.usage

        if usage and isinstance(usage, dict):
            total_prompt_tokens += usage.get("prompt_tokens", 0)
            total_completion_tokens += usage.get("completion_tokens", 0)
            total_tokens += usage.get("total_tokens", 0)

    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
    }
