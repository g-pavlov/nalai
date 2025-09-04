"""Internal base utilities for the core package."""

from pydantic import ConfigDict


class StrictModelMixin:
    """Mixin for models that forbid extra fields."""

    model_config = ConfigDict(extra="forbid")
