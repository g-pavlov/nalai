"""
Tool node for handling tool calls in the workflow.

This module provides a standard tool node using LangGraph's ToolNode.
"""

import logging

from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


def create_chunk_accumulating_tool_node(tools: list[BaseTool]) -> ToolNode:
    """
    Create a standard tool node using LangGraph's ToolNode.

    Args:
        tools: List of BaseTool instances

    Returns:
        ToolNode instance
    """
    # Create and return the ToolNode instance
    return ToolNode(tools)
