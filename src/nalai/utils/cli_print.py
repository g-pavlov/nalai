"""Utility & helper functions."""

import json
import logging

# Lazy imports to avoid circular dependencies
from ..utils.id_generator import generate_run_id

logger = logging.getLogger("nalai")

# Global state for accumulating tool call information
_tool_call_accumulator = {}
_tool_index_to_id = {}  # Map index to actual tool_id
_final_response_started = False  # Track if final response has started


def _is_api_selection_response(content: str) -> bool:
    """Check if the content is an API selection response that should be muted."""
    # API selection responses typically contain JSON with selected_apis
    return '"selected_apis"' in content and len(content.strip()) < 200


def print_streaming_chunk(chunk, printed_events: set, max_length=4000):
    """Print streaming chunk to terminal."""
    from ..core import (
        MessageChunk,
        ToolCallChunk,
        ToolChunk,
        UpdateChunk,
    )

    global _final_response_started

    if isinstance(chunk, UpdateChunk):
        # UpdateChunks are task milestone updates - render only status and task name
        # Suppress call_model task completion if final response has started
        if not (chunk.task == "call_model" and _final_response_started):
            print(f"[Task: {chunk.task}] Complete")

    elif isinstance(chunk, MessageChunk):
        # MessageChunks are pieces of text that need to be rendered progressively
        if chunk.content:
            # Check if this is an API selection response (mute it)
            if _is_api_selection_response(chunk.content):
                return  # Mute API selection responses

            if not _final_response_started:
                print()  # Add newline before final response
                print()  # Add extra newline for spacing
                _final_response_started = True
            print(chunk.content, end="")

    elif isinstance(chunk, ToolCallChunk):
        # ToolCallChunks are chunks streamed from the LLM for [Tool call: xxx] line
        if chunk.tool_calls_chunks:
            for tool_call_chunk in chunk.tool_calls_chunks:
                # Extract meaningful content from tool call chunk
                tool_name = tool_call_chunk.get("name")
                tool_args = tool_call_chunk.get("args")
                tool_id = tool_call_chunk.get("id")
                tool_index = tool_call_chunk.get("index", 0)

                # Skip if no meaningful content
                if not any([tool_name, tool_args, tool_id]):
                    continue

                # Map index to tool_id for subsequent chunks
                if tool_id and tool_index is not None:
                    _tool_index_to_id[tool_index] = tool_id
                elif (
                    not tool_id
                    and tool_index is not None
                    and tool_index in _tool_index_to_id
                ):
                    tool_id = _tool_index_to_id[tool_index]

                # Accumulate tool call information
                if tool_id and tool_id not in _tool_call_accumulator:
                    _tool_call_accumulator[tool_id] = {
                        "name": None,
                        "args": "",
                        "displayed": False,
                    }

                if tool_id in _tool_call_accumulator:
                    acc = _tool_call_accumulator[tool_id]

                    # Update accumulated information
                    if tool_name and tool_name != "None":
                        acc["name"] = tool_name
                    if tool_args and tool_args != "None":
                        if isinstance(tool_args, str):
                            acc["args"] += tool_args
                        else:
                            acc["args"] = str(tool_args)

                    # Display progressive updates
                    if acc["name"]:
                        if not acc["displayed"]:
                            # First time showing this tool call
                            print(
                                f'[Tool call: {acc["name"]}] {{ "args": {acc["args"]}',
                                end="",
                                flush=True,
                            )
                            acc["displayed"] = True
                        else:
                            # For subsequent updates, just print the new args directly
                            if tool_args:
                                print(tool_args, end="", flush=True)

    elif isinstance(chunk, ToolChunk):
        # ToolChunks provide tool execution status, invocation details and response for [Tool: xxx] line
        if chunk.status == "success":
            # Close the JSON for the tool call if it was displayed
            tool_call_id = chunk.tool_call_id
            tool_name = chunk.tool_name

            # Try to find the accumulator entry by tool_call_id or tool_name
            accumulator_key = None
            if tool_call_id in _tool_call_accumulator:
                accumulator_key = tool_call_id
            else:
                # Fallback: find by tool name
                for key, acc in _tool_call_accumulator.items():
                    if acc["name"] == tool_name and acc["displayed"]:
                        accumulator_key = key
                        break

            if accumulator_key and _tool_call_accumulator[accumulator_key]["displayed"]:
                print("}}")
            print(f"[Tool: {chunk.tool_name}] Success")
        elif chunk.status == "error":
            # Close the JSON for the tool call if it was displayed
            tool_call_id = chunk.tool_call_id
            tool_name = chunk.tool_name

            # Try to find the accumulator entry by tool_call_id or tool_name
            accumulator_key = None
            if tool_call_id in _tool_call_accumulator:
                accumulator_key = tool_call_id
            else:
                # Fallback: find by tool name
                for key, acc in _tool_call_accumulator.items():
                    if acc["name"] == tool_name and acc["displayed"]:
                        accumulator_key = key
                        break

            if accumulator_key and _tool_call_accumulator[accumulator_key]["displayed"]:
                print("}}")
            print(f"[Tool: {chunk.tool_name}] Failed: {chunk.content}")


async def handle_interruption(
    agent,
    interrupt_chunk,
    config: dict,
    conversation_id: str,
):
    """Handle human-in-the-loop interruption."""
    from ..core import ToolCallDecision

    # Extract tool call information from interrupt chunk
    interrupt_values = interrupt_chunk.values
    if not interrupt_values:
        print("No interrupt values found")
        return

    # Get the first interrupt value (action request)
    action_request = interrupt_values[0].get("action_request", {})

    user_input = input(
        "\n--------------- Confirmation Needed ---------------"
        "\nAI will perform the following tool invocation:"
        f"\nTool: {action_request.get('action', 'unknown')}"
        f"\nArgs: {json.dumps(action_request.get('args', {}), indent=2)}\n"
        "\nType 'y' or 'yes' to continue, 'no' or 'n' to abort; otherwise, explain the change you request."
        "\nConfirm: "
    )

    # Get the actual tool_call_id from the action request or find it in the accumulator
    tool_call_id = action_request.get("tool_call_id")
    if not tool_call_id or tool_call_id == "unknown":
        # Try to find the tool_call_id from the accumulator
        for acc_id, acc_data in _tool_call_accumulator.items():
            if acc_data.get("displayed", False):
                tool_call_id = acc_id
                break

    # If still no valid tool_call_id, generate one
    if not tool_call_id or tool_call_id == "unknown":
        tool_call_id = f"call_{generate_run_id()[:8]}"

    # Create tool call decision based on user input
    if user_input.lower() in ["y", "yes"]:
        decision = ToolCallDecision(
            type="tool_decision", tool_call_id=tool_call_id, decision="accept"
        )
    elif user_input.lower() in ["n", "no"]:
        # ask for rejection reason
        reject_reason = input("Please provide a reason for rejection: ").strip()
        decision = ToolCallDecision(
            type="tool_decision",
            tool_call_id=tool_call_id,
            decision="reject",
            message=reject_reason if reject_reason else None,
        )
    else:
        # needs changes - treat as feedback
        decision = ToolCallDecision(
            type="tool_decision",
            tool_call_id=tool_call_id,
            decision="feedback",
            message=user_input,
        )

    # Resume the conversation with the decision
    try:
        stream_generator, _ = await agent.resume_interrupted_streaming(
            resume_decision=decision, conversation_id=conversation_id, config=config
        )

        printed_events = set()
        async for chunk in stream_generator:
            # Handle events (ResponseCreatedEvent, ResponseCompletedEvent, etc.)
            if hasattr(chunk, "event"):
                if chunk.event == "response.created":
                    print("========== AI Response Started ==========")
                elif chunk.event == "response.completed":
                    print("\n")
                    print(
                        f"\n========== Response Completed (Usage: {chunk.usage}) =========="
                    )
                elif chunk.event == "response.error":
                    print(f"\n========== Response Error: {chunk.error} ==========")
            # Handle streaming chunks
            elif hasattr(chunk, "type"):
                if chunk.type == "interrupt":
                    await handle_interruption(agent, chunk, config, conversation_id)
                else:
                    print_streaming_chunk(chunk, printed_events)
    except Exception as e:
        print(f"Error resuming conversation: {e}")


async def stream_events_with_interruptions(
    agent,
    config: dict,
    user_input: str,
):
    """Stream events from agent with HITL support."""
    from ..core import HumanInputMessage

    # Create input message from user input
    messages = [
        HumanInputMessage(
            type="message", role="user", content=[{"type": "text", "text": user_input}]
        )
    ]

    # Start streaming conversation
    stream_generator, conversation_info = await agent.chat_streaming(
        messages=messages,
        conversation_id=None,  # Start new conversation
        config=config,
    )

    printed_events = set()
    interrupt_chunks = []

    # Clear tool call accumulator for new conversation
    global _tool_call_accumulator, _tool_index_to_id, _final_response_started
    _tool_call_accumulator.clear()
    _tool_index_to_id.clear()
    _final_response_started = False

    async for chunk in stream_generator:
        # Handle events (ResponseCreatedEvent, ResponseCompletedEvent, etc.)
        if hasattr(chunk, "event"):
            if chunk.event == "response.created":
                print("========== AI Response Started ==========")
            elif chunk.event == "response.completed":
                _final_response_started = False
                print()
                print(
                    f"\n========== Response Completed (Usage: {chunk.usage}) =========="
                )
            elif chunk.event == "response.error":
                _final_response_started = False
                print(f"\n========== Response Error: {chunk.error} ==========")
        # Handle streaming chunks
        elif hasattr(chunk, "type"):
            if chunk.type == "interrupt":
                interrupt_chunks.append(chunk)
                await handle_interruption(
                    agent, chunk, config, conversation_info.conversation_id
                )
            else:
                print_streaming_chunk(chunk, printed_events)
