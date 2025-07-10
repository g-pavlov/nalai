import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from langgraph.checkpoint.memory import MemorySaver

from ..config import settings
from ..core.agent import APIAssistant
from ..core.workflow import create_and_compile_workflow
from ..utils.logging import setup_logging
from .middleware import (
    create_log_request_middleware,
    create_user_context_middleware,
)
from .routes import (
    create_agent_routes,
    create_basic_routes,
)
from .runtime_config import (
    modify_runtime_config,
    validate_runtime_config,
)

load_dotenv()

# Set up dynamic logging configuration
setup_logging(settings.logging_config_path)

logging.captureWarnings(True)

app = FastAPI(
    title="API Assistant Server",
    version="1.0",
    description="API Assistant powered by LangGraph",
)

logger = logging.getLogger("api-assistant")

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {"/healthz", "/docs", "/"}


# Register middleware with public endpoint exclusions
@app.middleware("http")
async def log_request_middleware(request: Request, call_next):
    """Log incoming requests for monitoring and debugging."""
    middleware_func = create_log_request_middleware(excluded_paths=PUBLIC_ENDPOINTS)
    return await middleware_func(request, call_next)


@app.middleware("http")
async def user_context_middleware_wrapper(request: Request, call_next):
    """Extract and inject user context from authentication."""
    middleware_func = create_user_context_middleware(excluded_paths=PUBLIC_ENDPOINTS)
    return await middleware_func(request, call_next)


# Initialize agent with memory store
agent = create_and_compile_workflow(APIAssistant(), memory_store=MemorySaver())

# Register application routes
create_basic_routes(app)
create_agent_routes(
    app,
    agent=agent,
    validate_runtime_config=validate_runtime_config,
    modify_runtime_config=modify_runtime_config,
    agent_name="api-assistant",
)

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()

    uvicorn.run("server:app", host="0.0.0.0", port=8080)
