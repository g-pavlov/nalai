"""
Route handlers for API Assistant server.

This module contains FastAPI route handlers for basic endpoints
and agent endpoints with access control integration.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
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
    default_modify_runtime_config_with_access_control,
    default_validate_runtime_config,
    setup_runtime_config_with_access_control,
)

logger = logging.getLogger("nalai")


def create_basic_routes(app: FastAPI) -> None:
    """Create basic endpoint routes."""

    @app.get("/")
    async def redirect_root_to_docs() -> RedirectResponse:
        return RedirectResponse("/ui")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "Healthy"}

    @app.get("/ui", response_class=HTMLResponse)
    async def serve_ui() -> HTMLResponse:
        """Serve the demo UI."""
        # Calculate path from the current file location to the demo directory
        # From src/api_assistant/server/routes.py -> ../../../../demo/simple_ui.html
        ui_path = Path(__file__).parent.parent.parent.parent / "demo" / "simple_ui.html"
        if ui_path.exists():
            with open(ui_path, encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            raise HTTPException(status_code=404, detail="UI file not found")

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
    ] = default_modify_runtime_config_with_access_control,
    format_sse_event: Callable[[str, str], str] = format_sse_event_default,
    agent_name: str = "nalai",
    tool_node=None,
) -> None:
    """Create agent endpoint routes with access control."""

    @app.post(f"/{agent_name}/invoke", response_model=AgentInvokeResponse)
    async def handle_agent_invoke(
        request: AgentInvokeRequest, req: Request
    ) -> AgentInvokeResponse:
        """Invoke the agent synchronously with access control."""
        # Validate input content
        validate_agent_input(request.input.messages)

        # Set up runtime configuration with access control
        (
            agent_config,
            user_scoped_thread_id,
        ) = await setup_runtime_config_with_access_control(
            request.config,
            req,
            default_modify_runtime_config_with_access_control,
            validate_runtime_config,
        )

        # Convert structured input to dict for agent (using LangGraph format)
        agent_input = request.input.model_dump()

        # Use the processed config that has user-scoped thread_id properly set
        final_config = agent_config

        # Invoke the agent
        result = await agent.ainvoke(agent_input, config=final_config)

        return AgentInvokeResponse(output=result)

    @app.post(f"/{agent_name}/stream_events")
    async def handle_agent_stream_events(
        request: AgentStreamEventsRequest, req: Request
    ) -> StreamingResponse:
        """Stream events from the agent with optional filtering and access control."""
        # Validate input content
        validate_agent_input(request.input.messages)

        # Set up runtime configuration with access control
        (
            agent_config,
            user_scoped_thread_id,
        ) = await setup_runtime_config_with_access_control(
            request.config,
            req,
            default_modify_runtime_config_with_access_control,
            validate_runtime_config,
        )

        async def generate():
            allowed_events = request.allowed_events or [
                "on_chat_model_stream",
                "on_chat_model_start",
                "on_chat_model_end",
                "on_tool_start",
                "on_tool_stream",
                "on_tool_end",
                "on_chain_stream",
                "on_chain_start",
                "on_chain_end",
            ]
            agent_input = request.input.model_dump()

            async for event in agent.astream_events(
                agent_input, config=agent_config, stream_mode="values"
            ):
                try:
                    # Log the raw event for debugging
                    logger.debug(f"Raw event type: {type(event)}, event: {event}")

                    if event is not None:
                        # Debug mode: bypass filtering and pass through all events
                        if getattr(request, "debug", False):
                            formatted_event = format_sse_event(
                                "data", json.dumps(serialize_event(event))
                            )
                            logger.debug(
                                f"Debug mode - passing through all events: {formatted_event}"
                            )
                            yield formatted_event
                        else:
                            # Normal mode: apply filtering
                            formatted_event = process_and_format_event(
                                event, allowed_events, serialize_event, format_sse_event
                            )
                            logger.debug(f"Formatted event: {formatted_event}")
                            if formatted_event:
                                yield formatted_event
                    else:
                        logger.debug("Event was None")
                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
                    # Pass through the original event as fallback
                    formatted_event = process_and_format_event(
                        event, allowed_events, serialize_event, format_sse_event
                    )
                    if formatted_event:
                        yield formatted_event

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"X-Thread-ID": user_scoped_thread_id},
        )

    @app.post(f"/{agent_name}/human-review")
    async def handle_human_review(
        req: Request, raw_body: str = Body(..., media_type="application/json")
    ) -> StreamingResponse:
        """Handle human review requests with access control."""
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

        # Set up runtime configuration with access control
        (
            agent_config,
            user_scoped_thread_id,
        ) = await setup_runtime_config_with_access_control(
            request_payload,
            req,
            default_modify_runtime_config_with_access_control,
            validate_runtime_config,
        )

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
