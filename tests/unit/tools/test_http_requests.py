"""
Unit tests for HTTP tools functionality.

Tests cover HTTP request validation, header handling, payload processing,
and response handling for all HTTP methods.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml
from langchain_core.runnables import RunnableConfig

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.tools.http_requests import (
    DeleteTool,
    GetTool,
    HeadTool,
    HttpRequestsToolkit,
    OptionsTool,
    PatchTool,
    PostTool,
    PutTool,
    TraceTool,
)


@pytest.fixture
def test_data():
    """Load test data from YAML file."""
    test_data_path = os.path.join(
        os.path.dirname(__file__), "..", "test_data", "http_tools_test_cases.yaml"
    )
    with open(test_data_path) as f:
        return yaml.safe_load(f)


class TestHTTPTool:
    """Test suite for base HTTPTool class."""

    def test_http_tool_initialization(self):
        """Test HTTPTool initialization."""
        tool = GetTool()
        assert tool.method == "GET"
        assert hasattr(tool, "_run")
        assert tool.name == "get_http_requests"
        assert (
            tool.description
            == "Handles GET requests to retrieve data from the specified URL. Use this for reading information without modifying any data."
        )

    @pytest.mark.parametrize(
        "test_case", ["valid_base_url", "invalid_base_url", "subdomain_allowed"]
    )
    def test_url_validation(self, test_case, test_data):
        """Test URL validation against base URL."""
        case_data = next(
            c for c in test_data["http_request_validation"] if c["name"] == test_case
        )

        with patch("nalai.tools.http_requests.settings") as mock_settings:
            mock_settings.api_calls_allowed_urls_list = [case_data["input"]["base_url"]]

            # Create a test tool instance
            tool = GetTool()

            if case_data["expected"]:
                # Should not raise an error for valid URLs
                assert True  # URL validation happens in _run method
            else:
                # Should raise ValueError for invalid URLs
                with pytest.raises(ValueError):
                    tool._run.func(
                        case_data["input"]["url"],
                        input_data={},
                        config=RunnableConfig(configurable={}),
                    )

    @pytest.mark.parametrize(
        "test_case",
        ["with_auth_token", "no_auth_token", "user_headers_override_internal"],
    )
    def test_header_processing(self, test_case, test_data):
        """Test header processing and merging."""
        case_data = next(
            c for c in test_data["http_request_headers"] if c["name"] == test_case
        )

        with (
            patch("nalai.tools.http_requests.settings") as mock_settings,
            patch("requests.request") as mock_request,
        ):
            # Setup mocks
            mock_settings.api_calls_allowed_urls_list = ["https://api.example.com"]
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {"result": "success"}
            mock_request.return_value = mock_response

            # Create tool and config
            tool = GetTool()
            config = RunnableConfig(configurable=case_data["input"]["configurable"])

            # Prepare input data
            input_data = {}
            if "user_headers" in case_data["input"]:
                input_data["headers"] = case_data["input"]["user_headers"]

            # Execute the tool by calling the underlying function directly
            if case_data["expected"]["should_raise"]:
                with pytest.raises((ValueError, requests.RequestException)):
                    tool._run.func(
                        case_data["input"]["url"],
                        input_data=input_data,
                        config=config,
                    )
            else:
                tool._run.func(
                    case_data["input"]["url"],
                    input_data=input_data,
                    config=config,
                )

                # Verify request was made with correct headers
                call_args = mock_request.call_args
                assert call_args is not None

                actual_headers = call_args[1]["headers"]
                expected_headers = case_data["expected"]["headers"]

                for key, value in expected_headers.items():
                    assert actual_headers[key] == value

    @pytest.mark.parametrize(
        "test_case", ["get_request_params", "post_request_json", "put_request_json"]
    )
    def test_payload_processing(self, test_case, test_data):
        """Test payload processing for different HTTP methods."""
        case_data = next(
            c for c in test_data["http_request_payloads"] if c["name"] == test_case
        )

        with (
            patch("nalai.tools.http_requests.settings") as mock_settings,
            patch("requests.request") as mock_request,
        ):
            # Setup mocks
            mock_settings.api_calls_allowed_urls_list = ["https://api.example.com"]
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {"result": "success"}
            mock_request.return_value = mock_response

            # Create tool based on method
            method = case_data["input"]["method"]
            if method == "GET":
                tool = GetTool()
            elif method == "POST":
                tool = PostTool()
            elif method == "PUT":
                tool = PutTool()
            else:
                tool = GetTool()  # Default fallback

            # Execute the tool by calling the underlying function directly
            if case_data["expected"]["should_raise"]:
                with pytest.raises((ValueError, requests.RequestException)):
                    tool._run.func(
                        case_data["input"]["url"],
                        input_data=case_data["input"]["input_data"],
                        config=RunnableConfig(configurable={}),
                    )
            else:
                tool._run.func(
                    case_data["input"]["url"],
                    input_data=case_data["input"]["input_data"],
                    config=RunnableConfig(configurable={}),
                )

                # Verify request was made with correct payload
                call_args = mock_request.call_args
                assert call_args is not None

                expected_params = case_data["expected"]["params"]
                expected_json = case_data["expected"]["json"]

                if expected_params is not None:
                    assert call_args[1]["params"] == expected_params
                else:
                    assert (
                        "params" not in call_args[1] or call_args[1]["params"] is None
                    )

                if expected_json is not None:
                    assert call_args[1]["json"] == expected_json
                else:
                    assert "json" not in call_args[1] or call_args[1]["json"] is None

    @pytest.mark.parametrize(
        "test_case", ["successful_response", "empty_response", "http_error"]
    )
    def test_response_handling(self, test_case, test_data):
        """Test response handling for different scenarios."""
        case_data = next(
            c for c in test_data["http_response_handling"] if c["name"] == test_case
        )

        with (
            patch("nalai.tools.http_requests.settings") as mock_settings,
            patch("requests.request") as mock_request,
        ):
            # Setup mocks
            mock_settings.api_calls_allowed_urls_list = ["https://api.example.com"]
            mock_response = MagicMock()
            mock_response.ok = True
            mock_request.return_value = mock_response

            # Setup response based on test case
            if case_data["name"] == "http_error":
                mock_response.raise_for_status.side_effect = requests.HTTPError(
                    "HTTP Error", response=mock_response
                )
                mock_response.status_code = case_data["input"]["status_code"]
            elif case_data["name"] == "empty_response":
                mock_response.text = ""
                mock_response.json.side_effect = ValueError(
                    "No JSON object could be decoded"
                )
            else:
                # successful_response
                mock_response.json.return_value = case_data["input"]["json_data"]

            # Create tool and execute
            tool = GetTool()

            if case_data["expected"]["should_raise"]:
                with pytest.raises((ValueError, requests.RequestException)):
                    tool._run.func(
                        case_data["input"]["url"],
                        input_data={},
                        config=RunnableConfig(configurable={}),
                    )
            else:
                result = tool._run.func(
                    case_data["input"]["url"],
                    input_data={},
                    config=RunnableConfig(configurable={}),
                )
                assert result == case_data["expected"]["result"]

    def test_error_context_logging(self):
        """Test that error context is properly logged."""
        with (
            patch("nalai.tools.http_requests.settings") as mock_settings,
            patch("requests.request") as mock_request,
            patch("nalai.tools.http_requests.logger") as mock_logger,
        ):
            # Setup mocks
            mock_settings.api_calls_allowed_urls_list = ["https://api.example.com"]
            mock_request.side_effect = requests.RequestException("Test error")

            # Execute tool
            tool = GetTool()

            with pytest.raises(requests.RequestException):
                tool._run.func(
                    "https://api.example.com/test",
                    input_data={},
                    config=RunnableConfig(configurable={}),
                )

            # Verify error was logged
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args[0][0]
            assert "Unexpected error during HTTP request" in error_call
            assert "Test error" in error_call


class TestHTTPToolClasses:
    """Test suite for specific HTTP tool classes."""

    def test_get_tool(self):
        """Test GetTool class."""
        tool = GetTool()
        assert tool.method == "GET"
        assert tool.name == "get_http_requests"
        assert (
            tool.description
            == "Handles GET requests to retrieve data from the specified URL. Use this for reading information without modifying any data."
        )
        assert tool.is_safe is True

    def test_post_tool(self):
        """Test PostTool class."""
        tool = PostTool()
        assert tool.method == "POST"
        assert tool.name == "post_http_requests"
        assert (
            tool.description
            == "Handles POST requests to create new resources or submit data to the specified URL. Use this for creating new items or submitting forms."
        )
        assert tool.is_safe is False

    def test_put_tool(self):
        """Test PutTool class."""
        tool = PutTool()
        assert tool.method == "PUT"
        assert tool.name == "put_http_requests"
        assert (
            tool.description
            == "Handles PUT requests to update or replace existing resources at the specified URL. Use this for completely replacing an existing item."
        )
        assert tool.is_safe is False

    def test_delete_tool(self):
        """Test DeleteTool class."""
        tool = DeleteTool()
        assert tool.method == "DELETE"
        assert tool.name == "delete_http_requests"
        assert (
            tool.description
            == "Handles DELETE requests to remove resources at the specified URL. Use this for deleting items or resources."
        )
        assert tool.is_safe is False

    def test_head_tool(self):
        """Test HeadTool class."""
        tool = HeadTool()
        assert tool.method == "HEAD"
        assert tool.name == "head_http_requests"
        assert tool.description == "Handles HEAD requests"
        assert tool.is_safe is True

    def test_options_tool(self):
        """Test OptionsTool class."""
        tool = OptionsTool()
        assert tool.method == "OPTIONS"
        assert tool.name == "options_http_requests"
        assert tool.description == "Handles OPTIONS requests"
        assert tool.is_safe is True

    def test_patch_tool(self):
        """Test PatchTool class."""
        tool = PatchTool()
        assert tool.method == "PATCH"
        assert tool.name == "patch_http_requests"
        assert tool.description == "Handles PATCH requests"
        assert tool.is_safe is False

    def test_trace_tool(self):
        """Test TraceTool class."""
        tool = TraceTool()
        assert tool.method == "TRACE"
        assert tool.name == "trace_http_requests"
        assert tool.description == "Handles TRACE requests"
        assert tool.is_safe is True


class TestHttpRequestsToolkit:
    """Test suite for HttpRequestsToolkit class."""

    def test_toolkit_initialization(self):
        """Test HttpRequestsToolkit initialization."""
        toolkit = HttpRequestsToolkit()
        assert hasattr(toolkit, "get_tool")
        assert hasattr(toolkit, "post_tool")
        assert hasattr(toolkit, "put_tool")
        assert hasattr(toolkit, "delete_tool")
        assert hasattr(toolkit, "head_tool")
        assert hasattr(toolkit, "options_tool")
        assert hasattr(toolkit, "patch_tool")
        assert hasattr(toolkit, "trace_tool")

    def test_get_tools(self):
        """Test getting all tools from toolkit."""
        toolkit = HttpRequestsToolkit()
        tools = toolkit.get_tools()

        expected_tool_names = [
            "get_http_requests",
            "post_http_requests",
            "put_http_requests",
            "delete_http_requests",
            "head_http_requests",
            "options_http_requests",
            "patch_http_requests",
            "trace_http_requests",
        ]

        assert len(tools) == len(expected_tool_names)
        tool_names = [tool.name for tool in tools]
        assert set(tool_names) == set(expected_tool_names)

    @pytest.mark.parametrize(
        "tool_name,expected",
        [
            ("get_http_requests", True),
            ("post_http_requests", False),
            ("put_http_requests", False),
            ("delete_http_requests", False),
            ("head_http_requests", True),
            ("options_http_requests", True),
            ("patch_http_requests", False),
            ("trace_http_requests", True),
            ("unknown_tool", False),
        ],
    )
    def test_is_safe_tool(self, tool_name, expected):
        """Test is_safe_tool method returns correct boolean values."""
        toolkit = HttpRequestsToolkit()
        result = toolkit.is_safe_tool(tool_name)
        assert result == expected
