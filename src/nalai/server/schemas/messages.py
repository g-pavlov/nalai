"""
Agent Message Exchange API schemas.

This module contains all schemas for the agent message exchange endpoint:
- /api/v1/messages (POST) - conversation operations (new, append, resume)
"""

from typing import Any, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ===== Common Mixins =====


class StrictModelMixin:
    """Mixin for models that forbid extra fields."""

    model_config = ConfigDict(extra="forbid")


# ===== Common Validators =====


def validate_non_empty_string(value: str, field_name: str = "field") -> str:
    """Validate that a string field is not empty."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    return value.strip()


# ===== Common Types =====


class ContentBlock(BaseModel):
    """Base content block for message content."""

    type: str = Field(..., description="Content type")


class TextContent(ContentBlock):
    """Text content block for message content."""

    type: Literal["text"] = Field("text", description="Content type - text")
    text: str = Field(..., description="Text content", max_length=10000, min_length=1)


# ===== Request Types =====


class BaseInputMessage(BaseModel, StrictModelMixin):
    """Base input message structure with common properties."""

    role: str = Field(..., description="Message role")
    content: str | list[TextContent] = Field(
        ..., description="Message content - string or text content blocks", min_length=1
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, content):
        """Validate message content."""
        if isinstance(content, str):
            return content.strip()
        elif isinstance(content, list):
            if len(content) > 10:
                raise ValueError("Message content blocks cannot exceed 10")
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
            return HumanMessage(content=self.content)
        else:
            # Extract text content from content blocks
            text_content = ""
            for block in self.content:
                if isinstance(block, TextContent):
                    text_content += block.text
            return HumanMessage(content=text_content)


class ToolDecisionInputMessage(BaseModel, StrictModelMixin):
    """Tool decision input structure for agent requests."""

    type: Literal["tool_decision"] = Field(
        "tool_decision", description="Message type - tool decision"
    )
    tool_call_id: str = Field(
        ..., description="Tool call ID to correlate with interrupt"
    )
    decision: Literal["accept", "reject", "edit", "feedback"] = Field(
        ..., description="Decision type"
    )
    args: dict[str, Any] | None = Field(
        None, description="Editable tool call arguments for edit decision"
    )
    message: str | None = Field(
        None, description="Feedback message for feedback decision"
    )

    @field_validator("tool_call_id")
    @classmethod
    def validate_tool_call_id(cls, tool_call_id):
        """Validate tool call ID."""
        if not tool_call_id or not tool_call_id.strip():
            raise ValueError("Tool call ID cannot be empty")
        return tool_call_id.strip()

    @field_validator("args")
    @classmethod
    def validate_args(cls, args, info):
        """Validate args field."""
        decision = info.data.get("decision")
        if decision == "edit" and not args:
            raise ValueError("Args are required for edit decision")
        return args

    @field_validator("message")
    @classmethod
    def validate_message(cls, message, info):
        """Validate message field."""
        decision = info.data.get("decision")
        if decision == "feedback" and not message:
            raise ValueError("Message is required for feedback decision")
        return message

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
        None, description="Conversation ID for continuation"
    )
    previous_response_id: str | None = Field(
        None, description="Response ID to branch from"
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
        description="Enable caching for this request. Defaults to True (caching enabled).",
    )

    @model_validator(mode="after")
    def validate_input_message_list(self):
        """Validate list of InputMessage objects - only human and tool decision messages supported."""
        # Skip validation for string input
        if isinstance(self.input, str):
            return self

        # Get store value from the request
        store = self.store

        # Count message types
        human_messages = [
            msg for msg in self.input if isinstance(msg, HumanInputMessage)
        ]
        tool_decisions = [
            msg for msg in self.input if isinstance(msg, ToolDecisionInputMessage)
        ]

        if store:
            # Scenario 1: Stateful conversation (store: true)
            # - Exactly 1 human message OR exactly 1 tool decision

            if len(tool_decisions) == 1 and len(human_messages) == 0:
                # Tool decision scenario
                if len(self.input) != 1:
                    raise ValueError(
                        "Tool decision requests must contain exactly one tool decision message"
                    )
            elif len(human_messages) == 1 and len(tool_decisions) == 0:
                # Human message scenario
                if len(self.input) != 1:
                    raise ValueError(
                        "Stateful conversations must contain exactly one human message"
                    )
            else:
                raise ValueError(
                    "Stateful conversations must have exactly one human message OR exactly one tool decision"
                )

        else:
            # Scenario 2: Stateless conversation (store: false)
            # - 1+ messages of human type only
            # - Must start with human message

            if len(human_messages) == 0:
                raise ValueError(
                    "Stateless conversations must start with a human message"
                )

            if not isinstance(self.input[0], HumanInputMessage):
                raise ValueError(
                    "Stateless conversations must start with a human message"
                )

            # All messages must be human messages in stateless mode
            for i, msg in enumerate(self.input):
                if not isinstance(msg, HumanInputMessage):
                    raise ValueError(
                        f"Stateless conversations only support human messages, found {type(msg).__name__} at position {i}"
                    )

            # Validate conversation sequence for human messages
            self._validate_conversation_sequence(self.input)

        # Validate total content size
        total_size = 0
        for msg in self.input:
            if isinstance(msg, HumanInputMessage):
                if isinstance(msg.content, str):
                    total_size += len(msg.content)
                else:
                    for block in msg.content:
                        if block.type == "text":
                            total_size += len(block.text)
            elif isinstance(msg, ToolDecisionInputMessage):
                total_size += len(str(msg.decision))
                if msg.message:
                    total_size += len(msg.message)

        max_total_size = 100 * 1024  # 100KB total limit
        if total_size > max_total_size:
            raise ValueError(
                f"Total message content too large (max {max_total_size // 1024}KB)"
            )

        return self

    @field_validator("input")
    @classmethod
    def validate_input(cls, input_data, info):
        """Validate input messages for basic structure."""
        # Handle string input - convert to implicit human message
        if isinstance(input_data, str):
            if not input_data.strip():
                raise ValueError("String input cannot be empty")
            # Return string as-is - it will be converted to human message in to_langchain_messages
            return input_data

        # Handle list input
        if not isinstance(input_data, list):
            raise ValueError("Input must be a string or list of messages")

        if not input_data:
            raise ValueError("Input messages list cannot be empty")

        return input_data

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

            messages.append(HumanMessage(content=self.input))
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

        return overrides


# ===== Response Types =====


class ToolCall(BaseModel, StrictModelMixin):
    """Tool call structure for AI messages."""

    id: str = Field(..., description="Unique identifier for the tool call")
    name: str = Field(..., description="Name of the tool/function to call")
    args: dict[str, Any] = Field(..., description="Arguments to pass to the tool")

    @field_validator("id", "name")
    @classmethod
    def validate_non_empty_strings(cls, value):
        """Validate that string fields are not empty."""
        return validate_non_empty_string(value, "Field")


class Interrupt(BaseModel):
    """Single interrupt information structure."""

    type: str = Field(..., description="Interrupt type")
    tool_call_id: str = Field(..., description="Tool call ID")
    action: str = Field(..., description="Tool action")
    args: dict[str, Any] = Field(..., description="Tool arguments")


class ResponseMetadata(BaseModel, StrictModelMixin):
    """Response-level metadata structure."""

    error: str | None = Field(None, description="Error message if response failed")
    cache_hit: bool | None = Field(
        None, description="Whether this response was served from cache"
    )
    processing_time_ms: float | None = Field(
        None, description="Response processing time in milliseconds"
    )


class BaseOutputMessage(BaseModel):
    """Base output message structure for agent responses."""

    id: str = Field(..., description="Message ID")
    content: list[TextContent] = Field(..., description="Message content blocks")
    role: str = Field(..., description="Message role")


class HumanOutputMessage(BaseOutputMessage):
    """Human message output structure."""

    role: Literal["human"] = Field("human", description="Message role - human")


class AssistantOutputMessage(BaseOutputMessage):
    """Assistant message output structure."""

    role: Literal["assistant"] = Field(
        "assistant", description="Message role - assistant"
    )
    tool_calls: list[ToolCall] | None = Field(
        None, description="Tool calls for assistant messages"
    )
    invalid_tool_calls: list[dict[str, Any]] | None = Field(
        None, description="Invalid tool calls for assistant messages"
    )
    finish_reason: str | None = Field(
        None, description="Reason why message generation finished"
    )
    usage: dict[str, Any] = Field(
        ..., description="Token usage for this specific message (incremental)"
    )


class ToolOutputMessage(BaseOutputMessage):
    """Tool message output structure."""

    role: Literal["tool"] = Field("tool", description="Message role - tool")
    tool_call_id: str = Field(..., description="Tool call ID for tool messages")


# Union type for all output messages
OutputMessage = HumanOutputMessage | AssistantOutputMessage | ToolOutputMessage


class MessageResponse(BaseModel):
    """Response model for agent message exchange endpoint."""

    id: str = Field(..., description="Response ID")
    conversation_id: str = Field(..., description="Conversation ID")
    previous_response_id: str | None = Field(
        None, description="Previous response ID if this response branches from another"
    )

    output: list[OutputMessage] = Field(..., description="Output messages")
    created_at: str = Field(..., description="Creation timestamp")
    status: Literal["completed", "interrupted", "error", "cancelled", "processing"] = (
        Field(..., description="Response status")
    )
    interrupts: list[Interrupt] | None = Field(
        None, description="List of interrupts if response was interrupted"
    )
    metadata: ResponseMetadata | None = Field(None, description="Response metadata")
    usage: dict[str, Any] = Field(..., description="Token usage information")
