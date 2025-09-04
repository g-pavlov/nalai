from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class InputSchema(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class AgentState(InputSchema):
    api_specs: list[dict[str, Any]] | None
    api_summaries: list[dict[str, Any]] | None
    selected_apis: dict[str, str] | None
    cache_hit: bool | None
    cache_miss: bool | None


class OutputSchema(InputSchema):
    pass
