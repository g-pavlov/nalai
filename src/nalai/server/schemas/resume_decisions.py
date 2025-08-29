"""
Resume decision schemas for the server.

This module defines the request and response schemas for resume decision operations.
"""

from typing import Any, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from ...utils.id_generator import generate_message_id
from .base import StrictModelMixin


class ResumeDecisionInput(BaseModel, StrictModelMixin):
    """Input structure for resume decision operations."""

    decision: Literal["feedback", "edit", "reject"] = Field(
        ..., description="Decision type"
    )
    tool_call_id: str = Field(..., description="Tool call ID to respond to")
    args: dict[str, Any] | None = Field(None, description="Arguments for edit decision")
    message: str | None = Field(
        None, description="Message for feedback/reject decision"
    )


class ResumeDecisionRequest(BaseModel):
    """Request model for resume decision operations."""

    conversation_id: str = Field(..., description="Conversation ID")
    response_id: str = Field(..., description="Response ID to resume")
    input: ResumeDecisionInput = Field(..., description="Decision input")

    def to_internal(self) -> dict:
        """Convert to internal format for agent processing."""
        action = self.input.decision
        args = {}

        if self.input.decision == "edit" and self.input.args:
            args = self.input.args
        elif self.input.decision in ["feedback", "reject"] and self.input.message:
            args = {"message": self.input.message}

        return {"action": action, "args": args}

    def to_langchain_messages(self) -> list[BaseMessage]:
        """Convert to LangChain message format for resume decisions."""
        # For resume decisions, we create a human message with the decision
        decision_input = self.input
        content = f"Decision: {decision_input.decision}"

        if decision_input.decision == "feedback" and hasattr(decision_input, "message"):
            content += f" - {decision_input.message}"
        elif decision_input.decision == "edit" and hasattr(decision_input, "args"):
            content += f" - {decision_input.args}"
        elif decision_input.decision == "reject" and hasattr(decision_input, "message"):
            content += f" - {decision_input.message}"

        return [HumanMessage(content=content, id=generate_message_id())]


class ResumeDecisionResponse(BaseModel):
    """Response model for resume decision operations."""

    conversation_id: str = Field(..., description="Conversation ID")
    response_id: str = Field(..., description="New response ID")
    status: Literal["completed", "processing", "error"] = Field(
        ..., description="Response status"
    )
    message: str | None = Field(None, description="Status message")
