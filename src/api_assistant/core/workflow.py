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

from ..config import BaseRuntimeConfiguration
from ..services.api_docs_service import APIService
from .agent import APIAssistant
from .constants import (
    NODE_CALL_API,
    NODE_CALL_MODEL,
    NODE_CHECK_CACHE,
    NODE_HUMAN_REVIEW,
    NODE_LOAD_API_SPECS,
    NODE_LOAD_API_SUMMARIES,
    NODE_SELECT_RELEVANT_APIS,
)
from .interrupts import process_human_review
from .schemas import AgentState, InputSchema, OutputSchema
from .tool_node import create_chunk_accumulating_tool_node


def create_and_compile_workflow(
    agent: APIAssistant,
    memory_store: MemorySaver = None,
    available_tools: dict[str, Any] = None,
) -> CompiledStateGraph:
    """
    Creates and compiles the agent workflow using LangGraph's StateGraph.

    Args:
        agent: The APIAssistant instance
        memory_store: Optional memory store for checkpointing
        available_tools: Optional dictionary of tools to use

    Returns:
        Compiled workflow graph
    """
    if available_tools is None or NODE_CALL_API not in available_tools:
        available_tools = available_tools or {}
        # Use custom tool node with delayed execution for better streaming support
        available_tools[NODE_CALL_API] = create_chunk_accumulating_tool_node(
            agent.http_toolkit.get_tools()
        )

    workflow_graph = StateGraph(
        AgentState,
        config_schema=BaseRuntimeConfiguration,
        input=InputSchema,
        output=OutputSchema,
    )

    # Add workflow nodes
    workflow_graph.add_node(NODE_CHECK_CACHE, agent.check_cache_with_similarity)
    workflow_graph.set_entry_point(NODE_CHECK_CACHE)
    workflow_graph.add_node(NODE_LOAD_API_SUMMARIES, APIService.load_api_summaries)
    workflow_graph.add_node(NODE_SELECT_RELEVANT_APIS, agent.select_relevant_apis)
    workflow_graph.add_node(NODE_LOAD_API_SPECS, APIService.load_openapi_specifications)
    workflow_graph.add_node(NODE_CALL_MODEL, agent.generate_model_response)
    workflow_graph.add_node(NODE_CALL_API, available_tools[NODE_CALL_API])
    workflow_graph.add_node(NODE_HUMAN_REVIEW, process_human_review)

    # Add workflow edges
    workflow_graph.add_conditional_edges(
        NODE_CHECK_CACHE,
        agent.determine_cache_action,
        [NODE_LOAD_API_SUMMARIES, NODE_CALL_MODEL],
    )
    workflow_graph.add_edge(NODE_LOAD_API_SUMMARIES, NODE_SELECT_RELEVANT_APIS)
    workflow_graph.add_conditional_edges(
        NODE_SELECT_RELEVANT_APIS,
        agent.determine_next_step,
        [NODE_LOAD_API_SPECS, NODE_CALL_MODEL],
    )
    workflow_graph.add_edge(NODE_LOAD_API_SPECS, NODE_CALL_MODEL)
    workflow_graph.add_conditional_edges(
        NODE_CALL_MODEL,
        agent.determine_workflow_action,
        [NODE_HUMAN_REVIEW, END, NODE_CALL_API],
    )
    workflow_graph.add_edge(NODE_CALL_API, NODE_CALL_MODEL)

    return workflow_graph.compile(checkpointer=memory_store)
