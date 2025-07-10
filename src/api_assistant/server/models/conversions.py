"""
Message conversion utilities for API Assistant server.

This module contains utilities for converting between API format and LangChain format:
- validate_langchain_messages: Validate LangChain message lists
- convert_api_messages_to_langchain: Convert API format to LangChain
- convert_langchain_messages_to_api: Convert LangChain to API format
"""

from langchain_core.messages import BaseMessage, HumanMessage

from .input import MessageInput


def validate_langchain_messages(messages: list[BaseMessage]) -> None:
    """Validate a list of LangChain messages."""
    if not messages:
        raise ValueError("Messages list cannot be empty")

    # Ensure at least one human message
    human_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
    if not human_messages:
        raise ValueError("At least one human message is required")

    # Validate message content
    for msg in messages:
        if not msg.content or not str(msg.content).strip():
            raise ValueError("Message content cannot be empty")
        if len(str(msg.content)) > 10000:  # 10KB limit per message
            raise ValueError("Message content too long (max 10KB)")


def convert_api_messages_to_langchain(
    api_messages: list[MessageInput],
) -> list[BaseMessage]:
    """Convert API message format to LangChain messages."""
    return [msg.to_langchain_message() for msg in api_messages]


def convert_langchain_messages_to_api(
    langchain_messages: list[BaseMessage],
) -> list[MessageInput]:
    """Convert LangChain messages to API message format."""
    return [MessageInput.from_langchain_message(msg) for msg in langchain_messages]
