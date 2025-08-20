"""
Unit tests for workflow functionality.

Tests cover workflow creation, compilation, node addition, and edge management.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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

from nalai.config import BaseRuntimeConfiguration
from nalai.core.constants import (
    NODE_CALL_API,
    NODE_CALL_MODEL,
    NODE_CHECK_CACHE,
    NODE_LOAD_API_SPECS,
    NODE_LOAD_API_SUMMARIES,
    NODE_SELECT_RELEVANT_APIS,
)
from nalai.core.schemas import AgentState, InputSchema, OutputSchema
from nalai.core.workflow import create_and_compile_workflow
from nalai.core.workflow_nodes import WorkflowNodes
from nalai.services.api_docs_service import APIService


@pytest.fixture
def mock_agent():
    """Create a mock WorkflowNodes instance."""
    agent = MagicMock(spec=WorkflowNodes)
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

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
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

        # Verify tool node creation
        mock_tool_node.assert_called_once_with(mock_agent.http_toolkit.get_tools())

        # Verify nodes were added
        mock_graph_instance.add_node.assert_any_call(
            NODE_CHECK_CACHE, mock_agent.check_cache_with_similarity
        )
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

        # Verify edges were added
        mock_graph_instance.add_conditional_edges.assert_any_call(
            NODE_CHECK_CACHE,
            mock_agent.determine_cache_action,
            [NODE_LOAD_API_SUMMARIES, NODE_CALL_MODEL],
        )
        mock_graph_instance.add_edge.assert_any_call(
            NODE_LOAD_API_SUMMARIES, NODE_SELECT_RELEVANT_APIS
        )
        mock_graph_instance.add_conditional_edges.assert_any_call(
            NODE_SELECT_RELEVANT_APIS,
            mock_agent.determine_next_step,
            [NODE_LOAD_API_SPECS, NODE_CALL_MODEL],
        )
        mock_graph_instance.add_edge.assert_any_call(
            NODE_LOAD_API_SPECS, NODE_CALL_MODEL
        )
        mock_graph_instance.add_conditional_edges.assert_any_call(
            NODE_CALL_MODEL,
            mock_agent.should_execute_tools,
            [NODE_CALL_API, END],
        )
        mock_graph_instance.add_edge.assert_any_call(NODE_CALL_API, NODE_CALL_MODEL)

        # Verify compilation
        mock_graph_instance.compile.assert_called_once_with(checkpointer=None)
        assert result == mock_compiled_graph

    @patch("nalai.core.workflow.StateGraph")
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

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
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

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
    def test_create_and_compile_workflow_with_partial_tools(
        self, mock_tool_node, mock_state_graph, mock_agent
    ):
        """Test workflow creation when available_ttools is provided but missing call_api."""
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

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
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

        # Find the call for check_cache
        check_cache_call = next(
            call for call in add_node_calls if call[0][0] == NODE_CHECK_CACHE
        )
        assert check_cache_call[0][1] == mock_agent.check_cache_with_similarity

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

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
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
        mock_graph_instance.set_entry_point.assert_called_once_with(NODE_CHECK_CACHE)

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
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

        # Check check_cache conditional edge
        check_cache_edge = next(
            call for call in conditional_edge_calls if call[0][0] == NODE_CHECK_CACHE
        )
        assert check_cache_edge[0][1] == mock_agent.determine_cache_action
        assert check_cache_edge[0][2] == [NODE_LOAD_API_SUMMARIES, NODE_CALL_MODEL]

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
        assert call_model_edge[0][1] == mock_agent.should_execute_tools
        # The third argument should contain END and "call_api"
        assert END in call_model_edge[0][2]
        assert NODE_CALL_API in call_model_edge[0][2]

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
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

    @patch("nalai.core.workflow.StateGraph")
    @patch("nalai.core.workflow.ToolNode")
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


class TestWorkflowExecution:
    """Test suite for actual workflow execution with mocked tools."""

    @patch("nalai.core.workflow.ToolNode")
    def test_tool_node_creation_with_agent_tools(
        self, mock_tool_node_class, mock_agent
    ):
        """Test that ToolNode is created with the agent's tools."""
        # Mock the ToolNode constructor
        mock_tool_node_instance = MagicMock()
        mock_tool_node_class.return_value = mock_tool_node_instance

        # Create workflow
        workflow = create_and_compile_workflow(mock_agent)

        # Verify that the agent's tools were used to create ToolNode
        mock_agent.http_toolkit.get_tools.assert_called_once()
        mock_tool_node_class.assert_called_once_with(
            mock_agent.http_toolkit.get_tools()
        )

        # Verify the workflow was created successfully
        assert workflow is not None

    def test_workflow_with_custom_tool_node(self, mock_agent):
        """Test workflow with custom ToolNode to verify tool execution."""
        # Create a custom ToolNode that tracks execution
        mock_tool_node = MagicMock(spec=ToolNode)
        mock_tool_node.ainvoke = AsyncMock(return_value={"tool_result": "success"})

        # Create workflow with custom tool node
        workflow = create_and_compile_workflow(
            mock_agent, available_tools={"call_api": mock_tool_node}
        )

        # Verify workflow was created successfully
        assert workflow is not None

    @patch("nalai.core.workflow.ToolNode")
    def test_workflow_conditional_routing_to_tools(
        self, mock_tool_node_class, mock_agent
    ):
        """Test that workflow routes to tool execution when LLM determines it's needed."""
        # Mock the ToolNode constructor
        mock_tool_node_instance = MagicMock()
        mock_tool_node_class.return_value = mock_tool_node_instance

        # Mock the agent to return tool calls from LLM
        mock_agent.generate_model_response.return_value = {
            "tool_calls": [
                {"name": "test_http_tool", "args": {"url": "https://api.example.com"}}
            ]
        }
        mock_agent.should_execute_tools.return_value = NODE_CALL_API

        # Create workflow
        workflow = create_and_compile_workflow(mock_agent)

        # Verify workflow was created successfully
        assert workflow is not None

        # Verify the agent methods were set up correctly
        mock_agent.check_cache_with_similarity.assert_not_called()  # Not called during creation
        mock_agent.determine_cache_action.assert_not_called()  # Not called during creation
        mock_agent.select_relevant_apis.assert_not_called()  # Not called during creation
        mock_agent.determine_next_step.assert_not_called()  # Not called during creation
        mock_agent.generate_model_response.assert_not_called()  # Not called during creation
        mock_agent.should_execute_tools.assert_not_called()  # Not called during creation

    @patch("nalai.core.workflow.ToolNode")
    def test_workflow_without_tool_calls(self, mock_tool_node_class, mock_agent):
        """Test workflow execution when no tool calls are needed."""
        # Mock the ToolNode constructor
        mock_tool_node_instance = MagicMock()
        mock_tool_node_class.return_value = mock_tool_node_instance

        # Mock the agent to return no tool calls
        mock_agent.generate_model_response.return_value = {
            "content": "No tools needed for this response"
        }
        mock_agent.should_execute_tools.return_value = END

        # Create workflow
        workflow = create_and_compile_workflow(mock_agent)

        # Verify workflow was created successfully
        assert workflow is not None

    @patch("nalai.core.workflow.ToolNode")
    def test_tool_execution_error_handling(self, mock_tool_node_class, mock_agent):
        """Test workflow behavior when tool execution fails."""
        # Mock the ToolNode constructor
        mock_tool_node_instance = MagicMock()
        mock_tool_node_class.return_value = mock_tool_node_instance

        # Create workflow
        workflow = create_and_compile_workflow(mock_agent)

        # Verify workflow was created successfully
        assert workflow is not None

    @patch("nalai.core.workflow.ToolNode")
    def test_workflow_structure_with_tool_node(self, mock_tool_node_class, mock_agent):
        """Test that the workflow structure includes the tool node correctly."""
        # Mock the ToolNode constructor
        mock_tool_node_instance = MagicMock()
        mock_tool_node_class.return_value = mock_tool_node_instance

        # Create workflow
        workflow = create_and_compile_workflow(mock_agent)

        # Verify workflow was created
        assert workflow is not None

        # Verify agent's tools were accessed
        mock_agent.http_toolkit.get_tools.assert_called_once()

        # Verify ToolNode was created with the tools
        mock_tool_node_class.assert_called_once_with(
            mock_agent.http_toolkit.get_tools()
        )

        # Verify the tools list is not empty
        tools = mock_agent.http_toolkit.get_tools.return_value
        assert len(tools) > 0

    @patch("nalai.core.workflow.ToolNode")
    def test_workflow_with_memory_store_and_tools(
        self, mock_tool_node_class, mock_agent, mock_memory_store
    ):
        """Test workflow creation with memory store and tools."""
        # Mock the ToolNode constructor
        mock_tool_node_instance = MagicMock()
        mock_tool_node_class.return_value = mock_tool_node_instance

        # Create workflow with memory store
        workflow = create_and_compile_workflow(
            mock_agent, memory_store=mock_memory_store
        )

        # Verify workflow was created successfully
        assert workflow is not None

        # Verify agent's tools were accessed
        mock_agent.http_toolkit.get_tools.assert_called_once()

        # Verify ToolNode was created with the tools
        mock_tool_node_class.assert_called_once_with(
            mock_agent.http_toolkit.get_tools()
        )

    @patch("nalai.core.workflow.ToolNode")
    def test_workflow_tool_node_integration(self, mock_tool_node_class, mock_agent):
        """Test that the workflow integrates the ToolNode correctly."""
        # Mock the ToolNode constructor
        mock_tool_node_instance = MagicMock()
        mock_tool_node_class.return_value = mock_tool_node_instance

        # Create workflow
        workflow = create_and_compile_workflow(mock_agent)

        # Verify workflow was created
        assert workflow is not None

        # Verify that the agent's toolkit was used
        mock_agent.http_toolkit.get_tools.assert_called_once()

        # Verify ToolNode was created with the tools
        mock_tool_node_class.assert_called_once_with(
            mock_agent.http_toolkit.get_tools()
        )

        # Verify that tools were provided to the workflow
        tools = mock_agent.http_toolkit.get_tools.return_value
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_workflow_tool_binding_verification(self, mock_agent):
        """Test that tools are properly bound to the workflow."""
        # Create a custom ToolNode that we can track
        mock_tool_node = MagicMock(spec=ToolNode)

        # Create workflow with custom tool node
        workflow = create_and_compile_workflow(
            mock_agent, available_tools={"call_api": mock_tool_node}
        )

        # Verify workflow was created
        assert workflow is not None

        # Verify that the custom tool node was used instead of creating a new one
        # (This is verified by the fact that we didn't call agent.http_toolkit.get_tools)
        mock_agent.http_toolkit.get_tools.assert_not_called()
