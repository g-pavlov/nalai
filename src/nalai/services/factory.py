"""
Unified service factory for dependency injection.

This module provides a centralized way to create and configure services
that implement the core package Protocol interfaces.
"""

import logging

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.services import (
        APIService,
        AuditService,
        CacheService,
        CheckpointingService,
        ModelService,
    )

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating service instances that implement core Protocol interfaces."""

    # Service instances cache
    _instances: dict[str, Any] = {}

    @classmethod
    def create_checkpointing_service(cls) -> "CheckpointingService":
        """Create checkpointing service instance."""
        if "checkpointing" not in cls._instances:
            from .checkpointing_service import get_checkpointing_service

            cls._instances["checkpointing"] = get_checkpointing_service()
        return cls._instances["checkpointing"]

    @classmethod
    def create_cache_service(cls) -> "CacheService":
        """Create cache service instance."""
        if "cache" not in cls._instances:
            from .cache_service import get_cache_service

            cls._instances["cache"] = get_cache_service()
        return cls._instances["cache"]

    @classmethod
    def create_model_service(cls) -> "ModelService":
        """Create model service instance."""
        if "model" not in cls._instances:
            from .model_service import ModelManager

            cls._instances["model"] = ModelManager()
        return cls._instances["model"]

    @classmethod
    def create_api_service(cls) -> "APIService":
        """Create API service instance."""
        if "api" not in cls._instances:
            from .openapi_service import OpenAPIManager

            cls._instances["api"] = OpenAPIManager()
        return cls._instances["api"]

    @classmethod
    def create_audit_service(cls) -> "AuditService":
        """Create audit service instance."""
        if "audit" not in cls._instances:
            from .audit_service import get_audit_service

            cls._instances["audit"] = get_audit_service()
        return cls._instances["audit"]

    @classmethod
    def create_all_services(cls) -> dict[str, Any]:
        """Create all service instances."""
        return {
            "checkpointing_service": cls.create_checkpointing_service(),
            "cache_service": cls.create_cache_service(),
            "model_service": cls.create_model_service(),
            "api_service": cls.create_api_service(),
            "audit_service": cls.create_audit_service(),
        }

    @classmethod
    def reset_instances(cls) -> None:
        """Reset all cached instances (useful for testing)."""
        cls._instances.clear()


# Convenience functions for backward compatibility
def get_checkpointing_service() -> "CheckpointingService":
    """Get checkpointing service instance."""
    return ServiceFactory.create_checkpointing_service()


def get_cache_service() -> "CacheService":
    """Get cache service instance."""
    return ServiceFactory.create_cache_service()


def get_model_service() -> "ModelService":
    """Get model service instance."""
    return ServiceFactory.create_model_service()


def get_api_service() -> "APIService":
    """Get API service instance."""
    return ServiceFactory.create_api_service()


def get_audit_service() -> "AuditService":
    """Get audit service instance."""
    return ServiceFactory.create_audit_service()
