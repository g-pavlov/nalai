"""
Unit tests for Agent models and exceptions.

Tests the data models and exception hierarchy in the agent module.
"""

import pytest

from nalai.core import (
    AccessDeniedError,
    ClientError,
    ConversationInfo,
    ConversationNotFoundError,
    InvocationError,
    ValidationError,
)

# Internal types for unit testing
from nalai.core.agent import Error, SelectApi, SelectedApis


class TestAgentModels:
    """Test the Agent data models."""

    def test_conversation_info_model(self):
        """Test ConversationInfo model creation and field access."""
        conversation_info = ConversationInfo(
            conversation_id="test-conv-123",
            created_at="2024-01-01T00:00:00Z",
            last_accessed="2024-01-01T00:00:00Z",
            preview="Test conversation preview",
            status="active",
        )
        assert conversation_info.conversation_id == "test-conv-123"
        assert conversation_info.preview == "Test conversation preview"
        assert conversation_info.status == "active"
        assert conversation_info.created_at == "2024-01-01T00:00:00Z"
        assert conversation_info.last_accessed == "2024-01-01T00:00:00Z"
        assert conversation_info.interrupt_info is None

    def test_conversation_info_defaults(self):
        """Test ConversationInfo model with default values."""
        conversation_info = ConversationInfo(conversation_id="test-conv-456")
        assert conversation_info.conversation_id == "test-conv-456"
        assert conversation_info.status == "active"  # default value
        assert conversation_info.created_at is None
        assert conversation_info.last_accessed is None
        assert conversation_info.preview is None
        assert conversation_info.interrupt_info is None

    def test_select_api_model(self):
        """Test SelectApi model creation."""
        api = SelectApi(api_title="Test API", api_version="1.0.0")
        assert api.api_title == "Test API"
        assert api.api_version == "1.0.0"

    def test_selected_apis_model(self):
        """Test SelectedApis model creation and default behavior."""
        # Test with empty list (default)
        apis = SelectedApis()
        assert apis.selected_apis == []

        # Test with API list
        api1 = SelectApi(api_title="API 1", api_version="1.0")
        api2 = SelectApi(api_title="API 2", api_version="2.0")
        apis = SelectedApis(selected_apis=[api1, api2])
        assert len(apis.selected_apis) == 2
        assert apis.selected_apis[0].api_title == "API 1"
        assert apis.selected_apis[1].api_title == "API 2"


class TestAgentExceptions:
    """Test the Agent exception hierarchy."""

    def test_exception_inheritance(self):
        """Test that exceptions follow proper inheritance hierarchy."""
        # Test inheritance hierarchy
        assert issubclass(ValidationError, Error)
        assert issubclass(InvocationError, Error)
        assert issubclass(ConversationNotFoundError, Error)
        assert issubclass(AccessDeniedError, Error)
        assert issubclass(ClientError, Error)

    @pytest.mark.parametrize(
        "exception_class,expected_code,expected_message",
        [
            (ValidationError, "VALIDATION_ERROR", "Invalid input"),
            (InvocationError, "AGENT_ERROR", "Operation failed"),
            (ConversationNotFoundError, "NOT_FOUND", "Conversation not found"),
            (AccessDeniedError, "ACCESS_DENIED", "Access denied to conversation"),
            (ClientError, "CLIENT_ERROR", "Bad request"),
        ],
    )
    def test_exception_creation_and_properties(
        self, exception_class, expected_code, expected_message
    ):
        """Test exception creation and property access."""
        error = exception_class(expected_message)
        assert str(error) == expected_message
        assert error.error_code == expected_code
        assert error.message == expected_message
        assert error.context == {}

    def test_exception_with_context(self):
        """Test exception context handling."""
        context = {"field": "test_field", "value": "invalid_value"}
        error = ValidationError("Invalid input", context=context)
        assert error.context == context
        assert error.error_code == "VALIDATION_ERROR"

    def test_client_error_http_status(self):
        """Test ClientError HTTP status handling."""
        error = ClientError("Bad request", http_status=400)
        assert error.http_status == 400
        assert error.error_code == "CLIENT_ERROR"

    def test_invocation_error_original_exception(self):
        """Test InvocationError original exception handling."""
        original = ValueError("Original error")
        error = InvocationError("Agent failed", original_exception=original)
        assert error.original_exception == original
        assert error.error_code == "AGENT_ERROR"


class TestSelectApi:
    """Test suite for SelectApi."""

    def test_select_api_creation(self):
        """Test SelectApi creation with valid data."""
        api = SelectApi(api_title="User API", api_version="1.0")

        assert api.api_title == "User API"
        assert api.api_version == "1.0"

    def test_select_api_field_descriptions(self):
        """Test that SelectApi has proper field descriptions."""
        # Check that fields have descriptions
        title_field = SelectApi.model_fields["api_title"]
        version_field = SelectApi.model_fields["api_version"]

        assert title_field.description is not None
        assert version_field.description is not None
        assert "title" in title_field.description
        assert "version" in version_field.description

    def test_select_api_validation(self):
        """Test SelectApi validation."""
        # Should not raise any errors
        api = SelectApi(api_title="Product API", api_version="2.1")

        assert api.api_title == "Product API"
        assert api.api_version == "2.1"

    def test_select_api_empty_strings(self):
        """Test SelectApi with empty strings."""
        api = SelectApi(api_title="", api_version="")

        assert api.api_title == ""
        assert api.api_version == ""

    def test_select_api_special_characters(self):
        """Test SelectApi with special characters."""
        api = SelectApi(api_title="API-v1.2.3", api_version="beta-1.0")

        assert api.api_title == "API-v1.2.3"
        assert api.api_version == "beta-1.0"


class TestSelectedApis:
    """Test suite for SelectedApis."""

    def test_selected_apis_creation(self):
        """Test SelectedApis creation with valid data."""
        apis = [
            SelectApi(api_title="User API", api_version="1.0"),
            SelectApi(api_title="Product API", api_version="2.1"),
        ]

        selected_apis = SelectedApis(selected_apis=apis)

        assert len(selected_apis.selected_apis) == 2
        assert selected_apis.selected_apis[0].api_title == "User API"
        assert selected_apis.selected_apis[1].api_title == "Product API"

    def test_selected_apis_empty_list(self):
        """Test SelectedApis with empty list."""
        selected_apis = SelectedApis(selected_apis=[])

        assert len(selected_apis.selected_apis) == 0

    def test_selected_apis_default_factory(self):
        """Test SelectedApis default factory."""
        selected_apis = SelectedApis()

        assert len(selected_apis.selected_apis) == 0
        assert selected_apis.selected_apis == []

    def test_selected_apis_field_description(self):
        """Test that SelectedApis has proper field description."""
        # Check that the field has a description
        field = SelectedApis.model_fields["selected_apis"]

        assert field.description is not None
        assert "selected" in field.description.lower()
        assert "apis" in field.description.lower()

    def test_selected_apis_validation(self):
        """Test SelectedApis validation."""
        # Should not raise any errors
        apis = [SelectApi(api_title="Test API", api_version="1.0")]
        selected_apis = SelectedApis(selected_apis=apis)

        assert len(selected_apis.selected_apis) == 1
        assert selected_apis.selected_apis[0].api_title == "Test API"
