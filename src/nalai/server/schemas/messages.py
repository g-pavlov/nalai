"""
Message schemas for the server.

This module defines the request and response schemas for the agent message exchange API.
"""

import logging
import re
from typing import Any, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...utils.id_generator import generate_message_id, validate_domain_id_format
from .base import StrictModelMixin

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
        if not text or not text.strip():
            raise ValueError("Text content cannot be empty")

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


class ToolDecisionInputMessage(BaseModel, StrictModelMixin):
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

    def to_langchain_message(self) -> HumanMessage:
        """
        Convert to LangChain HumanMessage for tool decisions.
        This creates a human message with the decision information in additional_kwargs.
        """
        decision_content = f"Decision: {self.decision}"

        if self.decision == "feedback" and self.message:
            decision_content += f" - {self.message}"
        elif self.decision == "edit" and self.args:
            decision_content += f" - {self.args}"
        elif self.decision == "reject" and self.message:
            decision_content += f" - {self.message}"

        # Include tool decision data in additional_kwargs for proper detection
        tool_decision_data = {
            "decision": self.decision,
            "tool_call_id": self.tool_call_id,
        }
        if self.args:
            tool_decision_data["args"] = self.args
        if self.message:
            tool_decision_data["message"] = self.message

        return HumanMessage(
            content=decision_content,
            id=generate_message_id(),
            additional_kwargs={"tool_decision": tool_decision_data},
        )


# Union type for all input messages - only human and tool decision messages supported
InputMessage = HumanInputMessage | ToolDecisionInputMessage


class MessageRequest(BaseModel):
    """Request model for agent message exchange endpoint.

    This endpoint supports multiple conversation flows:

    **Stateful Conversations (store: true):**
    - New conversation: no conversation_id
    - Continue conversation: with conversation_id
    - Tool decision: single tool_decision message
    - Human message: single human message

    **Stateless Conversations (store: false):**
    - Multiple human messages only
    - Must start with human message
    - No history constraints

    **Transport Compatibility:**
    - stream="full"/"events" requires Accept: text/event-stream
    - stream="off" requires Accept: application/json

    **Content Limits:**
    - Individual text blocks: max 10KB
    - Total conversation: max 100KB
    - Content blocks per message: max 10
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(
        None, description="Conversation ID for continuation", max_length=100
    )
    previous_response_id: str | None = Field(
        None, description="Response ID to branch from", max_length=100
    )
    input: str | list[InputMessage] = Field(
        ...,
        description="Input messages - string (implicit human message) or list of structured messages. String input is converted to implicit human message. List input supports human messages and tool decision messages only.",
        min_length=1,
    )
    stream: Literal["full", "events", "off"] = Field(
        "full",
        description="Streaming mode - full (typed events + tokens), events (typed events only), off (non-streaming). Requires compatible Accept header: 'full'/'events' need 'text/event-stream', 'off' needs 'application/json'",
    )
    store: bool = Field(True, description="Whether to store the response")

    cache: bool = Field(
        True,
        description="Whether to use caching for this request. Set to false to bypass cache and get fresh responses.",
    )

    model_settings: dict[str, Any] | None = Field(
        None,
        description="Model-specific settings to override default configuration",
        max_length=10000,  # Limit model settings size
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate conversation ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "conv"):
                raise ValueError(
                    "conversation_id must be a valid domain-prefixed format: conv_xxx"
                )
        return v

    @field_validator("previous_response_id")
    @classmethod
    def validate_previous_response_id(cls, v):
        """Validate previous response ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "run"):
                raise ValueError(
                    "previous_response_id must be a valid domain-prefixed format: run_xxx"
                )
        return v

    @field_validator("input")
    @classmethod
    def validate_input(cls, input_data, info):
        """Validate input messages for basic structure."""
        # Handle string input - convert to implicit human message
        if isinstance(input_data, str):
            if not input_data.strip():
                raise ValueError("String input cannot be empty")
            if len(input_data) > 50000:
                raise ValueError("String input cannot exceed 50KB")
            # Return string as-is - it will be converted to human message in to_langchain_messages
            return input_data

        # Handle list input
        if not isinstance(input_data, list):
            raise ValueError("Input must be a string or list of messages")

        if not input_data:
            raise ValueError("Input messages list cannot be empty")

        if len(input_data) > 50:
            raise ValueError("Input messages list cannot exceed 50 messages")

        return input_data

    @field_validator("model_settings")
    @classmethod
    def validate_model_settings(cls, v):
        """Validate model settings structure."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("model_settings must be a dictionary")

            # Validate model settings keys
            allowed_keys = {
                "temperature",
                "max_tokens",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
            }
            invalid_keys = set(v.keys()) - allowed_keys
            if invalid_keys:
                raise ValueError(
                    f"Invalid model_settings keys: {invalid_keys}. Allowed: {allowed_keys}"
                )

            # Validate temperature range
            if "temperature" in v:
                temp = v["temperature"]
                if not isinstance(temp, int | float) or temp < 0 or temp > 2:
                    raise ValueError("temperature must be a number between 0 and 2")

            # Validate max_tokens
            if "max_tokens" in v:
                max_tokens = v["max_tokens"]
                if not isinstance(max_tokens, int) or max_tokens < 1:
                    raise ValueError("max_tokens must be a positive integer")

        return v

    @model_validator(mode="after")
    def validate_input_message_list(self):
        """Validate input message list for proper conversation flow."""
        if isinstance(self.input, list):
            self._validate_conversation_sequence(self.input)

        return self

    def _validate_conversation_sequence(self, messages):
        """Validate proper conversation flow sequence - only human messages supported."""
        for i in range(len(messages) - 1):
            current_msg = messages[i]
            next_msg = messages[i + 1]

            # Validate proper conversation flow - only human messages allowed
            if isinstance(current_msg, HumanInputMessage):
                # Human message can be followed by another human message
                if not isinstance(next_msg, HumanInputMessage):
                    raise ValueError(
                        f"Human message at position {i} can only be followed by another human message"
                    )

    def to_langchain_messages(self) -> list[BaseMessage]:
        """Convert to LangChain message format."""
        messages = []

        # Handle string input - convert to implicit human message
        if isinstance(self.input, str):
            from langchain_core.messages import HumanMessage

            messages.append(HumanMessage(content=self.input, id=generate_message_id()))
        else:
            # Handle list input
            for msg in self.input:
                # Handle existing InputMessage types
                messages.append(msg.to_langchain_message())

        return messages

    def to_runtime_overrides(self) -> dict[str, Any]:
        """Convert runtime configuration overrides to dict."""
        overrides = {}

        # Cache override (always include since it has a default)
        overrides["disable_cache"] = not self.cache

        # Model settings override
        if self.model_settings:
            overrides["model_settings"] = self.model_settings

        return overrides


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
        elif "_" in v and v.count("-") == 1:
            # Check for run-scoped format: run_xxx-index
            run_part, index_part = v.split("-", 1)
            if validate_domain_id_format(run_part, "run") and index_part.isdigit():
                return v
            # Check for conversation-scoped format: conv_xxx-index (for conversation loading)
            elif validate_domain_id_format(run_part, "conv") and index_part.isdigit():
                return v
            # Check for msg-scoped format: msg_xxx-index (for backward compatibility)
            elif validate_domain_id_format(run_part, "msg") and index_part.isdigit():
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
    usage: dict[str, int] = Field(..., description="Token usage information")

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


class Interrupt(BaseModel, StrictModelMixin):
    """Single interrupt information structure."""

    type: str = Field(..., description="Interrupt type", min_length=1, max_length=50)
    tool_call_id: str = Field(
        ..., description="Tool call ID", min_length=1, max_length=100
    )
    action: str = Field(..., description="Tool action", min_length=1, max_length=100)
    args: dict[str, Any] = Field(
        ...,
        description="Tool arguments",
        max_length=10000,  # Limit args size
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

    @field_validator("args")
    @classmethod
    def validate_args(cls, v):
        """Validate tool arguments."""
        if not isinstance(v, dict):
            raise ValueError("Tool arguments must be a dictionary")

        if len(str(v)) > 10000:
            raise ValueError("Tool arguments serialized size cannot exceed 10KB")

        return v


class ResponseMetadata(BaseModel, StrictModelMixin):
    """Response-level metadata structure."""

    error: str | None = Field(
        None, description="Error message if response failed", max_length=1000
    )
    cache_hit: bool | None = Field(
        None, description="Whether this response was served from cache"
    )
    processing_time_ms: float | None = Field(
        None,
        description="Response processing time in milliseconds",
        ge=0.0,  # Must be non-negative
    )

    @field_validator("processing_time_ms")
    @classmethod
    def validate_processing_time(cls, v):
        """Validate processing time."""
        if v is not None and (v < 0 or v > 3600000):  # Max 1 hour
            raise ValueError(
                "Processing time must be between 0 and 3,600,000 ms (1 hour)"
            )
        return v


class MessageResponse(BaseModel):
    """Response model for agent message exchange endpoint."""

    id: str = Field(..., description="Response ID", min_length=1, max_length=100)
    conversation_id: str | None = Field(
        None, description="Conversation ID", max_length=100
    )
    previous_response_id: str | None = Field(
        None,
        description="Previous response ID if this response branches from another",
        max_length=100,
    )
    output: list[OutputMessage] = Field(
        ..., description="Output messages", min_length=1
    )
    created_at: str = Field(..., description="Creation timestamp", max_length=50)
    status: Literal["completed", "interrupted", "error", "cancelled", "processing"] = (
        Field(..., description="Response status")
    )
    interrupts: list[Interrupt] | None = Field(
        None,
        description="List of interrupts if response was interrupted",
        max_length=10,  # Limit number of interrupts
    )
    metadata: ResponseMetadata | None = Field(None, description="Response metadata")
    usage: dict[str, int] = Field(..., description="Token usage information")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        """Validate response ID format."""
        if not validate_domain_id_format(v, "run"):
            raise ValueError(
                "Response ID must be a valid domain-prefixed format: run_xxx"
            )
        return v

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate conversation ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "conv"):
                raise ValueError(
                    "Conversation ID must be a valid domain-prefixed format: conv_xxx"
                )
        return v

    @field_validator("previous_response_id")
    @classmethod
    def validate_previous_response_id(cls, v):
        """Validate previous response ID format when provided."""
        if v is not None:
            if not validate_domain_id_format(v, "run"):
                raise ValueError(
                    "Previous response ID must be a valid domain-prefixed format: run_xxx"
                )
        return v

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v):
        """Validate creation timestamp format."""
        # Accept ISO 8601 format with or without timezone offset
        if not re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3,6})?(Z|[+-]\d{2}:\d{2})?$", v
        ):
            raise ValueError(
                "created_at must be in ISO 8601 format (YYYY-MM-DDTHH:MM:SS[.mmm][Z|±HH:MM])"
            )
        return v

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

    @model_validator(mode="after")
    def validate_response_consistency(self):
        """Validate response consistency."""
        # If status is interrupted, interrupts should be provided
        if self.status == "interrupted" and not self.interrupts:
            raise ValueError("Interrupted status requires interrupts list")

        # If status is error, metadata should contain error
        if self.status == "error" and (not self.metadata or not self.metadata.error):
            raise ValueError("Error status requires error message in metadata")

        return self

    @model_validator(mode="after")
    def validate_response_structure(self):
        """Validate complete response structure."""
        # Verify required fields are present
        if not self.id:
            raise ValueError("Response must have an ID")

        if not self.output:
            raise ValueError("Response must have output messages")

        if not self.created_at:
            raise ValueError("Response must have creation timestamp")

        if not self.status:
            raise ValueError("Response must have status")

        # Verify output contains at least one message
        if len(self.output) == 0:
            raise ValueError("Response output must contain at least one message")

        # Verify all output messages have valid structure
        for i, message in enumerate(self.output):
            if not message.id:
                raise ValueError(f"Output message {i} must have an ID")

            if not message.content:
                raise ValueError(f"Output message {i} must have content")

            if not message.role:
                raise ValueError(f"Output message {i} must have a role")

        return self
