"""
Core API Assistant functionality.

This module contains the main agent class, workflow definitions,
core data schemas, and agent interface.
"""

from langchain_core.messages import BaseMessage

from .checkpoints import get_checkpoints
from .langgraph_agent import LangGraphAgent
from .states import (
    AgentState,
    InputSchema,
    OutputSchema,
)
from .types.agent import (
    AccessDeniedError,
    Agent,
    ClientError,
    ConversationInfo,
    ConversationNotFoundError,
    # Exceptions
    Error,
    InvocationError,
    # Internal types
    SelectApi,
    SelectedApis,
    StreamingChunk,
    ValidationError,
)
from .types.messages import (
    InputMessage,
    OutputMessage,
    ToolCall,
    ToolCallDecision,
)
from .types.runtime_config import ConfigSchema, ModelConfig
from .workflow import create_and_compile_workflow
from .workflow_nodes import WorkflowNodes


# Factory function for easy agent creation
def create_agent() -> Agent:
    """Create and return an agent.

    Returns:
        Agent: Agent for business operations
    """
    # Create the compiled workflow with singleton memory store for checkpointing
    from ..services.checkpointing_service import get_checkpointing_service

    workflow_nodes = WorkflowNodes()
    checkpointing_service = get_checkpointing_service()
    memory_store = checkpointing_service.get_checkpointer()
    workflow = create_and_compile_workflow(workflow_nodes, memory_store=memory_store)

    # Create and return the agent API
    return LangGraphAgent(
        workflow_graph=workflow,
    )


__all__ = [
    "WorkflowNodes",
    "create_and_compile_workflow",
    "create_agent",  # Factory function
    "AgentState",
    "ConfigSchema",
    "InputSchema",
    "ModelConfig",
    "OutputSchema",
    "SelectApi",
    "SelectedApis",
    # Core data models
    "InputMessage",
    "OutputMessage",
    "StreamingChunk",
    "ToolCall",
    "ToolCallDecision",
    # Agent interface
    "Agent",
    "LangGraphAgent",
    # Checkpoints interface
    "get_checkpoints",
    # LangChain message types
    "BaseMessage",
    # Internal types
    "ConversationInfo",
    # Exceptions
    "Error",
    "AccessDeniedError",
    "ClientError",
    "ConversationNotFoundError",
    "ValidationError",
    "InvocationError",
]
