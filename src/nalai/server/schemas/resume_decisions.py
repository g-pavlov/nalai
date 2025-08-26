"""
Resume decision resource schemas.

This module contains all schemas for the resume decision resource:
- /api/v1/conversations/{conversation_id}/resume-decision (POST) - Resume decision
"""

from typing import Any, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, Field


class SimpleResumeDecisionRequest(BaseModel):
    """Simple tool call resume request that only requires decision."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["accept", "reject"] = Field(
        ..., description="Type of tool call decision. One of 'accept' or 'reject'"
    )
    message: str | None = Field(
        None, description="Optional message for reject decisions", max_length=1000
    )


class EditResumeDecisionRequest(BaseModel):
    """Complex tool call resume request that requires both decision and args."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["edit"] = Field(
        "edit", description="Type of tool call decision - 'edit'"
    )
    args: dict = Field(
        ...,
        description="Edited tool call args. Must be valid tool arguments matching the original tool call structure.",
    )


class FeedbackResumeDecisionRequest(BaseModel):
    """Complex tool call resume request that requires both decision and args."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["feedback"] = Field(
        "feedback", description="Type of tool call decision - 'feedback'"
    )
    message: str = Field(
        ..., description="The feedback message to send back to LLM", max_length=1000
    )


ToolCallDecisionUnion = (
    SimpleResumeDecisionRequest
    | EditResumeDecisionRequest
    | FeedbackResumeDecisionRequest
)


class ResumeDecisionRequest(BaseModel):
    """Request model for tool decision handling.

    **Decision Types:**
    - **accept**: Execute the tool call as-is
    - **reject**: Cancel the tool call (optional message)
    - **edit**: Modify tool call arguments (requires valid args)
    - **feedback**: Provide feedback to the LLM (requires message)

    **Validation Rules:**
    - edit decisions require valid args matching tool structure
    - feedback decisions require non-empty message
    - Message length limits: 1000 characters
    """

    model_config = ConfigDict(extra="forbid")

    input: ToolCallDecisionUnion = Field(
        ..., description="The tool call decision input"
    )

    def to_internal(self) -> dict:
        """
        Convert the request to the internal format expected by LangGraph.

        Returns:
            dict: The internal format with action, args, and tool_call_id fields
        """
        decision_input = self.input

        # Extract the decision type
        decision = decision_input.decision

        # Pass through the decision as the action
        action = decision

        # Extract args based on decision type
        if decision == "edit":
            args = decision_input.args
        elif decision == "feedback":
            args = decision_input.message
        else:
            # For accept and reject, no args needed
            args = None
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

        return [HumanMessage(content=content)]


class ResumeDecisionResponse(BaseModel):
    """Response model for resume decision operations."""

    model_config = ConfigDict(extra="forbid")

    output: dict[str, Any] = Field(..., description="Resume decision output")
