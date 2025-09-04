"""
API Assistant - AI Agent with API Integration

A Python package for building AI agents that can interact with APIs
and provide intelligent conversation capabilities.

Main components:
- WorkflowNodes: Workflow nodes for orchestrating API interactions
- Agent: Main agent interface for business operations
- create_agent: Factory function to create agent instances
"""

# CLI entry point
from .cli import main as cli_main

__all__ = [
    "cli_main",
]
