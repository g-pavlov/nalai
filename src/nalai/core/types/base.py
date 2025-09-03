"""Base type models for the core package."""

from pydantic import ConfigDict


# Import validation function locally to avoid circular imports
class StrictModelMixin:
    """Mixin for models that forbid extra fields."""

    model_config = ConfigDict(extra="forbid")
