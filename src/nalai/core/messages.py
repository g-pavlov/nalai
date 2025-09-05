"""
This module defines the request and response schemas for the agent message exchange API.
"""

import logging
import re
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from langchain_core.messages.content_blocks import is_data_content_block
from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.id_generator import generate_message_id, validate_domain_id_format
from .internal.base_models import StrictModelMixin

logger = logging.getLogger("nalai")


# ===== Content Block Types =====
# Using content block system with hybrid validation
#
# Content blocks support the following types:
# - Text blocks: {"type": "text", "text": "content"}
# - Image blocks: {"type": "image", "source_type": "url|base64", "url": "...", "mime_type": "..."}
# - Audio blocks: {"type": "audio", "source_type": "url|base64", "url": "...", "mime_type": "..."}
# - File blocks: {"type": "file", "source_type": "url|base64", "url": "...", "name": "...", "size": 123}


# ===== Input Message Types =====
class BaseInputMessage(BaseModel, StrictModelMixin):
    """Base input message structure.

    Examples:
        # Simple text message
        message = HumanInputMessage(content="Hello, world!")

        # Rich content with multiple blocks
        message = HumanInputMessage(content=[
            {"type": "text", "text": "Here's an image:"},
            {"type": "image", "source_type": "url", "url": "https://example.com/image.jpg"},
            {"type": "text", "text": "And here's a file:"},
            {"type": "file", "source_type": "url", "url": "https://example.com/doc.pdf", "name": "Document.pdf"}
        ])
    """

    type: Literal["message"] = Field("message", description="Message type")
    content: str | list[str | dict] = Field(
        ...,
        description="Message content - string or list of content blocks. Content blocks support: "
        'text ({"type": "text", "text": "content"}), '
        'images ({"type": "image", "source_type": "url|base64", "url": "...", "mime_type": "..."}), '
        'audio ({"type": "audio", "source_type": "url|base64", "url": "...", "mime_type": "..."}), '
        'files ({"type": "file", "source_type": "url|base64", "url": "...", "name": "...", "size": 123})',
        max_length=50000,  # Total content length limit
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate message content using content block validation + custom rules."""
        if isinstance(content, str):
            if not content.strip():
                raise ValueError("String content cannot be empty")
            if len(content) > 50000:
                raise ValueError("String content cannot exceed 50KB")
            return content.strip()

        elif isinstance(content, list):
            if not content:
                raise ValueError("Content blocks list cannot be empty")
            if len(content) > 10:
                raise ValueError("Content blocks list cannot exceed 10 blocks")

            # Validate each content block
            for i, block in enumerate(content):
                if isinstance(block, str):
                    if not block.strip():
                        raise ValueError(f"String block at index {i} cannot be empty")
                    continue

                elif isinstance(block, dict):
                    # Validate content blocks - text blocks or data content blocks
                    if block.get("type") == "text":
                        if "text" not in block:
                            raise ValueError(
                                f"Text content block at index {i} missing 'text' field: {block}"
                            )
                    elif not is_data_content_block(block):
                        raise ValueError(f"Invalid content block at index {i}: {block}")
                else:
                    raise ValueError(
                        f"Content block at index {i} must be string or dict, got {type(block)}"
                    )

            return content
        else:
            raise ValueError("Content must be string or list of content blocks")

    def text(self) -> str:
        """Extract text content from message content."""
        if isinstance(self.content, str):
            return self.content

        # Extract text from content blocks
        blocks = [
            block
            for block in self.content
            if isinstance(block, str)
            or (isinstance(block, dict) and block.get("type") == "text")
        ]
        return "".join(
            block if isinstance(block, str) else block["text"] for block in blocks
        )


class HumanInputMessage(BaseInputMessage):
    """Human message input structure for agent requests."""

    role: Literal["user"] = Field("user", description="Message role - user")

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate human message content."""
        # Call parent validation first
        content = super().validate_content(content)

        # For string content, validation is already done
        if isinstance(content, str):
            return content

        # For content blocks, ensure at least one non-empty text block exists
        has_text_content = False
        for block in content:
            if isinstance(block, str):
                if block.strip():  # Non-empty string
                    has_text_content = True
                    break
            elif isinstance(block, dict) and block.get("type") == "text":
                if block.get("text", "").strip():  # Non-empty text field
                    has_text_content = True
                    break

        if not has_text_content:
            raise ValueError(
                "Message must contain at least one non-empty text content block"
            )

        return content

    def to_langchain_message(self) -> HumanMessage:
        """Convert to external message format."""
        if isinstance(self.content, str):
            return HumanMessage(content=self.content, id=generate_message_id())
        else:
            # Pass through content blocks directly
            return HumanMessage(content=self.content, id=generate_message_id())


class ToolCallDecision(BaseModel, StrictModelMixin):
    """Tool decision input structure for agent requests."""

    type: Literal["tool_decision"] = Field("tool_decision", description="Message type")
    tool_call_id: str = Field(
        ..., description="Tool call ID to respond to", min_length=1, max_length=100
    )
    decision: Literal["accept", "feedback", "edit", "reject"] = Field(
        ..., description="Tool decision type"
    )
    args: dict[str, Any] | None = Field(
        None,
        description="Arguments for edit decision",
        max_length=10000,  # Limit args size
    )
    message: str | None = Field(
        None,
        description="Message for feedback/reject decision",
        max_length=1000,  # Limit message length
    )

    @field_validator("tool_call_id")
    @classmethod
    def validate_tool_call_id(cls, v):
        """Validate tool call ID format."""
        # Accept both tool_ and call_ prefixes (system uses call_ prefix)
        if validate_domain_id_format(v, "tool"):
            return v
        elif validate_domain_id_format(v, "call"):
            return v

        raise ValueError("Tool call ID must be either tool_xxx or call_xxx format")

    @field_validator("message")
    @classmethod
    def validate_message(cls, message, info):
        """Validate message field based on decision type."""
        decision = info.data.get("decision")
        if decision in ["feedback", "reject"] and not message:
            raise ValueError(f"{decision} decision requires a message")

        if message and not message.strip():
            raise ValueError("Message cannot be empty or whitespace-only")

        return message.strip() if message else message

    @field_validator("args")
    @classmethod
    def validate_args(cls, args, info):
        """Validate args field based on decision type."""
        decision = info.data.get("decision")
        if decision == "edit" and not args:
            raise ValueError("Args are required for edit decision")

        if args and not isinstance(args, dict):
            raise ValueError("Args must be a dictionary")

        if args and len(str(args)) > 10000:
            raise ValueError("Args serialized size cannot exceed 10KB")

        return args

    @model_validator(mode="after")
    def validate_decision_consistency(self):
        """Validate that decision type matches required fields."""
        if self.decision == "edit" and not self.args:
            raise ValueError("Edit decision requires args")

        if self.decision in ["feedback", "reject"] and not self.message:
            raise ValueError(f"{self.decision} decision requires message")

        if self.decision == "accept" and (self.args or self.message):
            raise ValueError("Accept decision should not include args or message")

        return self


# Union type for all input messages - only human and tool decision messages supported
InputMessage = HumanInputMessage | ToolCallDecision


# ===== Response Types =====


class ToolCall(BaseModel, StrictModelMixin):
    """Tool call structure for AI messages."""

    id: str = Field(..., description="Tool call ID", min_length=1, max_length=100)
    name: str = Field(..., description="Tool name", min_length=1, max_length=100)
    args: dict[str, Any] = Field(
        ...,
        description="Tool arguments",
        max_length=10000,  # Limit args size
    )
    type: str | None = Field(None, description="Tool call type", max_length=50)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        """Validate tool call ID format."""
        # Accept both tool_ and call_ prefixes (system uses call_ prefix)
        if validate_domain_id_format(v, "tool"):
            return v
        elif validate_domain_id_format(v, "call"):
            return v

        raise ValueError("Tool call ID must be either tool_xxx or call_xxx format")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate tool name format."""
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(
                "Tool name must be a valid identifier (letters, numbers, underscore, starting with letter or underscore)"
            )
        return v

    @field_validator("args")
    @classmethod
    def validate_args(cls, v):
        """Validate tool arguments."""
        if not isinstance(v, dict):
            raise ValueError("Tool arguments must be a dictionary")

        if len(str(v)) > 10000:
            raise ValueError("Tool arguments serialized size cannot exceed 10KB")

        return v

    @model_validator(mode="after")
    def validate_tool_call_structure(self):
        """Validate complete tool call structure."""
        # Verify required fields are present and non-empty
        if not self.id or not self.id.strip():
            raise ValueError("Tool call ID cannot be empty")

        if not self.name or not self.name.strip():
            raise ValueError("Tool name cannot be empty")

        if not self.args:
            raise ValueError("Tool arguments cannot be empty")

        # Verify type field if present
        if self.type is not None and self.type != "tool_call":
            raise ValueError("Tool call type should be 'tool_call' when specified")

        return self


class BaseOutputMessage(BaseModel, StrictModelMixin):
    """Base output message structure.

    Examples:
        # Simple text response
        message = HumanOutputMessage(id="msg_123", content="Hello, how can I help you?")

        # Rich content response with images and files
        message = HumanOutputMessage(id="msg_456", content=[
            {"type": "text", "text": "Here's the analysis:"},
            {"type": "image", "source_type": "url", "url": "https://example.com/chart.png"},
            {"type": "file", "source_type": "url", "url": "https://example.com/report.pdf", "name": "Analysis Report"}
        ])
    """

    id: str = Field(..., description="Message ID", max_length=100)
    content: str | list[str | dict] = Field(
        ...,
        description="Message content - string or list of content blocks. Content blocks support: "
        'text ({"type": "text", "text": "content"}), '
        'images ({"type": "image", "source_type": "url|base64", "url": "...", "mime_type": "..."}), '
        'audio ({"type": "audio", "source_type": "url|base64", "url": "...", "mime_type": "..."}), '
        'files ({"type": "file", "source_type": "url|base64", "url": "...", "name": "...", "size": 123})',
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        """Validate message ID format."""
        # Accept msg_ prefix format
        if validate_domain_id_format(v, "msg"):
            return v
        elif "_" in v:
            # Check for run-scoped format: run_xxx-index (index is optional)
            if "-" in v:
                # Has index part
                id_part, index_part = v.split("-", 1)
                if index_part and not index_part.isdigit():
                    raise ValueError("ID Index must be a number")
            else:
                # No index part
                id_part = v

            # Validate the base ID part (with or without index)
            if validate_domain_id_format(id_part, "run"):
                return v
            # Check for conversation-scoped format: conv_xxx-index (for conversation loading)
            elif validate_domain_id_format(id_part, "conv"):
                return v
            # Check for msg-scoped format: msg_xxx-index (for backward compatibility)
            elif validate_domain_id_format(id_part, "msg"):
                return v

        raise ValueError(
            "Message ID must be either msg_xxx format, run_xxx-index format, conv_xxx-index format, or msg_xxx-index format"
        )

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate content using content block validation + custom rules."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            if not content:
                raise ValueError("Content blocks list cannot be empty")
            if len(content) > 10:
                raise ValueError("Content blocks list cannot exceed 10 blocks")

            # Validate each content block
            for i, block in enumerate(content):
                if isinstance(block, str):
                    if not block.strip():
                        raise ValueError(f"String block at index {i} cannot be empty")
                    continue

                elif isinstance(block, dict):
                    # Validate content blocks - text blocks or data content blocks
                    if block.get("type") == "text":
                        if "text" not in block:
                            raise ValueError(
                                f"Text content block at index {i} missing 'text' field: {block}"
                            )
                    elif not is_data_content_block(block):
                        raise ValueError(f"Invalid content block at index {i}: {block}")
                else:
                    raise ValueError(
                        f"Content block at index {i} must be string or dict, got {type(block)}"
                    )

            return content
        else:
            raise ValueError("Content must be string or list of content blocks")

    @model_validator(mode="after")
    def validate_message_structure(self):
        """Validate complete message structure based on role."""
        # Verify content structure for all message types
        if self.content is None:
            raise ValueError("Message must have content")

        # For HumanOutputMessage and AssistantOutputMessage, allow empty content
        # For ToolOutputMessage, content is still required (handled in its own validator)
        if isinstance(self, HumanOutputMessage | AssistantOutputMessage):
            return self

        # For other message types (like ToolOutputMessage), verify at least one content block has text content
        has_text_content = False
        if isinstance(self.content, str):
            has_text_content = True
        elif isinstance(self.content, list):
            for content_block in self.content:
                if isinstance(content_block, str) and content_block.strip():
                    has_text_content = True
                    break
                elif (
                    isinstance(content_block, dict)
                    and content_block.get("type") == "text"
                    and content_block.get("text")
                ):
                    has_text_content = True
                    break

        if not has_text_content:
            raise ValueError("Message must contain at least one text content block")

        return self

    def text(self) -> str:
        """Extract text content from message content."""
        if isinstance(self.content, str):
            return self.content

        # Extract text from content blocks
        blocks = [
            block
            for block in self.content
            if isinstance(block, str)
            or (isinstance(block, dict) and block.get("type") == "text")
        ]
        return "".join(
            block if isinstance(block, str) else block["text"] for block in blocks
        )


class HumanOutputMessage(BaseOutputMessage):
    """Human message output structure."""

    role: Literal["user"] = Field("user", description="Message role")


class AssistantOutputMessage(BaseOutputMessage):
    """Assistant message output structure."""

    role: Literal["assistant"] = Field("assistant", description="Message role")
    tool_calls: list[ToolCall] | None = Field(
        None,
        description="Tool calls",
        max_length=10,  # Limit number of tool calls
    )
    invalid_tool_calls: list[Any] | None = Field(
        None,
        description="Invalid tool calls",
        max_length=10,  # Limit number of invalid tool calls
    )
    finish_reason: (
        Literal["stop", "length", "tool_calls", "content_filter", "function_call"]
        | None
    ) = Field(None, description="Finish reason")
    usage: dict[str, int] | None = Field(..., description="Token usage information")

    @field_validator("usage")
    @classmethod
    def validate_usage(cls, v):
        """Validate token usage information."""
        if not isinstance(v, dict):
            raise ValueError("Usage must be a dictionary")

        required_keys = {"prompt_tokens", "completion_tokens", "total_tokens"}
        missing_keys = required_keys - set(v.keys())
        if missing_keys:
            raise ValueError(f"Usage missing required keys: {missing_keys}")

        for key, value in v.items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"Usage value for {key} must be a non-negative integer"
                )

        return v


class ToolOutputMessage(BaseOutputMessage):
    """Tool message output structure."""

    role: Literal["tool"] = Field("tool", description="Message role")
    tool_call_id: str = Field(
        ..., description="Tool call ID", min_length=1, max_length=100
    )
    tool_name: str | None = Field(None, description="Tool name", max_length=100)
    status: str | None = Field(None, description="Tool execution status", max_length=50)
    args: dict[str, Any] | None = Field(
        None, description="Actual args used for execution", max_length=10000
    )

    @field_validator("tool_call_id")
    @classmethod
    def validate_tool_call_id(cls, v):
        """Validate tool call ID format."""
        # Accept both tool_ and call_ prefixes (system uses call_ prefix)
        if validate_domain_id_format(v, "tool"):
            return v
        elif validate_domain_id_format(v, "call"):
            return v

        raise ValueError("Tool call ID must be either tool_xxx or call_xxx format")

    @model_validator(mode="after")
    def validate_tool_message_structure(self):
        """Validate tool message structure and consistency."""
        # Verify tool call ID is not empty
        if not self.tool_call_id or not self.tool_call_id.strip():
            raise ValueError("Tool call ID cannot be empty")

        # Verify tool message has content
        if not self.content:
            raise ValueError("Tool message must have content")

        # Verify tool message content contains result
        content_text = ""
        if isinstance(self.content, str):
            content_text = self.content
        elif isinstance(self.content, list):
            for content_block in self.content:
                if isinstance(content_block, str):
                    content_text += content_block
                elif (
                    isinstance(content_block, dict)
                    and content_block.get("type") == "text"
                ):
                    content_text += content_block.get("text", "")

        if not content_text.strip():
            raise ValueError("Tool message must contain result content")

        return self


# Union type for all output messages
OutputMessage = HumanOutputMessage | AssistantOutputMessage | ToolOutputMessage


# Public API
__all__ = [
    # Input messages
    "InputMessage",
    "HumanInputMessage",
    "ToolCallDecision",
    # Output messages
    "AssistantOutputMessage",
    "OutputMessage",
    "HumanOutputMessage",
    "ToolCall",
]
