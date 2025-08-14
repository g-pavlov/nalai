"""
Route handlers for API Assistant server.

This module contains FastAPI route handlers for basic endpoints
and agent endpoints with access control integration.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from langgraph.graph.state import CompiledStateGraph

from ..config import BaseRuntimeConfiguration
from .event_handlers import (
    serialize_event_default,
    stream_events,
)
from .models import (
    AgentInvokeRequest,
    AgentInvokeResponse,
    AgentStreamEventsRequest,
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

    @app.get("/")
    async def redirect_root_to_docs() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "Healthy"}

    @app.get("/ui", response_class=HTMLResponse)
    async def serve_ui() -> HTMLResponse:
        """Serve the demo UI."""
        # Calculate path from the current file location to the demo directory
        # From src/nalai/server/routes.py -> ../../../../demo/ui/ai-chat.html
        ui_path = (
            Path(__file__).parent.parent.parent.parent / "demo" / "ui" / "ai-chat.html"
        )
        if ui_path.exists():
            with open(ui_path, encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            raise HTTPException(status_code=404, detail="UI file not found")

    @app.get("/ui/styles.css")
    async def serve_css() -> Response:
        """Serve the CSS file."""
        css_path = (
            Path(__file__).parent.parent.parent.parent / "demo" / "ui" / "styles.css"
        )
        if css_path.exists():
            with open(css_path, encoding="utf-8") as f:
                return Response(content=f.read(), media_type="text/css")
        else:
            raise HTTPException(status_code=404, detail="CSS file not found")

    @app.get("/ui/script.js")
    async def serve_js() -> Response:
        """Serve the JavaScript file."""
        js_path = (
            Path(__file__).parent.parent.parent.parent / "demo" / "ui" / "script.js"
        )
        if js_path.exists():
            with open(js_path, encoding="utf-8") as f:
                return Response(content=f.read(), media_type="application/javascript")
        else:
            raise HTTPException(status_code=404, detail="JavaScript file not found")

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
    agent_name: str = "nalai",
) -> None:
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
            agent_config = await modify_runtime_config(config, req)
            validate_runtime_config(agent_config)
            thread_id = agent_config.get("configurable", {}).get("thread_id", "unknown")
            # Validate the thread ID format without re-scoping
            validate_external_thread_id(thread_id)
            return agent_config, thread_id

    @app.post(
        f"/{agent_name}/chat/invoke",
        response_model=AgentInvokeResponse,
        responses={
            200: {
                "description": "Successful Response",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/AgentInvokeResponse"}
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
        },
    )
    async def handle_chat_invoke(
        request: AgentInvokeRequest, req: Request
    ) -> AgentInvokeResponse:
        """
        Invoke the agent synchronously.

        Returns the agent response along with an X-Thread-ID header that can be used
        for conversation management and resuming interrupted workflows via the resume endpoint.
        """
        # Validate input content
        validate_agent_input(request.input.messages)

        # Set up runtime configuration
        agent_config, thread_id = await setup_runtime_config(
            request.config, req, is_initial_request=True
        )

        # Convert structured input to dict for agent (using LangGraph format)
        agent_input = request.input.model_dump()

        # Invoke the agent
        result = await agent.ainvoke(agent_input, config=agent_config)

        # Return response with thread_id header for conversation management and resume capability
        response_data = AgentInvokeResponse(output=result)
        return Response(
            content=response_data.model_dump_json(),
            media_type="application/json",
            headers={"X-Thread-ID": thread_id},
        )

    @app.post(f"/{agent_name}/chat/stream", responses=streaming_response_examples)
    async def handle_chat_stream(
        request: AgentStreamEventsRequest, req: Request
    ) -> StreamingResponse:
        """Stream events from the agent with optional filtering."""
        # Validate input content
        validate_agent_input(request.input.messages)

        # Set up runtime configuration
        agent_config, thread_id = await setup_runtime_config(
            request.config, req, is_initial_request=True
        )

        async def generate():
            agent_input = request.input.model_dump()
            # Use stream_events_with_api_interruptions to handle interrupts properly
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

    @app.post(f"/{agent_name}/resume/stream", responses=streaming_response_examples)
    async def handle_resume_stream(
        request: ToolInterruptRequest, req: Request
    ) -> StreamingResponse:
        """
        Handle tool-level interrupt requests with streaming response.

        **Use Case**: Resume interrupted streaming workflows from /chat/stream endpoint.
        **Response**: Server-sent events stream with real-time updates.
        """
        return await _handle_tool_interrupt_internal(request, req, streaming=True)

    @app.post(
        f"/{agent_name}/resume/invoke",
        response_model=ToolInterruptSyncResponse,
        summary="Resume interrupted batch workflow",
        description="Resume an interrupted batch workflow from /chat/invoke endpoint. Returns single JSON response.",
        responses={
            200: {
                "description": "Synchronous response with agent output and X-Thread-ID header",
                "headers": {
                    "X-Thread-ID": {
                        "description": "Thread ID for conversation management and resume capability",
                        "schema": {"type": "string"},
                    }
                },
            }
        },
    )
    async def handle_resume_invoke(
        request: ToolInterruptRequest, req: Request
    ) -> ToolInterruptSyncResponse:
        """
        Handle tool-level interrupt requests with synchronous response.

        **Use Case**: Resume interrupted batch workflows from /chat/invoke endpoint.
        **Response**: Single JSON response with complete agent output.
        **Headers**: X-Thread-ID for conversation management.
        """
        result = await _handle_tool_interrupt_internal(request, req, streaming=False)
        # Convert Response to ToolInterruptSyncResponse
        import json

        response_data = json.loads(result.body.decode())
        return ToolInterruptSyncResponse(output=response_data["output"])

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
