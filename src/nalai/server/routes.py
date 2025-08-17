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

    def get_conversation_headers(
        conversation_id: str, user_id: str = "dev-user"
    ) -> dict[str, str]:
        """Get standard conversation response headers."""
        # Always return user-scoped ID for consistency
        if conversation_id.startswith("user:"):
            return {"X-Conversation-ID": conversation_id}
        else:
            # Convert base UUID to user-scoped ID
            return {"X-Conversation-ID": f"user:{user_id}:{conversation_id}"}

    def is_streaming_request(req: Request) -> bool:
        """Check if the request prefers streaming response."""
        accept_header = req.headers.get("accept", "text/event-stream")
        return "text/event-stream" in accept_header

    def get_user_context_safe(req: Request):
        """Get user context with proper error handling."""
        try:
            from ..server.runtime_config import get_user_context

            return get_user_context(req)
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            raise HTTPException(
                status_code=401, detail="Authentication required"
            ) from e

    def get_access_control_service():
        """Get thread access control service."""
        from ..services.thread_access_control import get_thread_access_control

        return get_thread_access_control()

    def get_checkpointing_service():
        """Get checkpointing service."""
        from ..services.checkpointing_service import get_checkpointer

        return get_checkpointer()

    async def validate_and_scope_conversation_id(
        conversation_id: str, user_id: str, access_control
    ) -> str:
        """
        Validate conversation ID format and scope it to user if needed.

        Returns:
            user_scoped_conversation_id: The conversation ID scoped to the user
        """
        # Validate conversation_id format
        try:
            validate_thread_id_format(conversation_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Determine the conversation ID to use for LangGraph
        # If the conversation_id is already user-scoped, use it directly
        # Otherwise, create a user-scoped version
        if conversation_id.startswith("user:"):
            # Already user-scoped, validate it belongs to this user
            parts = conversation_id.split(":", 2)
            if len(parts) >= 3 and parts[1] == user_id:
                return conversation_id
            else:
                raise HTTPException(
                    status_code=403, detail="Access denied to conversation"
                )
        else:
            # Not user-scoped, validate access and create user-scoped version
            has_access = await access_control.validate_thread_access(
                user_id, conversation_id
            )
            if not has_access:
                raise HTTPException(
                    status_code=403, detail="Access denied to conversation"
                )

            return await access_control.create_user_scoped_thread_id(
                user_id, conversation_id
            )

    def extract_base_conversation_id(conversation_id: str) -> str:
        """Extract base conversation ID from user-scoped ID."""
        if conversation_id.startswith("user:"):
            parts = conversation_id.split(":", 2)
            if len(parts) >= 3:
                return parts[2]
        return conversation_id

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
                headers=get_conversation_headers(conversation_id, "dev-user"),
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
                headers=get_conversation_headers(conversation_id, "dev-user"),
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

    # Load conversation endpoint
    @app.get(
        f"{settings.api_prefix}/conversations/{{conversation_id}}",
        response_model=LoadConversationResponse,
        tags=["Conversation API v1"],
        summary="Load Conversation",
        description="Load a previous conversation state by conversation ID. Returns conversation messages and metadata.",
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
        """
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

    async def _handle_load_conversation_internal(
        conversation_id: str, req: Request
    ) -> LoadConversationResponse:
        """
        Internal handler for loading conversation state.
        """
        # Get user context for access control
        user_context = get_user_context_safe(req)
        user_id = user_context.user_id

        # Get services
        access_control = get_access_control_service()
        checkpointer = get_checkpointing_service()

        try:
            # Validate and scope conversation ID
            user_scoped_conversation_id = await validate_and_scope_conversation_id(
                conversation_id, user_id, access_control
            )

            # Get the checkpoint state
            checkpoint_state = await checkpointer.aget(
                {"configurable": {"thread_id": user_scoped_conversation_id}}
            )

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

            # Extract messages from the checkpoint state
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
                        if hasattr(msg_obj, "content") and hasattr(
                            msg_obj, "__class__"
                        ):
                            msg_type = msg_obj.__class__.__name__.lower()
                            msg_content = msg_obj.content

                            # Map LangChain message types to our format
                            if "human" in msg_type:
                                messages.append(
                                    {"content": msg_content, "type": "human"}
                                )
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
                                messages.append(
                                    {"content": msg_content, "type": "human"}
                                )
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
                        logger.debug(
                            f"Message type: {msg_type}, content: {msg_content}"
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
                        logger.warning(f"Invalid message format: {msg_tuple}")

            logger.debug(f"Extracted {len(messages)} messages")
            for i, msg in enumerate(messages):
                logger.debug(f"Extracted message {i}: {msg}")

            # Get thread ownership information for metadata
            # Use the base conversation ID (without user scope) for ownership lookup
            base_conversation_id = conversation_id
            if conversation_id.startswith("user:"):
                parts = conversation_id.split(":", 2)
                if len(parts) >= 3:
                    base_conversation_id = parts[2]

            thread_ownership = await access_control.get_thread_ownership(
                base_conversation_id
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
        user_context = get_user_context_safe(req)
        user_id = user_context.user_id

        # Get services
        access_control = get_access_control_service()
        checkpointer = get_checkpointing_service()

        try:
            # Get all threads owned by the user
            user_threads = await access_control.list_user_threads(user_id)

            conversations = []

            for thread_ownership in user_threads:
                conversation_id = thread_ownership.thread_id

                # Create user-scoped conversation ID for LangGraph
                user_scoped_conversation_id = (
                    await access_control.create_user_scoped_thread_id(
                        user_id, conversation_id
                    )
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
                    conversation_id=user_scoped_conversation_id,
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

            # Get user context for headers
            user_context = get_user_context_safe(req)

            return SSEStreamingResponse(
                generate(),
                headers=get_conversation_headers(conversation_id, user_context.user_id),
            )
        else:
            # Return JSON response
            try:
                result = await agent.ainvoke(agent_input, config=agent_config)
                serialized_result = serialize_event(result)
                # Get user context for headers
                user_context = get_user_context_safe(req)

                return Response(
                    content=json.dumps({"output": serialized_result}),
                    media_type="application/json",
                    headers=get_conversation_headers(
                        conversation_id, user_context.user_id
                    ),
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
        description="Delete a conversation by ID. This will permanently remove the conversation and all its data.",
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
        """
        return await _handle_delete_conversation_internal(conversation_id, req)

    async def _handle_delete_conversation_internal(
        conversation_id: str, req: Request
    ) -> Response:
        """
        Internal handler for deleting conversation.
        """
        # Get user context for access control
        user_context = get_user_context_safe(req)
        user_id = user_context.user_id

        # Get services
        access_control = get_access_control_service()
        checkpointer = get_checkpointing_service()

        try:
            # Validate and scope conversation ID
            user_scoped_conversation_id = await validate_and_scope_conversation_id(
                conversation_id, user_id, access_control
            )

            # Delete the checkpoint state from LangGraph
            try:
                # LangGraph MemorySaver doesn't have a delete method, but we can try to clear it
                # by setting it to None or an empty state
                await checkpointer.aput(
                    {"configurable": {"thread_id": user_scoped_conversation_id}}, None
                )
                logger.debug(
                    f"Cleared checkpoint state for conversation {conversation_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to clear checkpoint state: {e}")
                # Continue with deletion even if checkpoint clearing fails

            # Extract base UUID for access control (access control stores base UUIDs)
            base_conversation_id = extract_base_conversation_id(conversation_id)

            # Delete the thread ownership record
            deleted = await access_control.delete_thread(user_id, base_conversation_id)
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
