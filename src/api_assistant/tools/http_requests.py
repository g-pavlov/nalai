import logging
import traceback
from datetime import UTC, datetime

import requests
from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import Field

from ..config import settings

logger = logging.getLogger(__name__)


class HTTPTool(BaseTool):
    """Base class for HTTP tools.

    Attributes:
        method (str): The HTTP method handled by this tool.
    """

    method: str = Field(
        default="GET", description="The HTTP method handled by this tool"
    )

    def _run(
        self,
        url: str,
        config: RunnableConfig,
        run_manager: CallbackManagerForToolRun | None = None,
        input_data: dict | None = None,
    ) -> dict:
        """Executes an HTTP request using the specified method.

        Args:
            url (str): The target URL for the HTTP request.
            config (RunnableConfig): Configuration object containing runtime parameters.
            run_manager (Optional[CallbackManagerForToolRun], optional): Manager for handling callbacks during the tool run. Defaults to None.
            input_data (Optional[dict], optional): Data to be sent with the request, either as query parameters or JSON payload, depending on the HTTP method. Defaults to None.

        Returns:
            dict: The JSON response from the HTTP request.

        Raises:
            requests.HTTPError: If the HTTP request returns an unsuccessful status code.
        """
        logger.debug("sending HTTP request: %s %s", self.method, url)

        configurable = config.get("configurable", {}) if config else {}
        internal_headers = {}

        if auth_token := configurable.get("auth_token"):
            internal_headers["Authorization"] = f"Bearer {auth_token}"

        # Extract user-supplied headers, excluding internal ones
        llm_supplied_headers = {}
        if input_data:
            user_headers = input_data.pop("headers", {})
            llm_supplied_headers = {
                key: value
                for key, value in user_headers.items()
                if key.lower() not in {k.lower() for k in internal_headers}
            }

        # Merge headers (internal overrides user-supplied)
        headers = {**llm_supplied_headers, **internal_headers}

        # Decide payload or query params
        is_body_method = self.method in ["POST", "PUT", "PATCH"]
        request_kwargs = {
            "headers": headers,
            "params": input_data if not is_body_method else None,
            "json": input_data if is_body_method else None,
        }

        # Create error context
        error_context = {
            "tool_name": getattr(self, "name", "unknown_tool"),
            "method": self.method,
            "url": url,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_context": {
                "email": configurable.get("user_email", "unknown"),
                "org_unit_id": configurable.get("org_unit_id", "unknown"),
            },
            "thread_id": configurable.get("thread_id", "unknown"),
        }

        api_calls_base_url = settings.api_calls_base_url
        if api_calls_base_url not in url:
            error = ValueError(
                f"HTTP requests are restricted to {api_calls_base_url}. Attempted to access: {url}"
            )
            error_context.update(
                {
                    "error_message": str(error),
                }
            )
            logger.error(
                f"Unexpected error during HTTP request. Error context: {error_context}"
            )
            if run_manager:
                run_manager.on_tool_error(error)
            raise error

        try:
            response = requests.request(self.method, url, **request_kwargs)
            response.raise_for_status()

            logger.info(
                f"Received HTTP response: {self.method} {url}, status code: {response.status_code}"
            )

            if response.ok and not response.text.strip():
                if run_manager:
                    run_manager.on_tool_end(output={})
                return {}

            if run_manager:
                run_manager.on_tool_end(output=response.json())

            return response.json()

        except requests.HTTPError as e:
            error_context.update(
                {
                    "error_type": "HTTPError",
                    "status_code": getattr(e.response, "status_code", None),
                    "error_message": str(e),
                    "response_body": getattr(e.response, "text", None),
                }
            )
            logger.error(f"HTTP request failedError context: {error_context}")
            if run_manager:
                run_manager.on_tool_error(error=e)
            raise
        except Exception as e:
            error_context.update(
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                }
            )
            logger.error(
                f"Unexpected error during HTTP request. Error context: {error_context}"
            )
            if run_manager:
                run_manager.on_tool_error(error=e)
            raise


class GetTool(HTTPTool):
    """Tool for handling GET requests."""

    method: str = Field(
        default="GET", description="The HTTP method handled by this tool"
    )
    name: str = "get_http_requests"
    description: str = "Handles GET requests to retrieve data from the specified URL. Use this for reading information without modifying any data."
    is_safe: bool = True


class PostTool(HTTPTool):
    """Tool for handling POST requests."""

    method: str = Field(
        default="POST", description="The HTTP method handled by this tool"
    )
    name: str = "post_http_requests"
    description: str = "Handles POST requests to create new resources or submit data to the specified URL. Use this for creating new items or submitting forms."
    is_safe: bool = False


class PutTool(HTTPTool):
    """Tool for handling PUT requests."""

    method: str = Field(
        default="PUT", description="The HTTP method handled by this tool"
    )
    name: str = "put_http_requests"
    description: str = "Handles PUT requests to update or replace existing resources at the specified URL. Use this for completely replacing an existing item."
    is_safe: bool = False


class DeleteTool(HTTPTool):
    """Tool for handling DELETE requests."""

    method: str = Field(
        default="DELETE", description="The HTTP method handled by this tool"
    )
    name: str = "delete_http_requests"
    description: str = "Handles DELETE requests to remove resources at the specified URL. Use this for deleting items or resources."
    is_safe: bool = False


class HeadTool(HTTPTool):
    """Tool for handling HEAD requests."""

    method: str = Field(
        default="HEAD", description="The HTTP method handled by this tool"
    )
    name: str = "head_http_requests"
    description: str = "Handles HEAD requests"
    is_safe: bool = True


class OptionsTool(HTTPTool):
    """Tool for handling OPTIONS requests."""

    method: str = Field(
        default="OPTIONS", description="The HTTP method handled by this tool"
    )
    name: str = "options_http_requests"
    description: str = "Handles OPTIONS requests"
    is_safe: bool = True


class PatchTool(HTTPTool):
    """Tool for handling PATCH requests."""

    method: str = Field(
        default="PATCH", description="The HTTP method handled by this tool"
    )
    name: str = "patch_http_requests"
    description: str = "Handles PATCH requests"
    is_safe: bool = False


class TraceTool(HTTPTool):
    """Tool for handling TRACE requests."""

    method: str = Field(
        default="TRACE", description="The HTTP method handled by this tool"
    )
    name: str = "trace_http_requests"
    description: str = "Handles TRACE requests"
    is_safe: bool = True

    def _run(
        self,
        url: str,
        config: RunnableConfig,
        run_manager: CallbackManagerForToolRun | None = None,
        input_data: dict | None = None,
    ) -> dict:
        """Executes a TRACE HTTP request.

        The TRACE method performs a message loop-back test along the path to the target resource.
        Input data is typically not used with TRACE requests.

        Args:
            url (str): The target URL for the HTTP request.
            config (RunnableConfig): Configuration object containing runtime parameters.
            run_manager (Optional[CallbackManagerForToolRun], optional): Manager for handling callbacks during the tool run. Defaults to None.
            input_data (Optional[dict], optional): Not used in TRACE requests. Defaults to None.

        Returns:
            dict: The JSON response from the HTTP request.

        Raises:
            requests.HTTPError: If the HTTP request returns an unsuccessful status code.
        """
        headers = {}
        if config and "auth_token" in config.get("configurable", {}):
            headers["Authorization"] = f"Bearer {config['configurable']['auth_token']}"

        response = requests.request(self.method, url, headers=headers)
        response.raise_for_status()
        return response.json()


class HttpRequestsToolkit(BaseToolkit):
    """Toolkit containing various HTTP tools for different request methods."""

    get_tool: GetTool = Field(default_factory=GetTool)
    post_tool: PostTool = Field(default_factory=PostTool)
    put_tool: PutTool = Field(default_factory=PutTool)
    delete_tool: DeleteTool = Field(default_factory=DeleteTool)
    head_tool: HeadTool = Field(default_factory=HeadTool)
    options_tool: OptionsTool = Field(default_factory=OptionsTool)
    patch_tool: PatchTool = Field(default_factory=PatchTool)
    trace_tool: TraceTool = Field(default_factory=TraceTool)

    def get_tools(self):
        """Returns a list of all HTTP tools in the toolkit.

        Returns:
            list: A list containing instances of all HTTP tools.
        """
        return [
            self.get_tool,
            self.post_tool,
            self.put_tool,
            self.delete_tool,
            self.head_tool,
            self.options_tool,
            self.patch_tool,
            self.trace_tool,
        ]

    def is_safe_tool(self, tool_name: str) -> bool:
        """
        Returns True if the tool with the given name is marked as safe.
        """
        for tool in self.get_tools():
            if tool.name == tool_name:
                return tool.is_safe
        return False
