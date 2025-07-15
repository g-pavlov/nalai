"""
API Assistant Server Entry Point.

This module provides the main FastAPI application with access control,
middleware, and route configuration.
"""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request

from ..config import settings
from ..core.agent import APIAssistant
from ..core.workflow import create_and_compile_workflow
from ..utils.logging import setup_logging
from ..services.checkpointing_service import get_checkpointer
from .middleware import (
    create_log_request_middleware,
    create_user_context_middleware,
    create_auth_middleware,
    create_audit_middleware,
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

logger = logging.getLogger("api-assistant")

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {"/healthz", "/docs", "/"}

# Pre-create middleware functions for efficiency
log_middleware = create_log_request_middleware(excluded_paths=PUBLIC_ENDPOINTS)
auth_middleware = create_auth_middleware(excluded_paths=PUBLIC_ENDPOINTS)
user_context_middleware = create_user_context_middleware(excluded_paths=PUBLIC_ENDPOINTS)
audit_middleware = create_audit_middleware(excluded_paths=PUBLIC_ENDPOINTS)


# Create FastAPI application
app = FastAPI(
    title="API Assistant Server",
    version="1.0",
    description="API Assistant powered by LangGraph"
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
def initialize_app():
    """Initialize the application components."""
    # Create basic routes
    create_basic_routes(app)
    
    # Initialize agent and create agent routes
    memory_store = get_checkpointer()
    agent = APIAssistant()
    agent_workflow = create_and_compile_workflow(agent, memory_store)
    create_agent_routes(app, agent_workflow)
    
    logger.info("Application routes initialized")


# Initialize the application
initialize_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api_assistant.server.app:app", host="0.0.0.0", port=8000, reload=True)
