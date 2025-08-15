"""
Route handlers for API Assistant server.

This module contains FastAPI route handlers for basic endpoints
and agent endpoints with access control integration.
"""

import json
import logging
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from langgraph.graph.state import CompiledStateGraph

from ..config import BaseRuntimeConfiguration, settings
from .event_handlers import (
    serialize_event_default,
    stream_events,
)
from .models import (
    AgentInvokeRequest,
    AgentInvokeResponse,
    HealthzResponse,
    InterruptResponse,
    ToolInterruptRequest,
    ToolInterruptSyncResponse,
)
from .models.validation import (
    validate_agent_input,
    validate_tool_interrupt_response_type,
)
from .runtime_config import (
    default_modify_runtime_config,
    default_validate_runtime_config,
    validate_external_thread_id,
    validate_thread_access_and_scope,
)

logger = logging.getLogger("nalai")


class SSEStreamingResponse(StreamingResponse):
    """Custom response class for Server-Sent Events with proper media type."""

    media_type = "text/event-stream"


# Response examples for streaming endpoints
streaming_response_examples = {
    200: {
        "description": "Server-Sent Events stream with real-time agent updates",
        "content": {
            "text/event-stream": {
                "example": """data: {"messages": [{"content": "Hello", "type": "ai"}], "selected_apis": [], "cache_miss": null}

data: {"messages": [{"content": "Processing your request...", "type": "ai"}], "selected_apis": [{"title": "Ecommerce API", "version": "1.0"}], "cache_miss": "miss"}

data: {"messages": [{"content": "Here are the products:", "type": "ai"}], "selected_apis": [], "cache_miss": null}

"""
            }
        },
        "headers": {
            "X-Thread-ID": {
                "description": "Thread ID for conversation management and resume capability",
                "schema": {"type": "string"},
            }
        },
    },
    422: {
        "description": "Validation Error",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
            }
        },
    },
}


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


def create_agent_routes(
    app: FastAPI,
    agent: CompiledStateGraph,
    *,
    validate_runtime_config: Callable[
        [dict], BaseRuntimeConfiguration
    ] = default_validate_runtime_config,
    serialize_event: Callable[[object], object] = serialize_event_default,
    modify_runtime_config: Callable[
        [dict, Request], dict
    ] = default_modify_runtime_config,
    agent_name: str = "agent",
) -> None:
    """Create agent endpoint routes."""
    """Create agent endpoint routes."""

    async def setup_runtime_config(
        config: dict, req: Request, is_initial_request: bool = True
    ) -> tuple[dict, str]:
        """
        Lean runtime configuration setup.

        Args:
            config: Configuration dictionary
            req: FastAPI request object
            is_initial_request: True for initial chat requests, False for resume operations
        """
        if is_initial_request:
            # For initial requests: create user-scoped thread ID if needed
            config, user_scoped_thread_id = await validate_thread_access_and_scope(
                config, req
            )
            validate_runtime_config(config)
            return config, user_scoped_thread_id
        else:
            # For resume operations: validate existing thread ID format only
            agent_config = modify_runtime_config(config, req)
            validate_runtime_config(agent_config)
            thread_id = agent_config.get("configurable", {}).get("thread_id", "unknown")
            # Validate the thread ID format without re-scoping
            validate_external_thread_id(thread_id)
            return agent_config, thread_id

    async def _handle_tool_interrupt_internal(
        request: ToolInterruptRequest, req: Request, streaming: bool = True
    ) -> StreamingResponse | Response:
        """Handle tool-level interrupt requests with access control (internal)."""
        validate_tool_interrupt_response_type(request.response_type)

        logger.info(
            f"Tool interrupt response: {request.response_type} for thread: {request.thread_id}"
        )

        # Map tool interrupt response to the format expected by the interrupt system
        if request.response_type == "accept":
            interrupt_response = InterruptResponse(type="accept")
        elif request.response_type == "edit":
            interrupt_response = InterruptResponse(
                type="edit", args={"args": request.args}
            )
        elif request.response_type == "response":
            interrupt_response = InterruptResponse(type="response", args=request.args)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported response type: {request.response_type}",
            )

        # Convert request to dict for configuration setup
        request_payload = request.model_dump()
        # Ensure configurable exists
        if "configurable" not in request_payload:
            request_payload["configurable"] = {}

        # Use the already scoped thread ID directly - no need to re-process
        # The thread ID from the request is already scoped and validated
        request_payload["configurable"]["thread_id"] = request.thread_id

        # For resume operations: validate existing thread ID format without re-scoping
        agent_config, thread_id = await setup_runtime_config(
            request_payload, req, is_initial_request=False
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
                headers={
                    "X-Thread-ID": request.thread_id
                },  # Use the same scoped thread ID
            )
        else:
            # For synchronous resume, invoke the agent directly
            from langgraph.types import Command

            result = await agent.ainvoke(
                Command(resume=[interrupt_response.model_dump()]), config=agent_config
            )

            # Serialize the result using the same function as streaming
            serialized_result = serialize_event(result)

            # Return the result with thread_id header
            return Response(
                content=json.dumps({"output": serialized_result}),
                media_type="application/json",
                headers={
                    "X-Thread-ID": request.thread_id
                },  # Use the same scoped thread ID
            )

    # Converged chat endpoint
    @app.post(
        f"{settings.api_prefix}/{agent_name}/chat",
        response_model=None,  # Disable automatic response model for union types
        tags=["Agent API v1"],
        summary="Handle Chat",
        description="Chat endpoint. Accepts messages and returns agent response in a converrsation.",
        responses={
            200: {
                "description": """
Successful Response.

The response type is determined by the media type in the **Accept** request header:  
- **Server-Side Event Streaming**: `text/event-stream`  
- **JSON**: `application/json`

The response **X-Thread-ID** header contains the thread ID for conversation management and resume capability.
                """,  # noqa: W291
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/AgentInvokeResponse"}
                    },
                    "text/event-stream": {
                        "example": """data: {"messages": [{"content": "Hello", "type": "ai"}], "selected_apis": [], "cache_miss": null}

data: {"messages": [{"content": "Processing your request...", "type": "ai"}], "selected_apis": [{"title": "Ecommerce API", "version": "1.0"}], "cache_miss": "miss"}

"""
                    },
                },
                "headers": {
                    "X-Thread-ID": {
                        "description": "Thread ID for conversation management and resume capability",
                        "schema": {"type": "string"},
                    }
                },
            },
            422: {
                "description": "Validation Error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                    }
                },
            },
        },
    )
    async def handle_converged_chat(
        request: AgentInvokeRequest, req: Request
    ) -> AgentInvokeResponse | StreamingResponse:
        """
        Converged chat endpoint that handles both JSON and streaming responses.
        Use Accept: text/event-stream header for streaming response.
        """
        # Check Accept header to determine response type
        accept_header = req.headers.get("accept", "text/event-stream")
        streaming = "text/event-stream" in accept_header

        return await _handle_converged_chat_internal(request, req, streaming=streaming)

    async def _handle_converged_chat_internal(
        request: AgentInvokeRequest, req: Request, streaming: bool = False
    ) -> AgentInvokeResponse | StreamingResponse:
        """
        Internal handler for converged chat operations.
        """
        # Validate input content
        validate_agent_input(request.input.messages)

        # Set up runtime configuration
        agent_config, thread_id = await setup_runtime_config(
            request.config, req, is_initial_request=True
        )

        # Convert structured input to dict for agent (using LangGraph format)
        agent_input = request.input.model_dump()

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
                headers={"X-Thread-ID": thread_id},
            )
        else:
            # Return synchronous response
            result = await agent.ainvoke(agent_input, config=agent_config)

            # Return response with thread_id header for conversation management and resume capability
            response_data = AgentInvokeResponse(output=result)
            return Response(
                content=response_data.model_dump_json(),
                media_type="application/json",
                headers={"X-Thread-ID": thread_id},
            )

    # Converged resume endpoint
    @app.post(
        f"{settings.api_prefix}/{agent_name}/resume-decision",
        response_model=None,  # Disable automatic response model for union types
        tags=["Agent API v1"],
        summary="Handle Resume Agent Workflow",
        description="""Resume an agent workflow that was interrupted for tool execution approval with a decision. An interface for implementing human-in-the-loop.  
        Use the thread ID of the interrupted workflow conversation to resume it.
        """,  # noqa: W291
        responses={
            200: {
                "description": """
Successful Response.

The response type is determined by the media type in the **Accept** request header:  
- **Server-Side Event Streaming**: `text/event-stream`  
- **JSON**: `application/json`

The response **X-Thread-ID** header contains the thread ID for conversation management and resume capability.
                """,  # noqa: W291
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ToolInterruptSyncResponse"
                        }
                    },
                    "text/event-stream": {
                        "example": """data: {"messages": [{"content": "Resuming...", "type": "ai"}], "selected_apis": [], "cache_miss": null}

data: {"messages": [{"content": "Tool execution completed", "type": "ai"}], "selected_apis": [], "cache_miss": null}

"""
                    },
                },
                "headers": {
                    "X-Thread-ID": {
                        "description": "Thread ID for conversation management and resume capability",
                        "schema": {"type": "string"},
                    }
                },
            },
            422: {
                "description": "Validation Error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                    }
                },
            },
        },
    )
    async def handle_converged_resume(
        request: ToolInterruptRequest, req: Request
    ) -> ToolInterruptSyncResponse | StreamingResponse:
        """
        Converged resume endpoint that handles both JSON and streaming responses.
        Use Accept: application/json header for JSON response.
        """
        # Check Accept header to determine response type
        accept_header = req.headers.get("accept", "text/event-stream")
        streaming = "text/event-stream" in accept_header

        return await _handle_converged_resume_internal(
            request, req, streaming=streaming
        )

    async def _handle_converged_resume_internal(
        request: ToolInterruptRequest, req: Request, streaming: bool = False
    ) -> ToolInterruptSyncResponse | StreamingResponse:
        """
        Internal handler for converged resume operations.
        """
        validate_tool_interrupt_response_type(request.response_type)

        logger.info(
            f"Tool interrupt response: {request.response_type} for thread: {request.thread_id}"
        )

        # Map tool interrupt response to the format expected by the interrupt system
        if request.response_type == "accept":
            interrupt_response = InterruptResponse(type="accept")
        elif request.response_type == "edit":
            interrupt_response = InterruptResponse(
                type="edit", args={"args": request.args}
            )
        elif request.response_type == "response":
            interrupt_response = InterruptResponse(type="response", args=request.args)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported response type: {request.response_type}",
            )

        # Convert request to dict for configuration setup
        request_payload = request.model_dump()
        # Ensure configurable exists
        if "configurable" not in request_payload:
            request_payload["configurable"] = {}

        # Use the already scoped thread ID directly - no need to re-process
        # The thread ID from the request is already scoped and validated
        request_payload["configurable"]["thread_id"] = request.thread_id

        # For resume operations: validate existing thread ID format without re-scoping
        agent_config, thread_id = await setup_runtime_config(
            request_payload, req, is_initial_request=False
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
                headers={
                    "X-Thread-ID": request.thread_id
                },  # Use the same scoped thread ID
            )
        else:
            # For synchronous resume, invoke the agent directly
            from langgraph.types import Command

            result = await agent.ainvoke(
                Command(resume=[interrupt_response.model_dump()]), config=agent_config
            )

            # Serialize the result using the same function as streaming
            serialized_result = serialize_event(result)

            # Return the result with thread_id header
            return Response(
                content=json.dumps({"output": serialized_result}),
                media_type="application/json",
                headers={
                    "X-Thread-ID": request.thread_id
                },  # Use the same scoped thread ID
            )
