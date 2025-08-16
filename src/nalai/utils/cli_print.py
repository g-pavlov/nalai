"""Utility & helper functions."""

import json
import logging
from typing import Any, Literal

# WiP
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

# AddableValuesDict is not available in current LangGraph version
# Using dict[str, Any] as a replacement
from langgraph.types import Command, Interrupt

from ..server.schemas import ResumeDecisionRequest

logger = logging.getLogger("nalai")


def print_streaming_event(
    event: dict[str, Any] | Any, printed_events: set, max_length=4000
):
    if type(event) is tuple:
        message = event[0]
        if len(message.content) == 0 and len(message.tool_call_chunks) == 0:
            print("========== AI Message ==========")
            return
        if isinstance(message, AIMessageChunk) and len(message.content) > 0:
            text_content = ""
            message_chunk = message.content[-1]
            if message_chunk.get("type") == "text":
                text_content = message.text()
            if message_chunk.get("type") == "tool_use":
                text_content = message_chunk.get("name")
                if text_content is None:
                    text_content = message_chunk.get("input")
            # if len(msg_repr) > max_length:
            #     msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(text_content, end="")
        else:
            pass
    elif isinstance(event, dict):  # Previously AddableValuesDict
        message = event.get("messages")
        if message:
            if isinstance(message, list):
                message = message[-1]
            if message.id not in printed_events:
                message_representation = message.pretty_repr(html=True)
                if len(message_representation) > max_length:
                    message_representation = (
                        message_representation[:max_length] + " ... (truncated)"
                    )
                print(message_representation)
                printed_events.add(message.id)
    else:
        raise ValueError(f"Unexpected event type: {type(event)}")


def print_event(event: dict[str, Any] | Any, printed_events: set, max_length=4000):
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in printed_events:
            message_representation = message.pretty_repr(html=True)
            if len(message_representation) > max_length:
                message_representation = (
                    message_representation[:max_length] + " ... (truncated)"
                )
            print(message_representation)
        printed_events.add(message.id)


async def handle_interruption(
    graph: CompiledStateGraph,
    interrupts: Interrupt,
    config: RunnableConfig,
    printed_events: set,
):
    # We have an interrupt! The agent is trying to use a tool, and the user can approve or deny it
    # The interrupt value is a list containing the interrupt request
    interrupt_request = (
        interrupts.value[0] if isinstance(interrupts.value, list) else interrupts.value
    )
    action_request = interrupt_request.get("action_request", {})

    user_input = input(
        "\n--------------- Confirmation Needed ---------------"
        "\nAI will perform the following tool invocation:"
        f"\nTool: {action_request.get('action', 'unknown')}"
        f"\nArgs: {json.dumps(action_request.get('args', {}), indent=2)}\n"
        "\nType 'y' or 'yes' to continue, 'no' or 'n' to abort; otherwise, explain the change you request."
        "\nConfirm: "
    )
    # the resume_input implies a certain structure handling by the state handlers (i.e. an oppinionated contract). see if this can be relaxed.
    resume_input = {"action": None, "data": None}
    # improve this with a more semantic analysis of user intent allowing multiple input optons for 'yes' or 'no'
    if user_input.lower() in ["y", "yes"]:
        # continue
        interrupt_response = ResumeDecisionRequest(input={"decision": "accept"})
        resume_input = [interrupt_response.to_internal()]
    elif user_input.lower() in ["n", "no"]:
        # ask for rejection reason
        reject_reason = input("Please provide a reason for rejection: ").strip()
        if not reject_reason:
            # Simple reject without reason
            interrupt_response = ResumeDecisionRequest(input={"decision": "reject"})
        else:
            # Reject with reason
            interrupt_response = ResumeDecisionRequest(
                input={"decision": "reject", "message": reject_reason}
            )
        resume_input = [interrupt_response.to_internal()]
    else:
        # needs changes - treat as feedback
        interrupt_response = ResumeDecisionRequest(
            input={"decision": "feedback", "message": user_input.lower()}
        )
        resume_input = [interrupt_response.to_internal()]
    # resume the workflow with a command built from the user input
    if interrupts.resumable:
        async for event in graph.astream(
            Command(resume=resume_input), config, stream_mode="values"
        ):
            print_event(event, printed_events)


async def stream_events_with_interruptions(
    graph: CompiledStateGraph,
    config: RunnableConfig,
    user_input: dict,
    stream_mode: Literal["values", "messages", "updates"] = "values",
):
    printed_events = set()
    async for event in graph.astream(
        {"messages": ("user", user_input)}, config, stream_mode=stream_mode
    ):
        print_event(event, printed_events)
    snapshot = graph.get_state(config)
    while snapshot.next:
        if len(snapshot) and len(snapshot[-1]) > 0:
            interrupts = snapshot[-1][0]
            await handle_interruption(graph, interrupts, config, printed_events)
            snapshot = graph.get_state(config)
