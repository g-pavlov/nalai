"""
API Assistant - AI Agent with API Integration

A Python package for building AI agents that can interact with APIs
and provide intelligent conversation capabilities.

Main components:
- WorkflowNodes: Workflow nodes for orchestrating API interactions
- Agent: Main agent interface for business operations
- create_agent: Factory function to create agent instances
"""

from .core import Agent, create_agent
from .core.workflow_nodes import WorkflowNodes

__version__ = "1.0.0"

__all__ = [
    "WorkflowNodes",
    "Agent",
    "create_agent",
]

# CLI entry point
from .cli import main as cli_main
