"""
Web Server servicing the Agent API.

This module sets up the FastAPI application with middleware,
routes, and agent initialization.
"""

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..config import settings
from ..core.agent import APIAgent
from ..core.workflow import create_and_compile_workflow
from ..services.checkpointing_service import get_checkpointer
from ..utils.logging import setup_logging
from .middleware import (
    create_audit_middleware,
    create_auth_middleware,
    create_log_request_middleware,
    create_user_context_middleware,
)
from .routes import (
    create_agent_routes,
    create_basic_routes,
)

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


# Create FastAPI application
app = FastAPI(
    title="AI Agent Server",
    version="1.0",
    description="An AI Agent Server implementing chat and tool calling capabilities",
    openapi_tags=[
        {
            "name": "Agent API v1",
            "description": "Agent interaction endpoints for API v1",
        },
        {
            "name": "System",
            "description": "System health and utility endpoints",
        },
    ],
)

# Configure CORS from environment variable
allowed_origins = settings.cors_origins_list

# Add CORS middleware for custom UI (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register middleware
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


def initialize_app():
    """Initialize the application components."""
    global _initialized
    if _initialized:
        return

    # Mount UI static files
    ui_path = Path(__file__).parent.parent.parent.parent / "demo" / "ui"
    if ui_path.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_path)), name="ui")
        logger.info(f"Mounted UI static files from {ui_path}")
    else:
        logger.warning(f"UI directory not found at {ui_path}")

    # Create basic routes
    create_basic_routes(app)

    # Initialize agent and create agent routes
    memory_store = get_checkpointer()
    agent = APIAgent()
    agent_workflow = create_and_compile_workflow(agent, memory_store)
    create_agent_routes(app, agent_workflow)

    logger.info("Application routes initialized")
    _initialized = True


# Initialize the application
initialize_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.nalai.server.app:app", host="0.0.0.0", port=8000, reload=True)
