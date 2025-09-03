"""
Resume decision schemas.

This module defines the request and response schemas for resume decision operations.
"""

from typing import Any, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from ...utils.id_generator import generate_message_id
from .base import StrictModelMixin


class ResumeDecision(BaseModel, StrictModelMixin):
    """Input structure for resume decision operations."""

    action: Literal["accept", "reject", "edit", "feedback"] = Field(
        ..., description="The decision type"
    )
    args: dict[str, Any] | None = Field(
        None,
        description="Optional arguments for the action (e.g., edited args for 'edit' action)",
    )
    message: str | None = Field(
        None, description="Message for feedback/reject decision"
    )
    tool_call_id: str = Field(..., description="Tool call ID to act upon")

    def to_internal(self) -> dict:
        """Convert to internal format for agent processing."""
        action = self.action
        args = {}

        if self.action == "edit" and self.args:
            args = self.args
        elif self.action in ["feedback", "reject"] and self.message:
            args = {"message": self.message}

        return {"action": action, "args": args}

    def to_langchain_messages(self) -> list[BaseMessage]:
        """Convert to LangChain message format for resume decisions."""
        # For resume decisions, we create a human message with the decision
        content = f"Decision: {self.action}"

        if self.action == "feedback" and hasattr(self, "message"):
            content += f" - {self.message}"
        elif self.action == "edit" and hasattr(self, "args"):
            content += f" - {self.args}"
        elif self.action == "reject" and hasattr(self, "message"):
            content += f" - {self.message}"

        return [HumanMessage(content=content, id=generate_message_id())]
