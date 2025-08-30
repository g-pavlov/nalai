import logging
from collections.abc import Callable
from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.tools import tool as create_tool
from langgraph.prebuilt.interrupt import (
    ActionRequest,
    HumanInterrupt,
    HumanInterruptConfig,
)
from langgraph.types import interrupt

from ..config import BaseRuntimeConfiguration
from ..utils.pii_masking import mask_pii

logger = logging.getLogger(__name__)


def log_human_review_action(
    review_action: str, config: BaseRuntimeConfiguration, tool_call: dict
):
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

    # Extract base UUID from user-scoped thread_id for logging
    base_thread_id = thread_id
    if thread_id != "unknown" and thread_id.startswith("user:"):
        try:
            base_thread_id = thread_id.split(":", 2)[2]
        except (IndexError, AttributeError):
            logger.warning(f"Invalid user-scoped thread_id format: {thread_id}")
            base_thread_id = thread_id
    # user_email = configurable.get("user_email", "unknown")  # Unused
    timestamp = datetime.now(UTC).isoformat()

    # Mask PII for logging - use user_id instead of email for privacy
    masked_user_id = mask_pii(user_id, "user_id")
    masked_org_unit_id = (
        mask_pii(org_unit_id, "user_id") if org_unit_id != "unknown" else org_unit_id
    )

    logger.info(
        f"Human review action: *{review_action}* is triggered by user: {masked_user_id} "
        f"for threadId: {base_thread_id} in org_unit_id: {masked_org_unit_id}. "
        f"Planned API to be executed: tool_call: {tool_call}. Timestamp: {timestamp}"
    )


def add_human_in_the_loop(
    tool: Callable | BaseTool,
    *,
    interrupt_config: HumanInterruptConfig = None,
) -> BaseTool:
    """Wrap a tool to support human-in-the-loop review."""
    if not isinstance(tool, BaseTool):
        tool = create_tool(tool)

    if not interrupt_config:
        interrupt_config = {
            "allow_accept": True,
            "allow_edit": True,
            "allow_respond": True,
        }

    @create_tool(tool.name, description=tool.description, args_schema=tool.args_schema)
    def call_tool_with_interrupt(config: RunnableConfig, **tool_input):
        request = request = HumanInterrupt(
            action_request=ActionRequest(
                action=tool.name,  # The action being requested
                args=tool_input,  # Arguments for the action
            ),
            config=HumanInterruptConfig(**interrupt_config),
            description="Please review the command before execution",
        )

        logger.info(f"Interrupt request: {request}")
        response = interrupt([request])[0]
        logger.info(f"Interrupt response: {response}")
        action = response.get("action")
        if action == "accept":
            run_manager = config.get("run_manager") if config else None
            # Use the tool's _run method directly to avoid LangGraph context issues
            tool_response = tool._run(
                **tool_input, config=config, run_manager=run_manager
            )

            # Store the args in the response for later extraction
            # We'll use a special format that can be parsed by the transformer
            response_with_args = {
                "content": str(tool_response),
                "tool_name": tool.name,
                "execution_args": tool_input,
                "_is_interrupt_response": True,
            }

            # Return the dictionary directly, not as a string
            return response_with_args
        elif action == "reject":
            tool_response = "User rejected the tool call"
        elif action == "edit":
            # args should contain the new tool arguments
            args = response.get("args")
            if isinstance(args, dict):
                tool_input = args
            else:
                logger.warning(f"Unexpected args format for edit: {args}")
                tool_input = tool_input
            run_manager = config.get("run_manager") if config else None
            tool_response = tool._run(
                **tool_input, config=config, run_manager=run_manager
            )

            # Store the args in the response for later extraction
            # We'll use a special format that can be parsed by the transformer
            response_with_args = {
                "content": str(tool_response),
                "tool_name": tool.name,
                "execution_args": tool_input,
                "_is_interrupt_response": True,
            }

            # Return the dictionary directly, not as a string
            return response_with_args
        elif action == "feedback":
            # Handle feedback decision - args should contain the user's feedback message
            user_feedback = response.get("args")
            if user_feedback is None:
                logger.warning("No feedback message provided, using default message")
                user_feedback = "User provided feedback"
            tool_response = user_feedback
        else:
            # Log the actual response structure for debugging
            logger.error(f"Unexpected interrupt response structure: {response}")
            raise ValueError(f"Unsupported interrupt response action: {action}")

        return tool_response

    return call_tool_with_interrupt
