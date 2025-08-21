"""
Core API Assistant functionality.

This module contains the main agent class, workflow definitions,
core data schemas, and agent interface.
"""

from langchain_core.messages import BaseMessage

from .agent import (
    AccessDeniedError,
    Agent,
    Conversation,
    ConversationInfo,
    ConversationNotFoundError,
    # Exceptions
    Error,
    InvocationError,
    # Internal types
    ResumeDecision,
    ValidationError,
)
from .checkpoints import get_checkpoints
from .langgraph_agent import LangGraphAgent
from .schemas import (
    AgentState,
    ConfigSchema,
    InputSchema,
    ModelConfig,
    OutputSchema,
    SelectApi,
    SelectedApis,
)
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
    # Agent interface
    "Agent",
    "LangGraphAgent",
    # Checkpoints interface
    "get_checkpoints",
    # LangChain message types
    "BaseMessage",
    # Internal types
    "ConversationInfo",
    "Conversation",
    "ResumeDecision",
    # Exceptions
    "Error",
    "AccessDeniedError",
    "ConversationNotFoundError",
    "ValidationError",
    "InvocationError",
]
