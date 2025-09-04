import logging
from collections.abc import Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.tools import tool as create_tool

from nalai.config import ToolCallMetadata

logger = logging.getLogger(__name__)


def add_execution_context(tool: Callable | BaseTool) -> BaseTool:
    """Wrap a tool to support human-in-the-loop review."""
    if not isinstance(tool, BaseTool):
        tool = create_tool(tool)

    @create_tool(tool.name, description=tool.description, args_schema=tool.args_schema)
    def call_tool_with_execution_context(config: RunnableConfig, **tool_input):
        run_manager = config.get("run_manager") if config else None
        tool_response = tool._run(**tool_input, config=config, run_manager=run_manager)

        tool_call_metadata = ToolCallMetadata(name=tool.name, args=tool_input)

        composite_tool_response = {
            "tool_response": str(tool_response),
            "execution_context": tool_call_metadata.model_dump(),
        }
        return composite_tool_response

    return call_tool_with_execution_context
