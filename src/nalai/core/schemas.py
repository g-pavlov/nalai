from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field


class InputSchema(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class AgentState(InputSchema):
    api_specs: list[dict[str, Any]] | None
    api_summaries: list[dict[str, Any]] | None
    selected_apis: dict[str, str] | None
    cache_hit: bool | None
    cache_miss: bool | None


class ModelConfig(BaseModel):
    name: str
    platform: str


# Add this default instance
DEFAULT_MODEL_CONFIG = ModelConfig(name="gpt-4.1", platform="openai")


class ConfigSchema(BaseModel):
    model: ModelConfig = Field(
        default=DEFAULT_MODEL_CONFIG,
        description=(
            "Configuration for the model to be used. "
            f"Defaults to {{'name': {DEFAULT_MODEL_CONFIG.name}, 'platform': {DEFAULT_MODEL_CONFIG.platform} }} ."
        ),
    )


class OutputSchema(InputSchema):
    pass


class SelectApi(BaseModel):
    """A selected API"""

    api_title: str = Field(description="The title of a selected API")
    api_version: str = Field(description="The version of a selected API")


class SelectedApis(BaseModel):
    """List of APIs selected by the LLM"""

    selected_apis: list[SelectApi] = Field(
        default_factory=list,
        description="List of selected APIs. May be empty if no relevant APIs are found.",
    )
