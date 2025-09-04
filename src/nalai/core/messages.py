"""
This module defines the request and response schemas for the agent message exchange API.
"""

import logging
import re
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.id_generator import generate_message_id, validate_domain_id_format
from .internal.base_models import StrictModelMixin

logger = logging.getLogger("nalai")


# ===== Content Block Types =====
class TextContent(BaseModel, StrictModelMixin):
    """Text content block for structured messages."""

    type: Literal["text"] = Field("text", description="Content type")
    text: str = Field(..., description="Text content", max_length=10000, min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, text):
        """Validate text content."""
        # if not text or not text.strip():
        #     raise ValueError("Text content cannot be empty")

        # Check for excessive whitespace
        if len(text.strip()) != len(text):
            raise ValueError(
                "Text content should not have leading or trailing whitespace"
            )

        # Check for control characters (except newlines and tabs)
        if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", text):
            raise ValueError("Text content contains invalid control characters")

        return text.strip()


# Union type for all content blocks
ContentBlock = TextContent


# ===== Input Message Types =====
class BaseInputMessage(BaseModel, StrictModelMixin):
    """Base input message structure."""

    type: Literal["message"] = Field("message", description="Message type")
    content: str | list[ContentBlock] = Field(
        ...,
        description="Message content - string or structured content blocks",
        max_length=50000,  # Total content length limit
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate message content."""
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

            # Validate total content length across all blocks
            total_length = sum(
                len(block.text) for block in content if hasattr(block, "text")
            )
            if total_length > 50000:
                raise ValueError(
                    "Total content length across all blocks cannot exceed 50KB"
                )

            return content
        else:
            raise ValueError("Content must be string or list of content blocks")


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

        # For content blocks, ensure at least one TextContent block exists
        has_text_content = False
        for block in content:
            if isinstance(block, TextContent):
                has_text_content = True
                break

        if not has_text_content:
            raise ValueError("Message must contain at least one text content block")

        return content

    def to_langchain_message(self) -> HumanMessage:
        """Convert to LangChain HumanMessage."""
        if isinstance(self.content, str):
            return HumanMessage(content=self.content, id=generate_message_id())
        else:
            # Extract text content from content blocks
            text_content = ""
            for block in self.content:
                if isinstance(block, TextContent):
                    text_content += block.text
            return HumanMessage(content=text_content, id=generate_message_id())


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
    """Base output message structure."""

    id: str = Field(..., description="Message ID", min_length=1, max_length=100)
    content: list[ContentBlock] = Field(
        ..., description="Message content blocks", min_length=1
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
    def validate_content(cls, v):
        """Validate content blocks."""
        if not isinstance(v, list):
            raise ValueError("Content must be a list of content blocks")

        if not v:
            raise ValueError("Content blocks list cannot be empty")

        if len(v) > 10:
            raise ValueError("Content blocks list cannot exceed 10 blocks")

        return v

    @model_validator(mode="after")
    def validate_message_structure(self):
        """Validate complete message structure based on role."""
        # Verify content structure for all message types
        if not self.content:
            raise ValueError("Message must have content blocks")

        # Verify at least one content block has text content
        has_text_content = False
        for content_block in self.content:
            if hasattr(content_block, "text") and content_block.text:
                has_text_content = True
                break

        if not has_text_content:
            raise ValueError("Message must contain at least one text content block")

        return self


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
    finish_reason: str | None = Field(None, description="Finish reason", max_length=50)
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

    @field_validator("finish_reason")
    @classmethod
    def validate_finish_reason(cls, v):
        """Validate finish reason."""
        if v is not None:
            valid_reasons = {
                "stop",
                "length",
                "tool_calls",
                "content_filter",
                "function_call",
            }
            if v not in valid_reasons:
                raise ValueError(
                    f"Invalid finish_reason: {v}. Valid reasons: {valid_reasons}"
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
        for content_block in self.content:
            if hasattr(content_block, "text"):
                content_text += content_block.text

        if not content_text.strip():
            raise ValueError("Tool message must contain result content")

        return self


# Union type for all output messages
OutputMessage = HumanOutputMessage | AssistantOutputMessage | ToolOutputMessage


# Public API
__all__ = [
    # Common types
    "ContentBlock",
    "TextContent",
    # Input messages
    "InputMessage",
    "HumanInputMessage",
    "ToolCallDecision",
    # Output messgaes
    "AssistantOutputMessage",
    "OutputMessage",
    "HumanOutputMessage",
    "ToolCall",
]
