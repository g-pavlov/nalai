"""
nalAI - Conversational AI agent for API integration and testing.

A comprehensive toolkit for building AI-powered API assistants that can:
- Analyze API specifications and select relevant endpoints
- Execute HTTP requests with proper error handling
- Maintain conversation context with intelligent history management
- Support human-in-the-loop review workflows
- Provide structured responses with examples and guidelines

Key components:
- APIAgent: Main agent class for orchestrating API interactions
- AgentState: Typed state management for conversation flow
- ConfigSchema: Configuration models for model and runtime settings
- HTTP tools: Complete HTTP client toolkit with safety features
- Rate limiting: Cross-process rate limiting for API calls
- Server: FastAPI server with streaming and authentication support
"""

from .core.agent import APIAgent
from .core.schemas import (
    AgentState,
    ConfigSchema,
    InputSchema,
    ModelConfig,
    OutputSchema,
    SelectApi,
    SelectedApis,
)

__all__ = [
    "APIAgent",
    "AgentState",
    "ConfigSchema",
    "InputSchema",
    "ModelConfig",
    "OutputSchema",
    "SelectApi",
    "SelectedApis",
]

# CLI entry point
from .cli import main as cli_main
