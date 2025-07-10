"""
Unit tests for workflow functionality.

Tests cover workflow creation, compilation, node addition, and edge management.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from api_assistant.config import BaseRuntimeConfiguration
from api_assistant.core.agent import APIAssistant
from api_assistant.core.constants import (
    NODE_CALL_API,
    NODE_CALL_MODEL,
    NODE_HUMAN_REVIEW,
    NODE_LOAD_API_SPECS,
    NODE_LOAD_API_SUMMARIES,
    NODE_SELECT_RELEVANT_APIS,
    NODE_CHECK_CACHE,
)
from api_assistant.core.interrupts import process_human_review
from api_assistant.core.schemas import AgentState, InputSchema, OutputSchema
from api_assistant.core.workflow import create_and_compile_workflow
from api_assistant.services.api_docs_service import APIService


@pytest.fixture
def mock_agent():
    """Create a mock APIAssistant instance."""
    agent = MagicMock(spec=APIAssistant)
    agent.http_toolkit = MagicMock()
    agent.http_toolkit.get_tools.return_value = [MagicMock(), MagicMock()]
    return agent


@pytest.fixture
def mock_memory_store():
    """Create a mock memory store."""
    return MagicMock(spec=MemorySaver)


@pytest.fixture
def mock_available_tools():
    """Create mock available tools."""
    return {"call_api": MagicMock(spec=ToolNode)}


class TestWorkflowCreation:
    """Test suite for workflow creation and compilation."""

    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_create_and_compile_workflow_basic(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test basic workflow creation without custom tools."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_compiled_graph = MagicMock(spec=CompiledStateGraph)
        mock_graph_instance.compile.return_value = mock_compiled_graph

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Call function
        result = create_and_compile_workflow(mock_agent)

        # Verify StateGraph creation
        mock_state_graph.assert_called_once_with(
            AgentState,
            config_schema=BaseRuntimeConfiguration,
            input=InputSchema,
            output=OutputSchema,
        )

        # Verify nodes were added
        mock_graph_instance.add_node.assert_any_call(
            NODE_LOAD_API_SUMMARIES, APIService.load_api_summaries
        )
        mock_graph_instance.add_node.assert_any_call(
            NODE_SELECT_RELEVANT_APIS, mock_agent.select_relevant_apis
        )
        mock_graph_instance.add_node.assert_any_call(
            NODE_LOAD_API_SPECS, APIService.load_openapi_specifications
        )
        mock_graph_instance.add_node.assert_any_call(
            NODE_CALL_MODEL, mock_agent.generate_model_response
        )
        mock_graph_instance.add_node.assert_any_call(
            NODE_CALL_API, mock_tool_node_instance
        )
        mock_graph_instance.add_node.assert_any_call(
            NODE_HUMAN_REVIEW, process_human_review
        )

        # Verify edges were added
        mock_graph_instance.add_edge.assert_any_call(
            NODE_LOAD_API_SUMMARIES, NODE_SELECT_RELEVANT_APIS
        )
        mock_graph_instance.add_edge.assert_any_call(
            NODE_LOAD_API_SPECS, NODE_CALL_MODEL
        )
        mock_graph_instance.add_edge.assert_any_call(NODE_CALL_API, NODE_CALL_MODEL)

        # Verify conditional edges
        mock_graph_instance.add_conditional_edges.assert_any_call(
            NODE_SELECT_RELEVANT_APIS,
            mock_agent.determine_next_step,
            [NODE_LOAD_API_SPECS, NODE_CALL_MODEL],
        )
        mock_graph_instance.add_conditional_edges.assert_any_call(
            NODE_CALL_MODEL,
            mock_agent.determine_workflow_action,
            [NODE_HUMAN_REVIEW, END, NODE_CALL_API],
        )

        # Verify compilation
        mock_graph_instance.compile.assert_called_once_with(checkpointer=None)
        assert result == mock_compiled_graph

    @patch("api_assistant.core.workflow.StateGraph")
    def test_create_and_compile_workflow_with_custom_tools(
        self, mock_state_graph, mock_agent, mock_available_tools
    ):
        """Test workflow creation with custom available tools."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_compiled_graph = MagicMock(spec=CompiledStateGraph)
        mock_graph_instance.compile.return_value = mock_compiled_graph

        # Call function with custom tools
        result = create_and_compile_workflow(
            mock_agent, available_tools=mock_available_tools
        )

        # Verify that custom tools were used instead of creating new ones
        mock_graph_instance.add_node.assert_any_call(
            NODE_CALL_API, mock_available_tools["call_api"]
        )

        # Verify compilation
        mock_graph_instance.compile.assert_called_once_with(checkpointer=None)
        assert result == mock_compiled_graph

    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_create_and_compile_workflow_with_memory_store(
        self, mock_tool_node, mock_state_graph, mock_agent, mock_memory_store
    ):
        """Test workflow creation with memory store."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_compiled_graph = MagicMock(spec=CompiledStateGraph)
        mock_graph_instance.compile.return_value = mock_compiled_graph

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Call function with memory store
        result = create_and_compile_workflow(mock_agent, memory_store=mock_memory_store)

        # Verify compilation with memory store
        mock_graph_instance.compile.assert_called_once_with(
            checkpointer=mock_memory_store
        )
        assert result == mock_compiled_graph

    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_create_and_compile_workflow_with_partial_tools(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test workflow creation when available_tools is provided but missing call_api."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_compiled_graph = MagicMock(spec=CompiledStateGraph)
        mock_graph_instance.compile.return_value = mock_compiled_graph

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Call function with partial tools (missing call_api)
        partial_tools = {"other_tool": MagicMock()}
        result = create_and_compile_workflow(mock_agent, available_tools=partial_tools)

        # Verify that call_api tool was created using agent's toolkit
        mock_tool_node.assert_called_once_with(mock_agent.http_toolkit.get_tools())
        mock_graph_instance.add_node.assert_any_call(
            NODE_CALL_API, mock_tool_node_instance
        )

        # Verify compilation
        mock_graph_instance.compile.assert_called_once_with(checkpointer=None)
        assert result == mock_compiled_graph

    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_create_and_compile_workflow_node_functions(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test that correct functions are assigned to workflow nodes."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_compiled_graph = MagicMock(spec=CompiledStateGraph)
        mock_graph_instance.compile.return_value = mock_compiled_graph

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Call function
        create_and_compile_workflow(mock_agent)

        # Verify that correct functions are assigned to nodes
        add_node_calls = mock_graph_instance.add_node.call_args_list

        # Find the call for load_api_summaries
        load_api_call = next(
            call for call in add_node_calls if call[0][0] == NODE_LOAD_API_SUMMARIES
        )
        assert load_api_call[0][1] == APIService.load_api_summaries

        # Find the call for select_relevant_apis
        select_apis_call = next(
            call for call in add_node_calls if call[0][0] == NODE_SELECT_RELEVANT_APIS
        )
        assert select_apis_call[0][1] == mock_agent.select_relevant_apis

        # Find the call for load_api_specs
        load_specs_call = next(
            call for call in add_node_calls if call[0][0] == NODE_LOAD_API_SPECS
        )
        assert load_specs_call[0][1] == APIService.load_openapi_specifications

        # Find the call for call_model
        call_model_call = next(
            call for call in add_node_calls if call[0][0] == NODE_CALL_MODEL
        )
        assert call_model_call[0][1] == mock_agent.generate_model_response

    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_create_and_compile_workflow_entry_point(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test that the entry point is set correctly."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_compiled_graph = MagicMock(spec=CompiledStateGraph)
        mock_graph_instance.compile.return_value = mock_compiled_graph

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Call function
        create_and_compile_workflow(mock_agent)

        # Verify entry point is set
        mock_graph_instance.set_entry_point.assert_called_once_with(
            NODE_CHECK_CACHE
        )

    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_create_and_compile_workflow_conditional_edges(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test that conditional edges are set up correctly."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_compiled_graph = MagicMock(spec=CompiledStateGraph)
        mock_graph_instance.compile.return_value = mock_compiled_graph

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Call function
        create_and_compile_workflow(mock_agent)

        # Verify conditional edges
        conditional_edge_calls = (
            mock_graph_instance.add_conditional_edges.call_args_list
        )

        # Check select_relevant_apis conditional edge
        select_apis_edge = next(
            call
            for call in conditional_edge_calls
            if call[0][0] == NODE_SELECT_RELEVANT_APIS
        )
        assert select_apis_edge[0][1] == mock_agent.determine_next_step
        assert select_apis_edge[0][2] == [NODE_LOAD_API_SPECS, NODE_CALL_MODEL]

        # Check call_model conditional edge
        call_model_edge = next(
            call for call in conditional_edge_calls if call[0][0] == NODE_CALL_MODEL
        )
        assert call_model_edge[0][1] == mock_agent.determine_workflow_action
        # The third argument should contain "human_review", END, and "call_api"
        assert NODE_HUMAN_REVIEW in call_model_edge[0][2]
        assert END in call_model_edge[0][2]
        assert NODE_CALL_API in call_model_edge[0][2]



    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_workflow_error_handling(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test workflow creation error handling."""
        # Setup mocks to simulate an error
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_graph_instance.add_node.side_effect = Exception("Node addition failed")

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Verify that the error is propagated
        with pytest.raises(Exception, match="Node addition failed"):
            create_and_compile_workflow(mock_agent)

    @patch("api_assistant.core.workflow.StateGraph")
    @patch("api_assistant.core.workflow.ToolNode")
    def test_workflow_compilation_error_handling(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test workflow compilation error handling."""
        # Setup mocks
        mock_graph_instance = MagicMock(spec=StateGraph)
        mock_state_graph.return_value = mock_graph_instance

        mock_graph_instance.compile.side_effect = Exception("Compilation failed")

        mock_tool_node_instance = MagicMock(spec=ToolNode)
        mock_tool_node.return_value = mock_tool_node_instance

        # Verify that the error is propagated
        with pytest.raises(Exception, match="Compilation failed"):
            create_and_compile_workflow(mock_agent)
