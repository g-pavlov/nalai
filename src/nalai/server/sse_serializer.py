"""
Event handling utilities for API Assistant server.

This module contains functions for processing, serializing, and formatting
events from the agent, including specialized handlers for different event types.
"""

import logging
from typing import Any

from ..core.types.streaming import (
    InterruptChunk,
    MessageChunk,
    StreamingChunk,
    ToolCallChunk,
    ToolCallUpdateChunk,
    ToolChunk,
    UpdateChunk,
)
from .schemas.sse import (
    ResponseInterruptEvent,
    ResponseOutputTextDeltaEvent,
    ResponseOutputToolCallsCompleteEvent,
    ResponseOutputToolCallsDeltaEvent,
    ResponseToolEvent,
    ResponseUpdateEvent,
)

logger = logging.getLogger("nalai")


def transform_chunk_to_sse(
    chunk: StreamingChunk, conversation_id: str, context: Any, run_id: str
) -> str | None:
    """Create SSE event from streaming chunk."""
    try:
        if isinstance(chunk, MessageChunk):
            # Handle message chunks
            if chunk.content:
                return ResponseOutputTextDeltaEvent.create(
                    conversation_id=conversation_id,
                    content=chunk.content,
                    usage=chunk.usage,
                    id=run_id,
                )

        elif isinstance(chunk, ToolCallChunk):
            # Use tool_calls_chunks for delta events
            if chunk.tool_calls_chunks:
                # Delta event - incremental tool call updates
                return ResponseOutputToolCallsDeltaEvent.create(
                    conversation_id=conversation_id,
                    tool_calls=chunk.tool_calls_chunks,
                    id=run_id,
                )

        elif isinstance(chunk, InterruptChunk):
            # Handle interrupt chunks
            if chunk.values:
                return ResponseInterruptEvent.create(
                    conversation_id=conversation_id,
                    interrupts=chunk.values,
                    id=run_id,
                )

        elif isinstance(chunk, ToolChunk):
            # Handle tool chunks (tool execution results)
            return ResponseToolEvent.create(
                conversation_id=conversation_id,
                tool_call_id=chunk.tool_call_id,
                tool_name=chunk.tool_name,
                status=chunk.status,
                content=chunk.content,
                args=chunk.args,
            )

        elif isinstance(chunk, UpdateChunk):
            # Handle update chunks (workflow progress events)
            return ResponseUpdateEvent.create(
                conversation_id=conversation_id,
                task=chunk.task,
                messages=[msg.model_dump() for msg in chunk.messages]
                if chunk.messages
                else None,
                id=run_id,
            )
        elif isinstance(chunk, ToolCallUpdateChunk):
            return ResponseOutputToolCallsCompleteEvent.create(
                conversation_id=conversation_id,
                tool_calls=chunk.tool_calls,
                id=run_id,
            )

        return None

    except Exception as e:
        logger.error(f"Error creating streaming event from chunk: {e}")
        return None
