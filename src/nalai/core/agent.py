"""
Core API Agent implementation.

Contains the main APIAgent class that orchestrates AI-powered
API interactions with intelligent context management, tool selection,
and human-in-the-loop review capabilities.
"""

import json
import logging
import traceback
from typing import Any, Literal, cast

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END

from ..config import settings
from ..prompts.prompts import format_template_with_variables, load_prompt_template
from ..services.cache_service import get_cache_service
from ..services.model_service import ModelService
from ..tools.http_requests import HttpRequestsToolkit
from ..utils.chat_history import compress_conversation_history_if_needed
from .constants import (
    NODE_CALL_API,
    NODE_CALL_MODEL,
    NODE_HUMAN_REVIEW,
    NODE_LOAD_API_SPECS,
    NODE_LOAD_API_SUMMARIES,
    NODE_SELECT_RELEVANT_APIS,
)
from .schemas import AgentState, SelectedApis

logger = logging.getLogger(__name__)


class APIAgent:
    """AI-powered API agent with intelligent context management.
    Orchestrates API interactions by:
    - Selecting relevant APIs based on conversation context
    - Managing conversation history with intelligent compression
    - Supporting human-in-the-loop review workflows
    - Providing structured responses with proper error handling
    """

    def __init__(self):
        """Initialize the API assistant with required resources.
        Sets up HTTP toolkit for API interactions.
        """
        self.http_toolkit = HttpRequestsToolkit()

    @staticmethod
    def create_prompt_and_model(config: RunnableConfig, variant: str, **kwargs: Any):
        """Create prompt template and model from configuration.
        Args:
            config: Runtime configuration containing model settings
            variant: Prompt variant ('call_model' or 'select_relevant_apis')
            **kwargs: Additional model initialization parameters
        Returns:
            tuple: (prompt_template, model) for AI interaction
        """
        model_id = ModelService.get_model_id_from_config(config)
        system_prompt_str = load_prompt_template(model_id, variant)
        # Always format the system prompt, even if no variables are present
        # Use the first allowed URL as the primary example, but mention all allowed URLs
        all_urls = settings.api_calls_allowed_urls_list
        primary_url = all_urls[0] if all_urls else "example.com"
        system_prompt_str = format_template_with_variables(
            system_prompt_str, base_url=primary_url
        )
        # Add information about all allowed URLs if there are multiple
        if len(all_urls) > 1:
            system_prompt_str += f"\n\nNote: You can also make requests to these additional URLs: {', '.join(all_urls[1:])}"
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt_str),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        model = ModelService.get_model_from_config(config, **kwargs)
        return prompt, model

    def select_relevant_apis(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, list[AIMessage]]:
        """
        Selects the most relevant APIs based on the conversation history and summaries.
        """

        # Disable streaming due to issue with ChatBedrockConverse lib. https://github.com/langchain-ai/langchain/issues/27962
        # Even calling it with invoke fails when the graph is streamed with .astream_events(...)
        prompt, model = APIAgent.create_prompt_and_model(
            config, NODE_SELECT_RELEVANT_APIS, disable_streaming=True
        )
        model = model.with_structured_output(SelectedApis)

        conversation_messages = state.get("messages", [])
        api_summaries_text = "\n".join(
            f"- title: {item.get('title', '')}\n  description: {item.get('description', '')}\n  methods: {', '.join(item.get('methods', []))}\n  version:  {item.get('version', '1.0')}\n"
            for item in state.get("api_summaries", [])
        )
        prompt_value = prompt.invoke(
            {"messages": conversation_messages, "api_summaries": api_summaries_text}
        )

        response = cast(AIMessage, model.invoke(prompt_value, config))

        state["selected_apis"] = response.selected_apis
        # Don't add the JSON message to conversation history - it's internal metadata
        return {"messages": [], **state}

    def check_cache_with_similarity(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, list[AIMessage]]:
        """
        Check cache for exact or similar responses before proceeding with the workflow.
        """
        conversation_messages = state.get("messages", [])

        # Check if caching is enabled globally
        if not settings.cache_enabled:
            logger.debug("Caching disabled globally - proceeding to load API summaries")
            return {"messages": conversation_messages, "cache_miss": True}

        # Check if cache is disabled for this specific request
        cache_disabled = False
        if config and "configurable" in config:
            cache_disabled = config["configurable"].get("cache_disabled", False)
        
        if cache_disabled:
            logger.debug("Cache disabled for this request - proceeding to load API summaries")
            return {"messages": conversation_messages, "cache_miss": True}

        if not conversation_messages:
            logger.debug("No messages available, proceeding to load API summaries")
            return {"messages": conversation_messages, "cache_miss": True}

        logger.debug(f"Checking cache for {len(conversation_messages)} messages")

        # Extract user ID from config for cache isolation
        user_id = "anonymous"
        if config and "configurable" in config:
            user_id = config["configurable"].get("user_id", "anonymous")

        # Check cache service
        cache_service = get_cache_service()

        # 1. Exact match first
        cached_result = cache_service.get(conversation_messages, user_id)
        if cached_result:
            cached_response, cached_tool_calls = cached_result
            logger.info("Cache hit (exact match) for messages")

            # Create AIMessage from cached response
            response = AIMessage(content=cached_response)
            if cached_tool_calls:
                response.tool_calls = cached_tool_calls

            conversation_messages = conversation_messages + [response]
            result = {"messages": conversation_messages, "cache_hit": True}
            logger.debug(f"Returning exact cache hit result: {result}")
            return result

        # 2. Similarity search (for the last human message) - only if enabled
        if settings.cache_similarity_enabled:
            last_human_message = None
            for message in reversed(conversation_messages):
                if hasattr(message, "content") and message.content:
                    last_human_message = message.content
                    break

            if last_human_message:
                similar_responses = cache_service.find_similar_cached_responses(
                    last_human_message, user_id, settings.cache_similarity_threshold
                )

                if similar_responses:
                    best_content, best_response, best_tool_calls, similarity_score = (
                        similar_responses[0]
                    )
                    logger.info(
                        f"Cache hit (similarity) for message matches '{best_content}' (score: {similarity_score:.2f})"
                    )

                    # Create AIMessage from cached response
                    response = AIMessage(content=best_response)
                    if best_tool_calls:
                        response.tool_calls = best_tool_calls

                    conversation_messages = conversation_messages + [response]
                    result = {"messages": conversation_messages, "cache_hit": True}
                    logger.debug(f"Returning cache hit result: {result}")
                    return result

        # 3. No cache hit, proceed to load API summaries
        logger.debug("No cache hit, proceeding to load API summaries")
        result = {"messages": conversation_messages, "cache_miss": True}
        logger.debug(f"Returning cache miss result: {result}")
        return result

    def determine_cache_action(
        self, state: AgentState
    ) -> Literal[NODE_LOAD_API_SUMMARIES, NODE_CALL_MODEL]:
        """
        Determines the next action after cache check.
        """
        cache_hit = state.get("cache_hit")
        cache_miss = state.get("cache_miss")
        logger.debug(
            f"determine_cache_action: cache_hit={cache_hit}, cache_miss={cache_miss}"
        )

        if cache_hit:
            logger.debug("Cache hit - routing to model call for single streaming event")
            return NODE_CALL_MODEL
        else:
            logger.debug("Cache miss - proceeding to load API summaries")
            return NODE_LOAD_API_SUMMARIES

    def determine_next_step(
        self, state: AgentState
    ) -> Literal["load_api_specs", "call_model"]:
        """
        Determines the next workflow step based on whether APIs were selected.
        """
        return (
            NODE_LOAD_API_SPECS if state.get("selected_apis", None) else NODE_CALL_MODEL
        )

    def generate_model_response(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, list[AIMessage]]:
        """
        Generates a response using the AI model with appropriate context and tools.
        """
        conversation_messages = state.get("messages", [])

        # Check if this is a cache hit - if so, create a mock model that returns cached content
        cache_hit = state.get("cache_hit")
        if cache_hit:
            logger.debug(
                "Cache hit detected in generate_model_response - creating single streaming event"
            )
            # Find the last AI message (which should be the cached response)
            last_ai_message = None
            for message in reversed(conversation_messages):
                if isinstance(message, AIMessage):
                    last_ai_message = message
                    break

            if last_ai_message:
                # For cache hits, we need to create a mock model that returns the cached content
                # This will generate a single streaming event with the full content
                cached_content = last_ai_message.content
                cached_tool_calls = getattr(last_ai_message, "tool_calls", None)

                # Create a mock model that returns the cached content as a single chunk
                from langchain_core.language_models import BaseChatModel
                from langchain_core.outputs import ChatGeneration, ChatResult

                class MockCachedModel(BaseChatModel):
                    def __init__(self, cached_content: str, cached_tool_calls=None):
                        super().__init__()
                        self._cached_content = cached_content
                        self._cached_tool_calls = cached_tool_calls

                    def _generate(
                        self, messages, stop=None, run_manager=None, **kwargs
                    ):
                        # Create a mock response with the cached content
                        response = AIMessage(content=self._cached_content)
                        if self._cached_tool_calls:
                            response.tool_calls = self._cached_tool_calls

                        return ChatResult(
                            generations=[ChatGeneration(message=response)]
                        )

                    @property
                    def _llm_type(self) -> str:
                        return "mock_cached"

                # Use the mock model to generate the response
                mock_model = MockCachedModel(cached_content, cached_tool_calls)
                response = cast(
                    AIMessage, mock_model.invoke(conversation_messages, config)
                )

                # Add the response to the conversation
                conversation_messages = conversation_messages + [response]

                logger.debug(
                    f"Created single streaming event for cache hit with content: {cached_content[:100]}..."
                )
                return {"messages": conversation_messages}
            else:
                logger.warning("Cache hit but no AI message found")

        # Normal flow for cache misses
        prompt_template, model = APIAgent.create_prompt_and_model(
            config, NODE_CALL_MODEL
        )

        api_specs = state.get("api_specs", "")
        api_specs_json = json.dumps(api_specs) if api_specs else ""

        compressed_messages = None
        try:
            conversation_messages, compressed_messages = (
                compress_conversation_history_if_needed(
                    conversation_messages,
                    model,
                    settings.chat_thread_compression_trigger_percentage,
                )
            )
        except ValueError as error:
            logger.error("failed to compress message history: %s\n", error)
        except Exception:
            logger.error("uncaught exception: %s", traceback.format_exc())

        prompt_value = prompt_template.invoke(
            {"messages": conversation_messages, "api_specs": api_specs_json}
        )

        if settings.api_calls_enabled is True:
            model = model.bind_tools(self.http_toolkit.get_tools())
        response = cast(AIMessage, model.invoke(prompt_value, config))

        # Cache the final response for future use
        if settings.cache_enabled:
            # Check if cache is disabled for this specific request
            cache_disabled = False
            if config and "configurable" in config:
                cache_disabled = config["configurable"].get("cache_disabled", False)
            
            if not cache_disabled:
                # Don't cache responses with empty content (especially tool-only responses)
                if response.content and response.content.strip():
                    cache_service = get_cache_service()

                    # Extract user ID from config for cache isolation
                    user_id = "anonymous"
                    if config and "configurable" in config:
                        user_id = config["configurable"].get("user_id", "anonymous")

                    cache_service.set(
                        messages=conversation_messages,
                        response=response.content,
                        tool_calls=response.tool_calls,
                        user_id=user_id,
                    )
                    logger.debug(
                        f"Cached response for {len(conversation_messages)} messages (user: {user_id})"
                    )
                else:
                    logger.debug("Skipping cache for empty content response")
            else:
                logger.debug("Cache disabled for this request - skipping cache storage")

        conversation_messages = conversation_messages + [response]
        if compressed_messages:
            conversation_messages = conversation_messages + compressed_messages

        return {"messages": conversation_messages}

    def determine_workflow_action(
        self, state: AgentState
    ) -> Literal[END, "human_review", "call_api"]:
        """
        Determines the next workflow action based on the model's output and tool calls.
        """
        for message in reversed(state["messages"]):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            raise ValueError("No AIMessage found in conversation history")

        if not last_ai_message.tool_calls:
            return END

        tool_call_name = last_ai_message.tool_calls[0]["name"]
        toolkit = self.http_toolkit

        if settings.api_calls_enabled is True and tool_call_name in (
            tool.name for tool in toolkit.get_tools()
        ):
            if toolkit.is_safe_tool(tool_call_name):
                return NODE_CALL_API
            else:
                return NODE_HUMAN_REVIEW
        logger.warning(f"Unrecognized tool name: {tool_call_name}")
        return END
