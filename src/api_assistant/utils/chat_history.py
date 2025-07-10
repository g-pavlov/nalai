from collections.abc import Callable
from functools import cache

import tiktoken
from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    trim_messages,
)


@cache  # Cache encoding lookup per model
def get_tiktoken_encoder(model_name: str):
    """Get cached tiktoken encoder for model.
    Args:
        model_name: Model name for tokenization
    Returns:
        tiktoken.Encoding: Encoder instance for the model
    """
    return tiktoken.encoding_for_model(model_name)


def get_token_ids_with_tiktoken(text: str, model_name: str = "gpt-2") -> list[int]:
    """Get token IDs using tiktoken for accurate tokenization.
    Uses tiktoken library for precise token counting based on model-specific
    tokenization rules.
    Args:
        text: Text to tokenize
        model_name: Model name for tokenization rules (default: "gpt-2")
    Returns:
        list[int]: Token IDs for the input text
    """
    encoding = get_tiktoken_encoder(model_name)
    return encoding.encode(text)


def get_token_ids_simplistic(text: str) -> list[int]:
    """Get approximate token count prioritizing speed over accuracy.
    Uses simple word splitting with 1.3x coefficient to account for
    punctuation and non-word tokens. Fast but less accurate than tiktoken.
    Args:
        text: Text to estimate token count for
    Returns:
        list[int]: Approximate token count as list of zeros
    """
    return [0] * int(len(text.split()) * 1.3)


def trim_conversation_history_if_needed(
    messages: list[BaseMessage],
    model: BaseChatModel,
    trim_trigger_percentage: int | None = 95,
    custom_get_token_ids: Callable[[str], list[int]] | None = get_token_ids_simplistic,
) -> list[BaseMessage]:
    """Trim conversation history when token count exceeds threshold.
    Removes older messages to stay within context window limits while
    preserving recent conversation context and system messages.
    Args:
        messages: List of conversation messages
        model: Language model with context window metadata
        trim_trigger_percentage: Context window percentage that triggers trimming
        custom_get_token_ids: Custom token counting function
    Returns:
        list[BaseMessage]: Trimmed message list
    """
    model_context_window_size = model.metadata.get(
        "context_window",
        32000,  # DEFAULT_MODEL_CONTEXT_WINDOW_SIZE
    )
    trim_threshold_tokens = int(
        model_context_window_size * trim_trigger_percentage / 100
    )
    model.custom_get_token_ids = custom_get_token_ids
    token_count = model.get_num_tokens_from_messages(messages)

    if token_count > trim_threshold_tokens:
        return trim_messages(
            messages,
            token_counter=model.get_num_tokens_from_messages,
            strategy="last",
            max_tokens=int(trim_threshold_tokens / 5),
            start_on="human",
            end_on=("human", "tool"),
            include_system=True,
        )

    return messages


def compress_conversation_history_if_needed(
    messages: list[BaseMessage],
    model: BaseChatModel,
    compression_trigger_percentage: int = 95,
    custom_get_token_ids: Callable[[str], list[int]] | None = get_token_ids_simplistic,
) -> tuple[list[BaseMessage], list[RemoveMessage] | None]:
    """Compress conversation history by summarizing older messages.
    When token count exceeds threshold, summarizes conversation history
    into a single message while preserving the most recent human message
    for context continuity.
    Args:
        messages: List of conversation messages
        model: Language model for summarization
        compression_trigger_percentage: Context window percentage that triggers compression
        custom_get_token_ids: Custom token counting function
    Returns:
        tuple: (updated_messages, removed_messages) where removed_messages may be None
    """
    model_context_window_size = model.metadata.get(
        "context_window",
        32000,  # DEFAULT_MODEL_CONTEXT_WINDOW_SIZE
    )
    model.custom_get_token_ids = custom_get_token_ids
    compression_threshold = int(
        model_context_window_size * compression_trigger_percentage / 100
    )
    if model.metadata.get("messages_token_count_supported", False):
        token_count = model.get_num_tokens_from_messages(messages)
    else:
        token_count = sum(
            len(custom_get_token_ids(message.content)) for message in messages
        )

    if token_count > compression_threshold:
        max_summary_tokens = int(
            model_context_window_size * 5 / 100
        )  # 5% of model context size
        summary_message = summarize_conversation(messages, model, max_summary_tokens)

        last_human_message = next(
            (
                message
                for message in reversed(messages)
                if isinstance(message, HumanMessage)
            ),
            None,
        )
        if last_human_message is None:
            raise ValueError(
                "No HumanMessage found in the list. Expected at least one."
            )

        # Retain the last human message for context
        human_message = HumanMessage(content=last_human_message.content)
        # Mark all previous messages for removal
        remove_messages = [RemoveMessage(id=message.id) for message in messages]

        return [summary_message, human_message], remove_messages

    return messages, None


def summarize_conversation(
    messages: list[BaseMessage], model: BaseChatModel, max_summary_tokens: int
) -> BaseMessage:
    """Summarize conversation into a single message.
    Uses the language model to create a concise summary of conversation
    history within the specified token limit.
    Args:
        messages: List of messages to summarize
        model: Language model for summarization
        max_summary_tokens: Maximum tokens allowed for summary
    Returns:
        BaseMessage: Generated summary message
    """
    summary_prompt = (
        f"Summarize the conversation into a single message of at most {max_summary_tokens} tokens. "
        "Retain all important details. Do not add additional text explaining your task."
    )

    message_history = messages[:-1]  # Exclude the most recent message
    return model.invoke(message_history + [HumanMessage(content=summary_prompt)])
