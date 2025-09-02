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

from ..config import BaseRuntimeConfiguration, ExecutionContext, ToolCallMetadata
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
        request = HumanInterrupt(
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

        if action not in ["accept", "reject", "edit", "feedback"]:
            logger.warning(f"Unexpected interrupt response structure: {response}")
            raise ValueError(f"Unsupported interrupt response action: {action}")

        if action == "reject":
            tool_response = "User rejected the tool call"

        if action == "feedback":
            # Handle feedback decision - args should contain the user's feedback message
            tool_response = response.get("args")
            if tool_response is None:
                logger.warning("No feedback message provided, using default message")
                tool_response = "User provided feedback"

        original_args = tool_input
        if action == "edit":
            # args should contain the new tool arguments
            args = response.get("args")
            if isinstance(args, dict):
                tool_input = args
            else:
                logger.warning(f"Unexpected args format for edit: {args}")

        if action != "reject" and action != "feedback":
            run_manager = config.get("run_manager") if config else None
            tool_response = tool._run(
                **tool_input, config=config, run_manager=run_manager
            )

        tool_calls = {}
        tool_calls[response.get("tool_call_id")] = ToolCallMetadata(
            name=tool.name, args=tool_input, original_args=original_args
        )
        exec_ctx = ExecutionContext(tool_calls=tool_calls)

        composite_tool_response = {
            "tool_response": str(tool_response),
            "execution_context": exec_ctx.model_dump(),
            "_is_interrupt_response": True,
        }
        return composite_tool_response

    return call_tool_with_interrupt
