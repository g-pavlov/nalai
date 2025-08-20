"""
Route handlers for API Assistant server.

This module contains FastAPI route handlers for basic endpoints
and conversation endpoints with access control integration.
"""

import json
import logging
import uuid
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from langgraph.graph.state import CompiledStateGraph

from ..config import settings
from .runtime_config import (
    default_modify_runtime_config,
    validate_runtime_config,
)
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
from .streaming import (
    serialize_event_default,
    stream_events,
)

logger = logging.getLogger("nalai")


def create_user_scoped_conversation_id(user_id: str, conversation_id: str) -> str:
    """
    Create a user-scoped conversation ID for LangGraph checkpointing.

    Args:
        user_id: The user ID
        conversation_id: The conversation ID (UUID)

    Returns:
        str: User-scoped conversation ID in format "user:{user_id}:{conversation_id}"
    """
    return f"user:{user_id}:{conversation_id}"


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

    async def get_user_context_safe(req: Request) -> tuple[str, str]:
        """
        Safely extract user context from request.

        Returns:
            tuple: (user_id, user_context)

        Raises:
            HTTPException: If user context cannot be extracted
        """
        try:
            from ..server.runtime_config import get_user_context

            user_context = get_user_context(req)
            return user_context.user_id, user_context
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            raise HTTPException(
                status_code=401, detail="Authentication required"
            ) from e

    async def validate_conversation_access(conversation_id: str, user_id: str) -> None:
        """
        Validate conversation access for a user.

        Args:
            conversation_id: The conversation ID to validate (must be UUID)
            user_id: The user ID requesting access

        Raises:
            HTTPException: If access is denied or conversation_id is invalid
        """
        from ..services.thread_access_control import get_thread_access_control

        access_control = get_thread_access_control()

        # Validate that conversation_id is a UUID using schema
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        # Validate access using UUID
        has_access = await access_control.validate_thread_access(
            user_id, conversation_id
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to conversation")

    async def create_agent_config(req: Request, conversation_id: str) -> dict:
        """
        Create agent configuration for conversation operations.

        Args:
            req: FastAPI request object
            conversation_id: Conversation ID (assumes thread already exists and validation done)

        Returns:
            dict: Agent configuration

        Raises:
            HTTPException: If configuration creation fails
        """
        user_id, _ = await get_user_context_safe(req)

        # Create user-scoped ID for LangGraph checkpointing
        user_scoped_conversation_id = create_user_scoped_conversation_id(
            user_id, conversation_id
        )

        # Create agent configuration
        config = {"configurable": {"thread_id": user_scoped_conversation_id}}

        # Apply runtime modifications (auth, user context, etc.)
        agent_config = modify_runtime_config(config, req)
        validate_runtime_config(agent_config)

        return agent_config

    def extract_messages_from_checkpoint(checkpoint_state: dict) -> list[dict]:
        """
        Extract messages from checkpoint state in a standardized format.

        Args:
            checkpoint_state: The checkpoint state from LangGraph

        Returns:
            list: List of message dictionaries in our API format
        """
        messages = []

        # Try to get messages from channel_values first (LangGraph format)
        if checkpoint_state and "channel_values" in checkpoint_state:
            channel_values = checkpoint_state["channel_values"]
            logger.debug(
                f"Channel values keys: {list(channel_values.keys()) if channel_values else 'None'}"
            )

            # Look for messages in channel_values
            if "messages" in channel_values:
                checkpoint_messages = channel_values["messages"]
                logger.debug(
                    f"Processing {len(checkpoint_messages)} messages from channel_values"
                )

                for i, msg_obj in enumerate(checkpoint_messages):
                    logger.debug(f"Processing message {i}: {msg_obj}")

                    # Handle LangChain message objects
                    if hasattr(msg_obj, "content") and hasattr(msg_obj, "__class__"):
                        msg_type = msg_obj.__class__.__name__.lower()
                        msg_content = msg_obj.content

                        # Map LangChain message types to our format
                        if "human" in msg_type:
                            messages.append({"content": msg_content, "type": "human"})
                        elif "ai" in msg_type:
                            # Handle AI messages with tool calls
                            tool_calls = getattr(msg_obj, "tool_calls", None)
                            messages.append(
                                {
                                    "content": msg_content,
                                    "type": "ai",
                                    "tool_calls": tool_calls,
                                }
                            )
                        elif "tool" in msg_type:
                            # Handle tool messages
                            tool_name = getattr(msg_obj, "name", None)
                            tool_call_id = getattr(msg_obj, "tool_call_id", None)
                            messages.append(
                                {
                                    "content": msg_content,
                                    "type": "tool",
                                    "name": tool_name,
                                    "tool_call_id": tool_call_id,
                                }
                            )
                        else:
                            logger.warning(
                                f"Unknown LangChain message type: {msg_type}"
                            )

                    # Handle tuple format (fallback)
                    elif isinstance(msg_obj, tuple) and len(msg_obj) >= 2:
                        msg_type, msg_content = msg_obj[0], msg_obj[1]
                        logger.debug(
                            f"Processing tuple message - type: {msg_type}, content: {msg_content}"
                        )

                        if msg_type == "human":
                            messages.append({"content": msg_content, "type": "human"})
                        elif msg_type == "ai":
                            # Handle AI messages with tool calls in tuple format
                            tool_calls = None
                            if (
                                isinstance(msg_content, dict)
                                and "tool_calls" in msg_content
                            ):
                                tool_calls = msg_content.get("tool_calls")
                            messages.append(
                                {
                                    "content": msg_content
                                    if isinstance(msg_content, str)
                                    else "",
                                    "type": "ai",
                                    "tool_calls": tool_calls,
                                }
                            )
                        elif msg_type == "tool" and isinstance(msg_content, dict):
                            # Ensure content is not None for tool messages
                            tool_content = msg_content.get("content", "")
                            if tool_content is None:
                                tool_content = ""
                            messages.append(
                                {
                                    "content": tool_content,
                                    "type": "tool",
                                    "name": msg_content.get("name"),
                                    "tool_call_id": msg_content.get("tool_call_id"),
                                }
                            )
                        else:
                            logger.warning(
                                f"Unknown message type or format: {msg_type}, {msg_content}"
                            )
                    else:
                        logger.warning(f"Invalid message format: {msg_obj}")

        # Fallback to direct messages key (if it exists)
        elif checkpoint_state and "messages" in checkpoint_state:
            checkpoint_messages = checkpoint_state["messages"]
            logger.debug(
                f"Processing {len(checkpoint_messages)} messages from direct messages key"
            )

            for i, msg_tuple in enumerate(checkpoint_messages):
                logger.debug(f"Processing message {i}: {msg_tuple}")
                if isinstance(msg_tuple, tuple) and len(msg_tuple) >= 2:
                    msg_type, msg_content = msg_tuple[0], msg_tuple[1]
                    logger.debug(f"Message type: {msg_type}, content: {msg_content}")

                    if msg_type == "human":
                        messages.append({"content": msg_content, "type": "human"})
                    elif msg_type == "ai":
                        # Handle AI messages with tool calls in tuple format
                        tool_calls = None
                        if (
                            isinstance(msg_content, dict)
                            and "tool_calls" in msg_content
                        ):
                            tool_calls = msg_content.get("tool_calls")
                        messages.append(
                            {
                                "content": msg_content
                                if isinstance(msg_content, str)
                                else "",
                                "type": "ai",
                                "tool_calls": tool_calls,
                            }
                        )
                    elif msg_type == "tool" and isinstance(msg_content, dict):
                        # Ensure content is not None for tool messages
                        tool_content = msg_content.get("content", "")
                        if tool_content is None:
                            tool_content = ""
                        messages.append(
                            {
                                "content": tool_content,
                                "type": "tool",
                                "name": msg_content.get("name"),
                                "tool_call_id": msg_content.get("tool_call_id"),
                            }
                        )
                    else:
                        logger.warning(
                            f"Unknown message type or format: {msg_type}, {msg_content}"
                        )
                else:
                    logger.warning(f"Invalid message format: {msg_tuple}")

        logger.debug(f"Extracted {len(messages)} messages")
        for i, msg in enumerate(messages):
            logger.debug(f"Extracted message {i}: {msg}")

        return messages

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

        # Validate conversation access before creating config
        user_id, _ = await get_user_context_safe(req)
        await validate_conversation_access(conversation_id, user_id)

        # Convert the request to internal format expected by LangGraph
        interrupt_response = request.to_internal()

        # Create agent configuration for resume operations
        agent_config = await create_agent_config(req, conversation_id)

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
    async def continue_conversation(
        conversation_id: str, request: ConversationRequest, req: Request
    ) -> ConversationResponse | StreamingResponse:
        """
        Continue existing conversation endpoint that handles both JSON and streaming responses.
        Use Accept: text/event-stream header for streaming response.
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id using schema
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        streaming = is_streaming_request(req)

        return await _handle_conversation_internal(
            request, req, streaming=streaming, conversation_id=conversation_id
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
    async def load_conversation(
        conversation_id: str, req: Request
    ) -> LoadConversationResponse:
        """
        Load conversation endpoint that returns conversation state and metadata.
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id using schema
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        return await _handle_load_conversation_internal(conversation_id, req)

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
    async def list_conversations(req: Request) -> ListConversationsResponse:
        """
        List conversations endpoint that returns all conversations accessible to the current user.
        """
        return await _handle_list_conversations_internal(req)

    # Resume decision endpoint
    @app.post(
        f"{settings.api_prefix}/conversations/{{conversation_id}}/resume-decision",
        response_model=ResumeDecisionResponse,  # Add response model for schema generation
        tags=["Conversation API v1"],
        summary="Handle Resume Decision",
        description="""Resume a conversation workflow that was interrupted for tool execution approval with a decision. An interface for implementing human-in-the-loop.  
        Use the conversation ID of the interrupted workflow conversation to resume it. The conversation_id must be a valid UUID4.
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
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id using schema
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        streaming = is_streaming_request(req)

        return await _handle_resume_decision_internal(
            request, req, conversation_id, streaming=streaming
        )

    async def _handle_load_conversation_internal(
        conversation_id: str, req: Request
    ) -> LoadConversationResponse:
        """
        Internal handler for loading conversation state.
        """
        # Get user context for access control
        user_id, _ = await get_user_context_safe(req)

        # Validate conversation access
        await validate_conversation_access(conversation_id, user_id)

        # Get access control service
        from ..services.thread_access_control import get_thread_access_control

        access_control = get_thread_access_control()

        # Get conversation state from checkpointing service
        from ..services.checkpointing_service import get_checkpointer

        checkpointer = get_checkpointer()

        try:
            # Create agent configuration using factory function
            agent_config = await create_agent_config(req, conversation_id)

            # Get the checkpoint state
            checkpoint_state = await checkpointer.aget(agent_config)

            if not checkpoint_state:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Log checkpoint state for debugging
            logger.debug(
                f"Checkpoint state keys: {list(checkpoint_state.keys()) if checkpoint_state else 'None'}"
            )
            if checkpoint_state and "messages" in checkpoint_state:
                logger.debug(f"Messages in checkpoint: {checkpoint_state['messages']}")
            if checkpoint_state and "channel_values" in checkpoint_state:
                logger.debug(f"Channel values: {checkpoint_state['channel_values']}")
                if "messages" in checkpoint_state["channel_values"]:
                    logger.debug(
                        f"Channel messages count: {len(checkpoint_state['channel_values']['messages'])}"
                    )
                    for i, msg in enumerate(
                        checkpoint_state["channel_values"]["messages"]
                    ):
                        logger.debug(
                            f"Channel message {i}: type={type(msg)}, content={getattr(msg, 'content', 'N/A') if hasattr(msg, 'content') else msg}"
                        )

            # Extract messages using the helper function
            messages = extract_messages_from_checkpoint(checkpoint_state)

            # Get thread ownership information for metadata
            thread_ownership = await access_control.get_thread_ownership(
                conversation_id
            )

            metadata = {}
            created_at = None
            last_accessed = None

            if thread_ownership:
                metadata = thread_ownership.metadata
                created_at = (
                    thread_ownership.created_at.isoformat()
                    if thread_ownership.created_at
                    else None
                )
                last_accessed = (
                    thread_ownership.last_accessed.isoformat()
                    if thread_ownership.last_accessed
                    else None
                )

            # Determine conversation status based on checkpoint state
            status = "active"
            if "interrupts" in checkpoint_state and checkpoint_state["interrupts"]:
                status = "interrupted"
            elif checkpoint_state.get("completed", False):
                status = "completed"

            return LoadConversationResponse(
                conversation_id=conversation_id,
                messages=messages,
                metadata=metadata,
                created_at=created_at,
                last_accessed=last_accessed,
                status=status,
            )

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to load conversation"
            ) from e

    async def _handle_list_conversations_internal(
        req: Request,
    ) -> ListConversationsResponse:
        """
        Internal handler for listing conversations.
        """
        # Get user context for access control
        user_id, _ = await get_user_context_safe(req)

        # Get access control service
        from ..services.thread_access_control import get_thread_access_control

        access_control = get_thread_access_control()

        # Get checkpointing service
        from ..services.checkpointing_service import get_checkpointer

        checkpointer = get_checkpointer()

        try:
            # Get all threads owned by the user
            user_threads = await access_control.list_user_threads(user_id)

            conversations = []

            for thread_ownership in user_threads:
                conversation_id = thread_ownership.thread_id

                # Create user-scoped conversation ID for LangGraph
                user_scoped_conversation_id = create_user_scoped_conversation_id(
                    user_id, conversation_id
                )

                # Get the checkpoint state to extract preview
                checkpoint_state = await checkpointer.aget(
                    {"configurable": {"thread_id": user_scoped_conversation_id}}
                )

                # Extract preview from messages
                preview = None
                if checkpoint_state and "channel_values" in checkpoint_state:
                    channel_values = checkpoint_state["channel_values"]
                    if "messages" in channel_values:
                        messages = channel_values["messages"]
                        if messages:
                            # Get the first message content for preview
                            first_msg = messages[0]
                            if hasattr(first_msg, "content"):
                                preview = first_msg.content[:256]
                            elif isinstance(first_msg, tuple) and len(first_msg) >= 2:
                                preview = str(first_msg[1])[:256]

                # Create conversation summary
                conversation_summary = ConversationSummary(
                    conversation_id=conversation_id,
                    created_at=(
                        thread_ownership.created_at.isoformat()
                        if thread_ownership.created_at
                        else None
                    ),
                    last_updated=(
                        thread_ownership.last_accessed.isoformat()
                        if thread_ownership.last_accessed
                        else None
                    ),
                    preview=preview,
                    metadata=thread_ownership.metadata,
                )

                conversations.append(conversation_summary)

            return ListConversationsResponse(
                conversations=conversations, total_count=len(conversations)
            )

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to list conversations for user {user_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to list conversations"
            ) from e

    async def _handle_conversation_internal(
        request: ConversationRequest,
        req: Request,
        streaming: bool = False,
        conversation_id: str = None,
    ) -> ConversationResponse | StreamingResponse:
        """
        Internal handler for conversation operations.
        """

        user_id, _ = await get_user_context_safe(req)

        if conversation_id:
            # For existing conversations: validate access
            await validate_conversation_access(conversation_id, user_id)
        else:
            # For new conversations: create new UUID and thread ownership record
            conversation_id = str(uuid.uuid4())
            from ..services.thread_access_control import get_thread_access_control

            access_control = get_thread_access_control()
            await access_control.create_thread(user_id, conversation_id)

        # Create agent configuration
        agent_config = await create_agent_config(req, conversation_id)

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
                generate(),
                headers=get_conversation_headers(conversation_id),
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
    async def delete_conversation(conversation_id: str, req: Request) -> Response:
        """
        Delete conversation endpoint that removes conversation data and access control records.
        The conversation_id must be a valid UUID4.
        """
        # Validate conversation_id using schema
        try:
            ConversationIdPathParam(conversation_id=conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        return await _handle_delete_conversation_internal(conversation_id, req)

    async def _handle_delete_conversation_internal(
        conversation_id: str, req: Request
    ) -> Response:
        """
        Internal handler for deleting conversation.
        """
        # Get user context for access control
        user_id, _ = await get_user_context_safe(req)

        # Validate conversation access
        await validate_conversation_access(conversation_id, user_id)

        # Get access control service
        from ..services.thread_access_control import get_thread_access_control

        access_control = get_thread_access_control()

        # Get checkpointing service
        from ..services.checkpointing_service import get_checkpointer

        checkpointer = get_checkpointer()

        try:
            # Create agent configuration using factory function
            agent_config = await create_agent_config(req, conversation_id)

            # Delete the checkpoint state from LangGraph
            try:
                # LangGraph MemorySaver doesn't have a delete method, but we can try to clear it
                # by setting it to None or an empty state
                await checkpointer.aput(agent_config, None)
                logger.debug(
                    f"Cleared checkpoint state for conversation {conversation_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to clear checkpoint state: {e}")
                # Continue with deletion even if checkpoint clearing fails

            # Delete the thread ownership record
            deleted = await access_control.delete_thread(user_id, conversation_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Conversation not found")

            logger.info(
                f"Successfully deleted conversation {conversation_id} for user {user_id}"
            )

            # Return 204 No Content for successful deletion
            return Response(status_code=204)

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to delete conversation"
            ) from e
