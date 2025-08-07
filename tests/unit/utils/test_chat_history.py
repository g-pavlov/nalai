"""
Unit tests for chat history utilities.

Tests cover token counting, conversation trimming, conversation compression,
and message summarization functionality.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import yaml
from langchain_core.messages import AIMessage, HumanMessage

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.utils.chat_history import (
    compress_conversation_history_if_needed,
    get_token_ids_simplistic,
    get_token_ids_with_tiktoken,
    summarize_conversation,
    trim_conversation_history_if_needed,
)


@pytest.fixture
def test_data():
    """Load test data from YAML file."""
    test_data_path = os.path.join(
        os.path.dirname(__file__), "..", "test_data", "chat_history_test_cases.yaml"
    )
    with open(test_data_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_model():
    """Create a mock language model for testing."""
    model = MagicMock()
    model.metadata = {"context_window": 1000, "messages_token_count_supported": True}
    model.get_num_tokens_from_messages.return_value = 100
    return model


class TestTokenCounting:
    """Test suite for token counting functionality."""

    @pytest.mark.parametrize("test_case", ["simple_text", "complex_text"])
    def test_get_token_ids_with_tiktoken(self, test_case, test_data):
        """Test token counting with tiktoken."""
        from nalai.utils import chat_history

        chat_history.get_tiktoken_encoder.cache_clear()
        case_data = next(
            c for c in test_data["token_counting"] if c["name"] == test_case
        )

        with patch("nalai.utils.chat_history.tiktoken") as mock_tiktoken:
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [0] * case_data["expected"][
                "token_count"
            ]
            mock_tiktoken.encoding_for_model.return_value = mock_encoding

            result = get_token_ids_with_tiktoken(
                case_data["input"]["text"], case_data["input"]["model_name"]
            )

            assert len(result) == case_data["expected"]["token_count"]
            mock_tiktoken.encoding_for_model.assert_called_once_with(
                case_data["input"]["model_name"]
            )

    def test_get_token_ids_simplistic(self, test_data):
        """Test simplistic token counting."""
        case_data = next(
            c for c in test_data["token_counting"] if c["name"] == "simplistic_counting"
        )

        result = get_token_ids_simplistic(case_data["input"]["text"])
        assert len(result) == case_data["expected"]["token_count"]

    def test_tiktoken_encoder_caching(self):
        """Test that tiktoken encoder is cached."""
        from nalai.utils import chat_history

        chat_history.get_tiktoken_encoder.cache_clear()
        with patch("nalai.utils.chat_history.tiktoken") as mock_tiktoken:
            mock_encoding = MagicMock()
            mock_tiktoken.encoding_for_model.return_value = mock_encoding

            # Call twice with same model
            get_token_ids_with_tiktoken("test", "gpt-2")
            get_token_ids_with_tiktoken("test2", "gpt-2")

            # Should only be called once due to caching
            mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-2")


class TestConversationTrimming:
    """Test suite for conversation trimming functionality."""

    @pytest.mark.parametrize(
        "test_case", ["within_limits", "exceeds_limits", "preserves_system_messages"]
    )
    def test_trim_conversation_history_if_needed(
        self, test_case, test_data, mock_model
    ):
        """Test conversation trimming functionality."""
        case_data = next(
            c for c in test_data["conversation_trimming"] if c["name"] == test_case
        )

        # Create messages from test data
        messages = []
        for msg_data in case_data["input"]["messages"]:
            if msg_data["content"].startswith("System"):
                messages.append(HumanMessage(content=msg_data["content"]))
            else:
                messages.append(HumanMessage(content=msg_data["content"]))

        # Setup model metadata
        mock_model.metadata["context_window"] = case_data["input"]["context_window"]

        # Calculate expected token count based on whether trimming should occur
        if case_data["expected"]["should_trim"]:
            mock_model.get_num_tokens_from_messages.return_value = (
                case_data["input"]["context_window"] + 100
            )
        else:
            mock_model.get_num_tokens_from_messages.return_value = (
                case_data["input"]["context_window"] - 100
            )

        with patch("nalai.utils.chat_history.trim_messages") as mock_trim:
            if case_data["expected"]["should_trim"]:
                if test_case == "preserves_system_messages":
                    mock_trim.return_value = messages[:2]
                else:
                    mock_trim.return_value = messages[:1]  # Return trimmed messages
            else:
                mock_trim.return_value = messages  # Return original messages

            result = trim_conversation_history_if_needed(
                messages, mock_model, case_data["input"]["trim_trigger_percentage"]
            )

            if case_data["expected"]["should_trim"]:
                mock_trim.assert_called_once()
                assert len(result) == case_data["expected"]["message_count"]
            else:
                mock_trim.assert_not_called()
                assert result == messages

    def test_trim_conversation_with_custom_token_counter(self, mock_model):
        """Test conversation trimming with custom token counter."""
        messages = [
            HumanMessage(content="Message 1"),
            HumanMessage(content="Message 2"),
            HumanMessage(content="Message 3"),
        ]

        def custom_token_counter(text):
            return [0] * 2000  # Exceeds threshold

        mock_model.metadata["context_window"] = 1000
        mock_model.get_num_tokens_from_messages.return_value = 2000

        with patch("nalai.utils.chat_history.trim_messages") as mock_trim:
            mock_trim.return_value = messages[:1]

            result = trim_conversation_history_if_needed(
                messages, mock_model, custom_get_token_ids=custom_token_counter
            )

            mock_trim.assert_called_once()
            assert len(result) == 1

    def test_trim_conversation_preserves_system_messages(self, mock_model):
        """Test that system messages are preserved during trimming."""
        messages = [
            HumanMessage(content="System message"),
            HumanMessage(content="Very long message repeated many times"),
            HumanMessage(content="Final message"),
        ]

        mock_model.metadata["context_window"] = 1000
        mock_model.get_num_tokens_from_messages.return_value = 1200  # Exceeds threshold

        with patch("nalai.utils.chat_history.trim_messages") as mock_trim:
            mock_trim.return_value = messages[:1]  # Keep only first message

            trim_conversation_history_if_needed(messages, mock_model)

            mock_trim.assert_called_once()
            # Verify trim_messages was called with include_system=True
            call_args = mock_trim.call_args
            assert call_args[1]["include_system"] is True


class TestConversationCompression:
    """Test suite for conversation compression functionality."""

    @pytest.mark.parametrize(
        "test_case", ["within_limits", "exceeds_limits", "no_human_message"]
    )
    def test_compress_conversation_history_if_needed(
        self, test_case, test_data, mock_model
    ):
        """Test conversation compression functionality."""
        case_data = next(
            c for c in test_data["conversation_compression"] if c["name"] == test_case
        )

        # Create messages from test data
        messages = []
        for msg_data in case_data["input"]["messages"]:
            if "human" in msg_data["content"].lower():
                messages.append(HumanMessage(content=msg_data["content"]))
            else:
                messages.append(AIMessage(content=msg_data["content"]))

        # Setup model metadata
        mock_model.metadata["context_window"] = case_data["input"]["context_window"]

        # Calculate expected token count based on whether compression should occur
        if case_data["expected"]["should_compress"]:
            mock_model.get_num_tokens_from_messages.return_value = (
                case_data["input"]["context_window"] + 100
            )
        else:
            mock_model.get_num_tokens_from_messages.return_value = (
                case_data["input"]["context_window"] - 100
            )

        if case_data["expected"].get("should_raise_error"):
            with pytest.raises(ValueError, match="No HumanMessage found"):
                compress_conversation_history_if_needed(
                    messages,
                    mock_model,
                    case_data["input"]["compression_trigger_percentage"],
                )
        else:
            with patch(
                "nalai.utils.chat_history.summarize_conversation"
            ) as mock_summarize:
                if case_data["expected"]["should_compress"]:
                    summary_message = AIMessage(content="Summary of conversation")
                    mock_summarize.return_value = summary_message

                result, removed_messages = compress_conversation_history_if_needed(
                    messages,
                    mock_model,
                    case_data["input"]["compression_trigger_percentage"],
                )

                if case_data["expected"]["should_compress"]:
                    mock_summarize.assert_called_once()
                    assert len(result) == case_data["expected"]["message_count"]
                    assert result[0] == summary_message
                    assert isinstance(result[1], HumanMessage)
                    assert removed_messages is not None
                    assert len(removed_messages) == len(messages)
                else:
                    mock_summarize.assert_not_called()
                    assert result == messages
                    assert removed_messages is None

    def test_compress_conversation_without_token_count_support(self, mock_model):
        """Test compression when model doesn't support token counting."""
        messages = [HumanMessage(content=f"Message {i}") for i in range(10)]

        mock_model.metadata["context_window"] = 1000
        mock_model.metadata["messages_token_count_supported"] = False

        def custom_token_counter(text):
            return [0] * 1000  # High token count for each message

        with patch("nalai.utils.chat_history.summarize_conversation") as mock_summarize:
            summary_message = AIMessage(content="Summary")
            mock_summarize.return_value = summary_message

            result, removed_messages = compress_conversation_history_if_needed(
                messages, mock_model, custom_get_token_ids=custom_token_counter
            )

            mock_summarize.assert_called_once()
            assert len(result) == 2
            assert result[0] == summary_message
            assert isinstance(result[1], HumanMessage)

    def test_compress_conversation_custom_token_counter(self, mock_model):
        """Test compression with custom token counter."""
        messages = [HumanMessage(content=f"Message {i}") for i in range(10)]

        def custom_token_counter(text):
            return [0] * 1000  # High token count for each message

        mock_model.metadata["context_window"] = 1000
        mock_model.metadata["messages_token_count_supported"] = False

        with patch("nalai.utils.chat_history.summarize_conversation") as mock_summarize:
            summary_message = AIMessage(content="Summary")
            mock_summarize.return_value = summary_message

            result, removed_messages = compress_conversation_history_if_needed(
                messages, mock_model, custom_get_token_ids=custom_token_counter
            )

            mock_summarize.assert_called_once()
            assert len(result) == 2


class TestConversationSummarization:
    """Test suite for conversation summarization functionality."""

    def test_summarize_conversation(self, mock_model):
        """Test conversation summarization."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm doing well, thanks!"),
        ]

        max_summary_tokens = 50
        expected_summary = AIMessage(content="Summary of conversation")
        mock_model.invoke.return_value = expected_summary

        result = summarize_conversation(messages, mock_model, max_summary_tokens)

        # The summary prompt is appended to messages[:-1], so the call_args should be len(messages)
        call_args = mock_model.invoke.call_args[0][0]
        assert len(call_args) == len(messages)
        assert isinstance(result, AIMessage)
        assert result == expected_summary

    def test_summarize_conversation_empty_messages(self, mock_model):
        """Test summarization with empty messages list."""
        messages = []
        max_summary_tokens = 50
        mock_model.invoke.return_value = AIMessage(content="Summary")
        result = summarize_conversation(messages, mock_model, max_summary_tokens)
        assert isinstance(result, AIMessage)
