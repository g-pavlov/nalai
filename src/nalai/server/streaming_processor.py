"""
Streaming event processor for handling tool call chunks.

This module provides a streaming event processor that can handle
incomplete tool call chunks and accumulate them until complete.
"""

import logging
from typing import Any

from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)


class StreamingEventProcessor:
    """Processes streaming events and accumulates tool call chunks."""

    def __init__(self, tool_node=None):
        """Initialize the streaming event processor."""
        self.tool_node = tool_node
        self.tool_call_buffers: dict[str, str] = {}
        self.completed_tool_calls: dict[str, Any] = {}

    def process_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Process a single streaming event and return events to emit."""
        event_type = event.get("event")

        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk", {})

            # Process tool call chunks
            if "tool_call_chunks" in chunk:
                for tool_call_chunk in chunk.get("tool_call_chunks", []):
                    tool_call_id = tool_call_chunk.get("id")
                    args_chunk = tool_call_chunk.get("args", "")

                    if tool_call_id and self.tool_node:
                        self.tool_node.accumulate_chunk(
                            {"id": tool_call_id, "args": args_chunk}
                        )

            # Process invalid tool calls (incomplete JSON)
            if "invalid_tool_calls" in chunk:
                for invalid_call in chunk.get("invalid_tool_calls", []):
                    tool_call_id = invalid_call.get("id")
                    args_chunk = invalid_call.get("args", "")

                    if tool_call_id and self.tool_node:
                        self.tool_node.accumulate_chunk(
                            {"id": tool_call_id, "args": args_chunk}
                        )

            # Return the event as-is for now
            return event

        elif event_type == "on_tool_end":
            # Tool execution completed
            tool_call_id = event.get("data", {}).get("tool_call_id")

            if self.tool_node and tool_call_id:
                # Check if we have accumulated args for this tool call
                tool_node_buffers = self.tool_node.get_buffered_tool_calls()
                if tool_call_id in tool_node_buffers:
                    # Tool was executed with accumulated args
                    return event

            return event

        else:
            # Pass through other events
            return event

    def process_chat_model_stream_with_tool_calls(
        self, events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process a stream of chat model events with tool calls."""
        processed_events = []

        for event in events:
            if event.get("event") == "on_tool_start":
                # Start accumulating tool call
                tool_call_id = event.get("data", {}).get("name")
                if tool_call_id:
                    self.tool_call_buffers[tool_call_id] = ""

            elif event.get("event") == "on_tool_end":
                # Tool call completed
                tool_call_id = event.get("data", {}).get("name")
                if tool_call_id and tool_call_id in self.tool_call_buffers:
                    completed_args = self.tool_call_buffers.pop(tool_call_id)
                    self.completed_tool_calls[tool_call_id] = completed_args

            processed_events.append(event)

        return processed_events

    def process_complete_tool_call(
        self, tool_call_id: str, args: dict[str, Any]
    ) -> ToolMessage:
        """Process a complete tool call."""
        self.completed_tool_calls[tool_call_id] = args
        return ToolMessage(
            content=f"Tool call {tool_call_id} completed", tool_call_id=tool_call_id
        )

    def process_other_event_types(self, event: dict[str, Any]) -> dict[str, Any]:
        """Process other types of events."""
        return event

    def clear_buffers(self):
        """Clear all accumulated buffers."""
        self.tool_call_buffers.clear()
        self.completed_tool_calls.clear()

    def get_buffered_tool_calls(self) -> dict[str, Any]:
        """Get all buffered tool calls."""
        return self.completed_tool_calls.copy()


def create_streaming_event_processor() -> StreamingEventProcessor:
    """Create a new streaming event processor."""
    return StreamingEventProcessor()
