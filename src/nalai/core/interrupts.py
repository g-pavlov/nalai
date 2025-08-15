import logging
from collections.abc import Callable
from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.tools import tool as create_tool
from langgraph.prebuilt.interrupt import HumanInterrupt, HumanInterruptConfig
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
    # user_email = configurable.get("user_email", "unknown")  # Unused
    timestamp = datetime.now(UTC).isoformat()

    # Mask PII for logging - use user_id instead of email for privacy
    masked_user_id = mask_pii(user_id, "user_id")
    masked_org_unit_id = (
        mask_pii(org_unit_id, "user_id") if org_unit_id != "unknown" else org_unit_id
    )

    logger.info(
        f"Human review action: *{review_action}* is triggered by user: {masked_user_id} "
        f"for threadId: {thread_id} in org_unit_id: {masked_org_unit_id}. "
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

    if interrupt_config is None:
        interrupt_config = {
            "allow_accept": True,
            "allow_edit": True,
            "allow_respond": True,
        }

    @create_tool(tool.name, description=tool.description, args_schema=tool.args_schema)
    def call_tool_with_interrupt(config: RunnableConfig, **tool_input):
        request: HumanInterrupt = {
            "action_request": {
                "action": tool.name,
                "args": tool_input,
            },
            "config": interrupt_config,
            "description": "Please review the tool call",
        }
        logger.info(f"Interrupt request: {request}")
        response = interrupt([request])[0]
        # approve the tool call
        logger.info(f"Interrupt response: {response}")
        if response["type"] == "accept":
            # Extract run_manager from config if available
            run_manager = config.get("run_manager") if config else None
            # Use the tool's _run method directly to avoid LangGraph context issues
            tool_response = tool._run(
                **tool_input, config=config, run_manager=run_manager
            )
        # update tool call args
        elif response["type"] == "edit":
            tool_input = response["args"]["args"]
            run_manager = config.get("run_manager") if config else None
            tool_response = tool._run(
                **tool_input, config=config, run_manager=run_manager
            )
        # respond to the LLM with user feedback
        elif response["type"] == "response":
            user_feedback = response["args"]
            tool_response = user_feedback
        else:
            raise ValueError(f"Unsupported interrupt response type: {response['type']}")

        return tool_response

    return call_tool_with_interrupt
