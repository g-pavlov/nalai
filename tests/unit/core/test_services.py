"""
Unit tests for service interfaces.

Tests cover service protocol definitions and contracts.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)


from nalai.core.services import (
    APIService,
    AuditService,
    CacheService,
    CheckpointingService,
    ModelService,
)


class TestServiceProtocols:
    """Test suite for service protocol definitions."""

    def test_checkpointing_service_protocol(self):
        """Test CheckpointingService protocol definition."""
        # Verify the protocol has the expected methods
        assert hasattr(CheckpointingService, "get_checkpointer")
        assert hasattr(CheckpointingService, "get_stats")
        assert hasattr(CheckpointingService, "health_check")

    def test_cache_service_protocol(self):
        """Test CacheService protocol definition."""
        # Verify the protocol has the expected methods
        assert hasattr(CacheService, "get")
        assert hasattr(CacheService, "set")
        assert hasattr(CacheService, "find_similar_cached_responses")

    def test_model_service_protocol(self):
        """Test ModelService protocol definition."""
        # Verify the protocol has the expected methods
        assert hasattr(ModelService, "get_model_from_config")
        assert hasattr(ModelService, "get_model_id_from_config")
        assert hasattr(ModelService, "extract_message_content")
        assert hasattr(ModelService, "get_context_window_size")

    def test_api_service_protocol(self):
        """Test APIService protocol definition."""
        # Verify the protocol has the expected methods
        assert hasattr(APIService, "load_api_summaries")
        assert hasattr(APIService, "load_openapi_specifications")

    def test_audit_service_protocol(self):
        """Test AuditService protocol definition."""
        # Verify the protocol has the expected methods
        assert hasattr(AuditService, "log_conversation_access_event")
        assert hasattr(AuditService, "log_thread_access")


class TestServiceProtocolCompliance:
    """Test suite for service protocol compliance."""

    def test_mock_checkpointing_service_compliance(self):
        """Test that a mock CheckpointingService implements the protocol."""
        from unittest.mock import Mock

        mock_service = Mock(spec=CheckpointingService)

        # Should not raise any errors
        mock_service.get_checkpointer()
        mock_service.get_stats()
        mock_service.health_check()

    def test_mock_cache_service_compliance(self):
        """Test that a mock CacheService implements the protocol."""
        from unittest.mock import Mock

        mock_service = Mock(spec=CacheService)

        # Should not raise any errors
        mock_service.get([], "user_id")
        mock_service.set([], "response", [], "user_id")
        mock_service.find_similar_cached_responses("message", "user_id")

    def test_mock_model_service_compliance(self):
        """Test that a mock ModelService implements the protocol."""
        from unittest.mock import Mock

        mock_service = Mock(spec=ModelService)

        # Should not raise any errors
        mock_service.get_model_from_config({})
        mock_service.get_model_id_from_config({})
        mock_service.extract_message_content("test")
        mock_service.get_context_window_size("gpt-4", "openai")

    def test_mock_api_service_compliance(self):
        """Test that a mock APIService implements the protocol."""
        from unittest.mock import Mock

        mock_service = Mock(spec=APIService)

        # Should not raise any errors
        mock_service.load_api_summaries({})
        mock_service.load_openapi_specifications({})

    def test_mock_audit_service_compliance(self):
        """Test that a mock AuditService implements the protocol."""
        from unittest.mock import Mock

        mock_service = Mock(spec=AuditService)

        # Should not raise any errors
        mock_service.log_conversation_access_event("user_id", "conv_id", "action")
        mock_service.log_thread_access("user_id", "thread_id", "action")
