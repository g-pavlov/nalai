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
from ..core import create_agent
from ..utils.logging import setup_logging
from .api_agent import create_agent_api
from .api_conversations import (
    APP_DESCRIPTION,
    APP_TITLE,
    APP_VERSION,
    OPENAPI_TAGS,
    create_conversations_api,
)
from .api_system import create_server_api
from .middleware import (
    create_audit_middleware,
    create_auth_middleware,
    create_log_request_middleware,
    create_user_context_middleware,
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
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
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


def initialize_app():
    """Initialize the application components."""
    global _initialized
    if _initialized:
        return

    # Mount UI static files
    ui_path = Path(__file__).parent.parent.parent.parent / "demo" / "ui"
    logger.info(f"Attempting to mount UI from path: {ui_path}")
    logger.info(f"Path exists: {ui_path.exists()}")
    logger.info(f"Path is absolute: {ui_path.is_absolute()}")
    logger.info(f"Current working directory: {Path.cwd()}")

    if ui_path.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_path)), name="ui")
        logger.info(f"Mounted UI static files from {ui_path}")
    else:
        logger.warning(f"UI directory not found at {ui_path}")
        # Try alternative paths
        alt_paths = [
            Path.cwd() / "demo" / "ui",
            Path.cwd()
            / "src"
            / "nalai"
            / "server"
            / ".."
            / ".."
            / ".."
            / ".."
            / "demo"
            / "ui",
        ]
        for alt_path in alt_paths:
            logger.info(f"Trying alternative path: {alt_path}")
            if alt_path.exists():
                app.mount("/ui", StaticFiles(directory=str(alt_path)), name="ui")
                logger.info(
                    f"Mounted UI static files from alternative path: {alt_path}"
                )
                break

    # Create basic routes
    create_server_api(app)

    # Initialize agent and create conversation routes
    agent = create_agent()
    create_conversations_api(app, agent)

    # Create agent message exchange routes
    create_agent_api(app, agent)

    logger.info("Application routes initialized")
    _initialized = True


# Initialize the application
initialize_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.nalai.server.app:app", host="0.0.0.0", port=8000, reload=True)
