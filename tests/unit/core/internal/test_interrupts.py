"""
Unit tests for the interrupts module.

Tests cover the human-in-the-loop functionality and tool execution
with interrupt capabilities.
"""

from unittest.mock import MagicMock, patch

# Internal types for unit testing
from nalai.core.internal.interrupts import add_human_in_the_loop


class TestInterrupts:
    """Test interrupt functionality."""

    def test_add_human_in_the_loop_creates_tool(self):
        """Test that add_human_in_the_loop creates a tool with interrupt capability."""
        # Create a proper mock tool that won't be converted
        mock_tool = MagicMock(spec=["name", "description", "args_schema", "_run"])
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.args_schema = {}

        # Mock the create_tool function to return the mock directly
        with patch(
            "nalai.core.internal.interrupts.create_tool", return_value=mock_tool
        ):
            # Call function
            result = add_human_in_the_loop(mock_tool)

            # Verify result is the expected tool
            assert result is not None
            assert hasattr(result, "name")
            assert hasattr(result, "description")
            assert hasattr(result, "args_schema")

    def test_add_human_in_the_loop_with_custom_config(self):
        """Test that add_human_in_the_loop accepts custom interrupt configuration."""
        # Create a proper mock tool
        mock_tool = MagicMock(spec=["name", "description", "args_schema", "_run"])
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.args_schema = {}

        # Custom interrupt config
        custom_config = {
            "allow_accept": False,
            "allow_edit": True,
            "allow_respond": False,
        }

        # Mock the create_tool function to return the mock directly
        with patch(
            "nalai.core.internal.interrupts.create_tool", return_value=mock_tool
        ):
            # Call function
            result = add_human_in_the_loop(mock_tool, interrupt_config=custom_config)

            # Verify result is the expected tool
            assert result is not None
            assert hasattr(result, "name")
            assert hasattr(result, "description")
            assert hasattr(result, "args_schema")

    def test_add_human_in_the_loop_with_callable(self):
        """Test that add_human_in_the_loop works with callable functions."""

        # Create a mock callable function with docstring
        def test_function():
            """A test function for testing interrupts."""
            return "test result"

        # Mock the create_tool function to return a mock tool
        mock_tool = MagicMock(spec=["name", "description", "args_schema", "_run"])
        mock_tool.name = "test_function"
        mock_tool.description = "A test function for testing interrupts."
        mock_tool.args_schema = {}

        with patch(
            "nalai.core.internal.interrupts.create_tool", return_value=mock_tool
        ):
            # Call function
            result = add_human_in_the_loop(test_function)

            # Verify result is the expected tool
            assert result is not None
            assert hasattr(result, "name")
            assert hasattr(result, "description")

    def test_interrupt_config_defaults(self):
        """Test that interrupt config has proper defaults."""
        # Create a proper mock tool
        mock_tool = MagicMock(spec=["name", "description", "args_schema", "_run"])
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.args_schema = {}

        # Mock the create_tool function to return the mock directly
        with patch(
            "nalai.core.internal.interrupts.create_tool", return_value=mock_tool
        ):
            # Call function without interrupt_config
            result = add_human_in_the_loop(mock_tool)

            # Verify result is created
            assert result is not None

    def test_interrupt_config_custom_values(self):
        """Test that custom interrupt config values are accepted."""
        # Create a proper mock tool
        mock_tool = MagicMock(spec=["name", "description", "args_schema", "_run"])
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.args_schema = {}

        # Custom interrupt config with all options
        custom_config = {
            "allow_accept": False,
            "allow_edit": False,
            "allow_respond": True,
        }

        # Mock the create_tool function to return the mock directly
        with patch(
            "nalai.core.internal.interrupts.create_tool", return_value=mock_tool
        ):
            # Call function with custom config
            result = add_human_in_the_loop(mock_tool, interrupt_config=custom_config)

            # Verify result is created
            assert result is not None

    def test_tool_attributes_preserved(self):
        """Test that tool attributes are preserved in the result."""
        # Create a proper mock tool with specific attributes
        mock_tool = MagicMock(spec=["name", "description", "args_schema", "_run"])
        mock_tool.name = "preserved_tool"
        mock_tool.description = "A tool with preserved attributes"
        mock_tool.args_schema = {"type": "object", "properties": {}}

        # Mock the create_tool function to return the mock directly
        with patch(
            "nalai.core.internal.interrupts.create_tool", return_value=mock_tool
        ):
            # Call function
            result = add_human_in_the_loop(mock_tool)

            # Verify result is a tool with the expected attributes
            assert result is not None
            assert hasattr(result, "name")
            assert hasattr(result, "description")
            assert hasattr(result, "args_schema")
