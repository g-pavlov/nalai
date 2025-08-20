"""
LangGraph workflow construction and management.

This module handles the creation and compilation of the API Assistant
workflow using LangGraph's StateGraph.
"""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from ..config import BaseRuntimeConfiguration
from ..services.api_docs_service import APIService
from .constants import (
    NODE_CALL_API,
    NODE_CALL_MODEL,
    NODE_CHECK_CACHE,
    NODE_LOAD_API_SPECS,
    NODE_LOAD_API_SUMMARIES,
    NODE_SELECT_RELEVANT_APIS,
)
from .interrupts import add_human_in_the_loop
from .schemas import AgentState, InputSchema, OutputSchema
from .workflow_nodes import WorkflowNodes


def create_and_compile_workflow(
    workflow_nodes: WorkflowNodes,
    memory_store: MemorySaver = None,
    available_tools: dict[str, Any] = None,
) -> CompiledStateGraph:
    """
    Creates and compiles the agent workflow using LangGraph's StateGraph.

    Args:
        workflow_nodes: The WorkflowNodes instance
        memory_store: Optional memory store for checkpointing
        available_tools: Optional dictionary of tools to use

    Returns:
        Compiled workflow graph
    """
    if available_tools is None or NODE_CALL_API not in available_tools:
        available_tools = available_tools or {}
        tools = [
            add_human_in_the_loop(tool)
            if not workflow_nodes.http_toolkit.is_safe_tool(tool.name)
            else tool
            for tool in workflow_nodes.http_toolkit.get_tools()
        ]
        available_tools[NODE_CALL_API] = ToolNode(tools)

    workflow_graph = StateGraph(
        AgentState,
        config_schema=BaseRuntimeConfiguration,
        input=InputSchema,
        output=OutputSchema,
    )

    # Add workflow nodes
    workflow_graph.add_node(
        NODE_CHECK_CACHE, workflow_nodes.check_cache_with_similarity
    )
    workflow_graph.set_entry_point(NODE_CHECK_CACHE)
    workflow_graph.add_node(NODE_LOAD_API_SUMMARIES, APIService.load_api_summaries)
    workflow_graph.add_node(
        NODE_SELECT_RELEVANT_APIS, workflow_nodes.select_relevant_apis
    )
    workflow_graph.add_node(NODE_LOAD_API_SPECS, APIService.load_openapi_specifications)
    workflow_graph.add_node(NODE_CALL_MODEL, workflow_nodes.generate_model_response)
    workflow_graph.add_node(NODE_CALL_API, available_tools[NODE_CALL_API])

    # Add workflow edges
    workflow_graph.add_conditional_edges(
        NODE_CHECK_CACHE,
        workflow_nodes.determine_cache_action,
        [NODE_LOAD_API_SUMMARIES, NODE_CALL_MODEL],
    )
    workflow_graph.add_edge(NODE_LOAD_API_SUMMARIES, NODE_SELECT_RELEVANT_APIS)
    workflow_graph.add_conditional_edges(
        NODE_SELECT_RELEVANT_APIS,
        workflow_nodes.determine_next_step,
        [NODE_LOAD_API_SPECS, NODE_CALL_MODEL],
    )
    workflow_graph.add_edge(NODE_LOAD_API_SPECS, NODE_CALL_MODEL)
    workflow_graph.add_edge(NODE_CALL_API, NODE_CALL_MODEL)
    workflow_graph.add_conditional_edges(
        NODE_CALL_MODEL,
        workflow_nodes.should_execute_tools,
        [NODE_CALL_API, END],
    )

    return workflow_graph.compile(checkpointer=memory_store)
