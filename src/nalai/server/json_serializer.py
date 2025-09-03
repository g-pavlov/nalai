"""
Message serialization utilities for API Assistant server.

This module transforms core Message objects to JSON response format
that complies with the schema defined in messages.py.
"""

import logging
from datetime import UTC, datetime

from ..core.types.agent import ConversationInfo
from ..core.types.messages import (
    BaseOutputMessage,
    InputMessage,
    Interrupt,
    MessageResponse,
    OutputMessage,
)
from ..utils.id_generator import generate_run_id

logger = logging.getLogger("nalai")


def _extract_usage_from_core_messages(
    messages: list[InputMessage | OutputMessage],
) -> dict[str, int]:
    """
    Extract and aggregate usage information from core message models.

    This function calculates total token usage across all messages
    in the current response.
    """
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for message in messages:
        if (
            hasattr(message, "usage")
            and message.usage
            and isinstance(message.usage, dict)
        ):
            total_prompt_tokens += message.usage.get("prompt_tokens", 0)
            total_completion_tokens += message.usage.get("completion_tokens", 0)
            total_tokens += message.usage.get("total_tokens", 0)

    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
    }


def _extract_interrupts(conversation_info: ConversationInfo) -> list[Interrupt]:
    interrupts_list = None

    if conversation_info.interrupt_info:
        interrupt_info = conversation_info.interrupt_info
        # Handle new multiple interrupts structure
        if "interrupts" in interrupt_info:
            # New structure with multiple interrupts
            interrupt_infos = []
            for single_interrupt in interrupt_info["interrupts"]:
                interrupt_infos.append(
                    Interrupt(
                        type=single_interrupt.get("type", "tool_call"),
                        tool_call_id=single_interrupt.get("tool_call_id", "unknown"),
                        action=single_interrupt.get("action", "unknown"),
                        args=single_interrupt.get("args", {}),
                    )
                )
            interrupts_list = interrupt_infos
        else:
            # Legacy single interrupt structure - convert to new format
            interrupt_infos = [
                Interrupt(
                    type=interrupt_info.get("type", "tool_call"),
                    tool_call_id=interrupt_info.get("tool_call_id", "unknown"),
                    action=interrupt_info.get("action", "unknown"),
                    args=interrupt_info.get("args", {}),
                )
            ]
            interrupts_list = interrupt_infos
    return interrupts_list


def serialize_message_response(
    messages: list[BaseOutputMessage],
    conversation_info: ConversationInfo,
    previous_response_id: str | None,
    status: str,
) -> MessageResponse:
    """Serialize message response to output format for JSON responses."""

    run_id = generate_run_id()

    interrupts = _extract_interrupts(conversation_info)
    if interrupts:
        status = "interrupted"

    response_data = {
        "id": run_id,
        "conversation_id": conversation_info.conversation_id,
        "previous_response_id": previous_response_id,
        "output": messages,
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "interrupts": interrupts,
        "metadata": None,
        "usage": _extract_usage_from_core_messages(messages),
    }

    return MessageResponse(**response_data)
