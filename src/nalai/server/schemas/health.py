"""
Health resource schemas.

This module contains all schemas for the health check resource:
- /healthz (GET) - Health check endpoint
"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthzResponse(BaseModel):
    """Status model for health check."""

    status: Literal["Healthy"] = Field(..., description="Health status")
