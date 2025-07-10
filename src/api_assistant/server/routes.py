"""
Route handlers for API Assistant server.

This module contains FastAPI route handlers for basic endpoints,
agent endpoints, and custom router endpoints.
"""

import logging
from collections.abc import Callable

from fastapi import Body, FastAPI, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from langgraph.graph.state import CompiledStateGraph

from ..config import BaseRuntimeConfiguration
from .event_handlers import (
    format_sse_event_default,
    process_and_format_event,
    serialize_event_default,
    stream_interruptable_events,
)
from .models import (
    AgentInvokeRequest,
    AgentInvokeResponse,
    AgentStreamEventsRequest,
    HumanReviewRequest,
)
from .models.validation import (
    validate_agent_input,
    validate_human_review_action,
    validate_json_body,
)
from .runtime_config import (
    default_modify_runtime_config,
    default_validate_runtime_config,
    setup_runtime_config,
)

logger = logging.getLogger("api-assistant")


def create_basic_routes(app: FastAPI) -> None:
    """Create basic endpoint routes."""

    @app.get("/")
    async def redirect_root_to_docs() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "Healthy"}

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
    format_sse_event: Callable[[str, str], str] = format_sse_event_default,
    agent_name: str = "api-assistant",
) -> None:
    """Create agent endpoint routes."""

    @app.post(f"/{agent_name}/invoke", response_model=AgentInvokeResponse)
    async def handle_agent_invoke(
        request: AgentInvokeRequest, req: Request
    ) -> AgentInvokeResponse:
        """Invoke the agent synchronously."""
        # Validate input content
        validate_agent_input(request.input.messages)

        # Set up runtime configuration
        agent_config, _ = setup_runtime_config(
            request.config, req, modify_runtime_config, validate_runtime_config
        )

        # Convert structured input to dict for agent (using LangGraph format)
        agent_input = request.input.model_dump()

        # Use the processed config that has thread_id properly set
        final_config = agent_config

        # Invoke the agent
        result = await agent.ainvoke(agent_input, config=final_config)

        return AgentInvokeResponse(output=result)

    @app.post(f"/{agent_name}/stream_events")
    async def handle_agent_stream_events(
        request: AgentStreamEventsRequest, req: Request
    ) -> StreamingResponse:
        """Stream events from the agent with optional filtering."""
        # Validate input content
        validate_agent_input(request.input.messages)

        # Set up runtime configuration
        agent_config, _ = setup_runtime_config(
            request.config, req, modify_runtime_config, validate_runtime_config
        )

        async def generate():
            # Default allowed events if none specified
            allowed_events = request.allowed_events or [
                "on_chat_model_stream",
                "on_tool_end",
                "on_chain_stream",
            ]

            # Convert structured input to dict for agent (using LangGraph format)
            agent_input = request.input.model_dump()

            async for event in agent.astream_events(
                agent_input, config=agent_config, stream_mode="values"
            ):
                # Handle both StandardStreamEvent and CustomStreamEvent
                # Both are TypedDict types, so they behave like dictionaries
                if isinstance(event, dict):
                    formatted_event = process_and_format_event(
                        event, allowed_events, serialize_event, format_sse_event
                    )
                    if formatted_event:
                        yield formatted_event

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post(f"/{agent_name}/human-review")
    async def handle_human_review(
        req: Request, raw_body: str = Body(..., media_type="application/json")
    ) -> StreamingResponse:
        """Handle human review requests."""
        parsed_body = validate_json_body(raw_body)
        request = HumanReviewRequest(**parsed_body)
        validate_human_review_action(request.action)

        logger.info(
            f"Human review action: {request.action} for thread: {request.thread_id}"
        )

        resume_input = {"action": request.action}
        if request.action in ["update", "feedback"]:
            resume_input["data"] = request.data

        request_payload = await req.json()
        # Ensure thread_id exists (use the one from request if provided)
        if request.thread_id:
            # Convert to dict if it's a Pydantic model
            if hasattr(request_payload, "model_dump"):
                request_payload = request_payload.model_dump()
            # Ensure configurable exists
            if "configurable" not in request_payload:
                request_payload["configurable"] = {}
            request_payload["configurable"]["thread_id"] = request.thread_id

        agent_config = modify_runtime_config(request_payload, req)

        return StreamingResponse(
            stream_interruptable_events(
                agent,
                resume_input,
                agent_config,
                serialize_event=serialize_event,
                format_sse_event=format_sse_event,
            ),
            media_type="text/event-stream",
            headers={"X-Thread-ID": request.thread_id},
        )
