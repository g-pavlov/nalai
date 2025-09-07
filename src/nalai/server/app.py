"""
Web Server servicing the Agent API.

This module sets up the FastAPI application with middleware,
routes, and agent initialization.
"""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from langgraph.graph import StateGraph

from ..config import settings
from ..utils.logging import setup_logging
from .agent_routes import create_agent_routes
from .api_conversations import APP_DESCRIPTION, APP_TITLE, APP_VERSION, OPENAPI_TAGS
from .api_system import create_server_api
from .middleware import (
    create_audit_middleware,
    create_auth_middleware,
    create_log_request_middleware,
    create_user_context_middleware,
)
from .ui_routes import create_ui_route

# Load environment variables
load_dotenv()

# Set up dynamic logging configuration
setup_logging(settings.logging_config_path)
logging.captureWarnings(True)

logger = logging.getLogger("nalai")

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {"/healthz", "/docs", "/", "/ui"}

# Pre-create middleware functions for efficiency
log_middleware = create_log_request_middleware(excluded_paths=PUBLIC_ENDPOINTS)
auth_middleware = create_auth_middleware(excluded_paths=PUBLIC_ENDPOINTS)
user_context_middleware = create_user_context_middleware(
    excluded_paths=PUBLIC_ENDPOINTS
)
audit_middleware = create_audit_middleware(excluded_paths=PUBLIC_ENDPOINTS)

# Create FastAPI application with conditional OpenAPI settings
openapi_config = {
    "title": APP_TITLE,
    "version": APP_VERSION,
    "description": APP_DESCRIPTION,
    "openapi_tags": OPENAPI_TAGS,
}

if settings.api_docs_endpoint_enabled:
    openapi_config.update(
        {
            "openapi_url": "/openapi.json",
            "docs_url": "/docs",
            "redoc_url": "/redoc",
        }
    )
    logger.info(
        f"OpenAPI docs endpoints enabled: {openapi_config['openapi_url']}, {openapi_config['docs_url']}, {openapi_config['redoc_url']}"
    )
else:
    openapi_config.update(
        {
            "openapi_url": None,
            "docs_url": None,
            "redoc_url": None,
        }
    )
    logger.info("OpenAPI endpoints disabled")

app = FastAPI(**openapi_config)

# Configure CORS from environment variable
allowed_origins = settings.cors_origins_list

if allowed_origins:
    # Add CORS middleware for custom UI (must be first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Register middleware - explicit and readable
@app.middleware("http")
async def log_request_middleware(request: Request, call_next):
    """Log incoming requests for monitoring and debugging."""
    return await log_middleware(request, call_next)


@app.middleware("http")
async def auth_middleware_wrapper(request: Request, call_next):
    """Authenticate requests using the auth service."""
    return await auth_middleware(request, call_next)


@app.middleware("http")
async def user_context_middleware_wrapper(request: Request, call_next):
    """Extract and inject user context from authentication."""
    return await user_context_middleware(request, call_next)


@app.middleware("http")
async def audit_middleware_wrapper(request: Request, call_next):
    """Log audit events for all requests."""
    return await audit_middleware(request, call_next)


# Initialize application components
_initialized = False


def create_agent_workflow() -> StateGraph:
    # Initialize agent and create conversation routes
    from ..workflow.workflow import create_workflow
    from ..workflow.workflow_nodes import WorkflowNodes

    nodes = WorkflowNodes()
    logger.info("Creating workflow")
    workflow = create_workflow(nodes)
    return workflow


def initialize_app():
    """Initialize the application components."""
    global _initialized
    if _initialized:
        return

    if settings.api_docs_endpoint_enabled:

        @app.get("/", include_in_schema=False)
        async def redirect_root_to_docs() -> RedirectResponse:
            return RedirectResponse("/docs")

    if settings.ui_enabled:
        create_ui_route(app)
        logger.info("UI enabled: /ui")

    if settings.system_endpoint_enabled:
        # Create basic routes
        create_server_api(app)
        logger.info("System API endpoint enabled")

    # Initialize agent and create routes for it
    workflow = create_agent_workflow()
    create_agent_routes(app, workflow)

    logger.info("Application routes initialized")
    _initialized = True


# Initialize the application
initialize_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.nalai.server.app:app", host="0.0.0.0", port=8000, reload=True)
