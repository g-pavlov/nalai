import logging
from datetime import UTC, datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command, interrupt

from ..config import BaseRuntimeConfiguration
from ..utils.pii_masking import mask_pii
from .constants import NODE_CALL_API, NODE_CALL_MODEL
from .schemas import AgentState

logger = logging.getLogger(__name__)

# Constants for human review messages
ABORT_MESSAGE = "Abort this tool call"


def process_human_review(
    state: AgentState, config: BaseRuntimeConfiguration
) -> Command[Literal["call_model", "call_api"]]:
    """Process human review of tool calls and return workflow commands.
    Handles human-in-the-loop review workflow by:
    - Extracting the latest AI message with tool calls
    - Presenting tool call for human review
    - Processing review actions (continue, abort, update, feedback)
    - Returning appropriate workflow commands
    Args:
        state: Current agent state with conversation history
        config: Runtime configuration with user context
    Returns:
        Command directing workflow to next step
    Raises:
        ValueError: If no AI message with tool calls is found
    """
    last_ai_message = None
    for message in reversed(state["messages"]):
        if isinstance(message, AIMessage):
            last_ai_message = message
            break
    else:
        raise ValueError("No AIMessage found in conversation history")
    if not last_ai_message.tool_calls:
        # No tool calls to review - return to model
        return Command(goto=NODE_CALL_MODEL, update={})

    current_tool_call = last_ai_message.tool_calls[-1]

    # Create human review interrupt for tool call validation
    human_review_interrupt = interrupt(
        {
            "question": "Is this correct?",
            "tool_call": current_tool_call,
        }
    )

    review_action = human_review_interrupt["action"]
    review_data = human_review_interrupt.get("data")

    # Process review actions
    if review_action == "continue":
        # Approved - execute the tool call
        log_human_review_action(review_action, config, current_tool_call)
        return Command(goto=NODE_CALL_API, update={})

    elif review_action == "abort":
        # Aborted - add abort messages and return to model
        confirmation_message = HumanMessage(content=review_action)
        tool_message = ToolMessage(
            content=ABORT_MESSAGE,
            name=current_tool_call["name"],
            tool_call_id=current_tool_call["id"],
        )
        log_human_review_action(review_action, config, current_tool_call)
        return Command(
            goto=NODE_CALL_MODEL,
            update={"messages": [tool_message, confirmation_message]},
        )

    elif review_action == "update":
        # Update tool call arguments and execute
        updated_ai_message = {
            "role": "ai",
            "content": last_ai_message.content,
            "tool_calls": [
                {
                    "id": current_tool_call["id"],
                    "name": current_tool_call["name"],
                    "args": review_data,  # Updated arguments from human
                }
            ],
            "id": last_ai_message.id,  # Preserve message ID to avoid duplication
        }
        return Command(goto=NODE_CALL_API, update={"messages": [updated_ai_message]})

    elif review_action == "feedback":
        # Provide feedback to LLM for reconsideration
        feedback_tool_message = ToolMessage(
            content=review_data,  # Natural language feedback
            name=current_tool_call["name"],
            tool_call_id=current_tool_call["id"],
        )
        return Command(
            goto=NODE_CALL_MODEL, update={"messages": [feedback_tool_message]}
        )

    else:
        # Unknown action - log warning and default to continue
        logger.warning(
            f"Unknown review action '{review_action}' received. Defaulting to 'continue'. "
            f"Tool call: {current_tool_call}"
        )
        log_human_review_action("continue", config, current_tool_call)
        return Command(goto=NODE_CALL_API, update={})


def log_human_review_action(review_action: str, config: BaseRuntimeConfiguration, tool_call: dict):
    """Log human review actions for audit and debugging.
    Records review decisions with user context and tool call details
    for compliance and troubleshooting purposes.
    
    Args:
        review_action: Action taken by human reviewer
        config: Runtime configuration with user context
        tool_call: Tool call being reviewed
    """
    # Handle case where config might be None or not have expected structure
    if config is None:
        config = {}

    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "unknown")
    org_unit_id = configurable.get("org_unit_id", "unknown")
    user_id = configurable.get("user_id", "unknown")
    user_email = configurable.get("user_email", "unknown")
    timestamp = datetime.now(UTC).isoformat()

    # Mask PII for logging - use user_id instead of email for privacy
    masked_user_id = mask_pii(user_id, "user_id")
    masked_org_unit_id = mask_pii(org_unit_id, "user_id") if org_unit_id != "unknown" else org_unit_id

    logger.info(
        f"Human review action: *{review_action}* is triggered by user: {masked_user_id} "
        f"for threadId: {thread_id} in org_unit_id: {masked_org_unit_id}. "
        f"Planned API to be executed: tool_call: {tool_call}. Timestamp: {timestamp}"
    )
