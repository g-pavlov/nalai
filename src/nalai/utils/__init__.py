"""
Utility functions for API Assistant.

This module contains utility functions for logging, formatting,
and other common operations.
"""

from .chat_history import (
    compress_conversation_history_if_needed,
    get_token_ids_simplistic,
    get_token_ids_with_tiktoken,
    summarize_conversation,
    trim_conversation_history_if_needed,
)
from .cli_print import stream_events_with_interruptions
from .logging import setup_logging

__all__ = [
    "get_token_ids_simplistic",
    "get_token_ids_with_tiktoken",
    "compress_conversation_history_if_needed",
    "trim_conversation_history_if_needed",
    "summarize_conversation",
    "stream_events_with_interruptions",
    "setup_logging",
]
