"""
Tool node for handling tool calls in the workflow.

This module provides a standard tool node using LangGraph's ToolNode
and a custom chunk accumulating tool node for handling streaming tool calls.
"""

import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


class ChunkAccumulatingToolNode:
    """Custom tool node that accumulates tool call chunks."""

    def __init__(self, tools: list[BaseTool]):
        """Initialize the chunk accumulating tool node."""
        self.tools = {tool.name: tool for tool in tools}
        self.tool_call_buffers: dict[str, str] = {}
        self.completed_tool_calls: dict[str, Any] = {}

    def accumulate_chunk(self, chunk: dict[str, Any]):
        """Accumulate a tool call chunk."""
        tool_call_id = chunk.get("id")
        args_chunk = chunk.get("args", "")

        if tool_call_id:
            if tool_call_id not in self.tool_call_buffers:
                self.tool_call_buffers[tool_call_id] = ""
            self.tool_call_buffers[tool_call_id] += args_chunk

    def _execute_tool(
        self, tool_name: str, args: dict[str, Any], tool_call_id: str
    ) -> ToolMessage:
        """Execute a tool with the given arguments."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")

        tool = self.tools[tool_name]
        result = tool.invoke(args)

        return ToolMessage(
            content=str(result), name=tool_name, tool_call_id=tool_call_id
        )

    def clear_buffers(self):
        """Clear all accumulated buffers."""
        self.tool_call_buffers.clear()
        self.completed_tool_calls.clear()

    def get_buffered_tool_calls(self) -> dict[str, Any]:
        """Get all buffered tool calls."""
        return self.completed_tool_calls.copy()


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
