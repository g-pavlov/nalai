import logging
import traceback
from datetime import UTC, datetime

import requests
from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseToolkit, StructuredTool
from pydantic import BaseModel, Field

from ..config import settings

logger = logging.getLogger(__name__)


class HTTPToolArgs(BaseModel):
    """Base schema for HTTP tool arguments."""

    url: str = Field(..., description="The target URL for the HTTP request")
    input_data: dict | None = Field(
        default=None,
        description="Data to be sent with the request (query parameters for GET, JSON payload for POST/PUT/PATCH)",
    )


def http_request_tool(method: str, is_safe: bool, name: str, description: str):
    def _http_request(
        url: str,
        input_data: dict | None = None,
        config: RunnableConfig | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict:
        logger.debug("sending HTTP request: %s %s", method, url)
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
        headers = {**llm_supplied_headers, **internal_headers}
        is_body_method = method in ["POST", "PUT", "PATCH"]
        request_kwargs = {
            "headers": headers,
            "params": input_data if not is_body_method else None,
            "json": input_data if is_body_method else None,
        }
        error_context = {
            "tool_name": name,
            "method": method,
            "url": url,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_context": {
                "email": configurable.get("user_email", "unknown"),
                "org_unit_id": configurable.get("org_unit_id", "unknown"),
            },
            "thread_id": configurable.get("thread_id", "unknown"),
        }
        # Check if URL is allowed by checking against all allowed URLs
        allowed_urls = settings.api_calls_allowed_urls_list
        url_allowed = any(url.startswith(allowed_url) for allowed_url in allowed_urls)

        if not url_allowed:
            error = ValueError(
                f"HTTP requests are restricted to {', '.join(allowed_urls)}. Attempted to access: {url}"
            )
            error_context.update({"error_message": str(error)})
            logger.error(
                f"Unexpected error during HTTP request. Error context: {error_context}"
            )
            if run_manager:
                run_manager.on_tool_error(error)
            raise error
        try:
            response = requests.request(method, url, **request_kwargs)
            response.raise_for_status()
            logger.info(
                f"Received HTTP response: {method} {url}, status code: {response.status_code}"
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

    return StructuredTool.from_function(
        func=_http_request,
        name=name,
        description=description,
        args_schema=HTTPToolArgs,
        return_type=dict,
    )


class HttpRequestsToolkit(BaseToolkit):
    """Toolkit containing various HTTP tools for different request methods."""

    get_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="GET",
            is_safe=True,
            name="get_http_requests",
            description="Handles GET requests to retrieve data from the specified URL. Use this for reading information without modifying any data.",
        )
    )
    post_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="POST",
            is_safe=False,
            name="post_http_requests",
            description="Handles POST requests to create new resources or submit data to the specified URL. Use this for creating new items or submitting forms.",
        )
    )
    put_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="PUT",
            is_safe=False,
            name="put_http_requests",
            description="Handles PUT requests to update or replace existing resources at the specified URL. Use this for completely replacing an existing item.",
        )
    )
    delete_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="DELETE",
            is_safe=False,
            name="delete_http_requests",
            description="Handles DELETE requests to remove resources at the specified URL. Use this for deleting items or resources.",
        )
    )
    head_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="HEAD",
            is_safe=True,
            name="head_http_requests",
            description="Handles HEAD requests",
        )
    )
    options_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="OPTIONS",
            is_safe=True,
            name="options_http_requests",
            description="Handles OPTIONS requests",
        )
    )
    patch_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="PATCH",
            is_safe=False,
            name="patch_http_requests",
            description="Handles PATCH requests",
        )
    )
    trace_tool: StructuredTool = Field(
        default_factory=lambda: http_request_tool(
            method="TRACE",
            is_safe=True,
            name="trace_http_requests",
            description="Handles TRACE requests",
        )
    )

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
        # Define safe tools explicitly since the is_safe attribute is not set on StructuredTool
        safe_tools = {
            "get_http_requests",
            "head_http_requests",
            "options_http_requests",
            "trace_http_requests",
        }
        return tool_name in safe_tools
