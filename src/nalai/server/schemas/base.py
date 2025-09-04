"""Base schemas for the server."""

from pydantic import BaseModel, Field, field_validator


class ConversationIdPathParam(BaseModel):
    """Path parameter for conversation ID with domain-prefixed validation."""

    conversation_id: str = Field(
        ...,
        description="Conversation ID (must be valid domain-prefixed format: conv_xxx)",
        min_length=1,
        max_length=100,
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v):
        """Validate that conversation_id is a valid domain-prefixed ID."""
        # Import validation function locally to avoid circular imports
        from ...utils.id_generator import validate_domain_id_format

        if not validate_domain_id_format(v, "conv"):
            raise ValueError(
                "conversation_id must be a valid domain-prefixed format: conv_xxx"
            ) from None
        return v
