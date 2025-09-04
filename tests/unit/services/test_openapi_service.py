"""
Unit tests for OpenAPI service.

Tests the OpenAPIManager class functionality including loading API summaries
and OpenAPI specifications.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add src to path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src")
)

from nalai.services.openapi_service import OpenAPIManager


class TestOpenAPIManager:
    """Test suite for OpenAPIManager."""

    @pytest.fixture
    def openapi_manager(self):
        """Create OpenAPIManager instance for testing."""
        return OpenAPIManager()

    @pytest.fixture
    def temp_api_specs_dir(self):
        """Create temporary directory with test API specs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test API summaries
            api_summaries = [
                {
                    "title": "Test API 1",
                    "version": "1.0.0",
                    "description": "First test API",
                    "openapi_file": "test_api_1.yaml",
                },
                {
                    "title": "Test API 2",
                    "version": "2.0.0",
                    "description": "Second test API",
                    "openapi_file": "test_api_2.yaml",
                },
            ]

            summaries_file = os.path.join(temp_dir, "api_summaries.yaml")
            with open(summaries_file, "w", encoding="utf-8") as f:
                yaml.dump(api_summaries, f)

            # Create test OpenAPI specs
            openapi_spec_1 = {
                "openapi": "3.0.0",
                "info": {"title": "Test API 1", "version": "1.0.0"},
                "paths": {
                    "/users": {
                        "get": {
                            "summary": "Get users",
                            "responses": {"200": {"description": "Success"}},
                        }
                    }
                },
            }

            openapi_spec_2 = {
                "openapi": "3.0.0",
                "info": {"title": "Test API 2", "version": "2.0.0"},
                "paths": {
                    "/products": {
                        "get": {
                            "summary": "Get products",
                            "responses": {"200": {"description": "Success"}},
                        }
                    }
                },
            }

            spec_file_1 = os.path.join(temp_dir, "test_api_1.yaml")
            spec_file_2 = os.path.join(temp_dir, "test_api_2.yaml")

            with open(spec_file_1, "w", encoding="utf-8") as f:
                yaml.dump(openapi_spec_1, f)

            with open(spec_file_2, "w", encoding="utf-8") as f:
                yaml.dump(openapi_spec_2, f)

            yield temp_dir

    def test_load_api_summaries_success(self, openapi_manager, temp_api_specs_dir):
        """Test successful loading of API summaries."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            state = {}
            result = openapi_manager.load_api_summaries(state)

            assert "api_summaries" in result
            assert len(result["api_summaries"]) == 2
            assert result["api_summaries"][0]["title"] == "Test API 1"
            assert result["api_summaries"][1]["title"] == "Test API 2"

    def test_load_api_summaries_file_not_found(self, openapi_manager):
        """Test handling of missing API summaries file."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = "/nonexistent/path"

            state = {}
            with pytest.raises(FileNotFoundError, match="API summaries file not found"):
                openapi_manager.load_api_summaries(state)

    def test_load_api_summaries_preserves_existing_state(
        self, openapi_manager, temp_api_specs_dir
    ):
        """Test that existing state is preserved when loading API summaries."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            state = {"existing_key": "existing_value"}
            result = openapi_manager.load_api_summaries(state)

            assert result["existing_key"] == "existing_value"
            assert "api_summaries" in result

    def test_load_openapi_specifications_no_selected_apis(self, openapi_manager):
        """Test loading OpenAPI specs when no APIs are selected."""
        state = {"api_summaries": []}
        result = openapi_manager.load_openapi_specifications(state)

        assert result == state
        assert "api_specs" not in result

    def test_load_openapi_specifications_success(
        self, openapi_manager, temp_api_specs_dir
    ):
        """Test successful loading of OpenAPI specifications."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            # Mock selected APIs
            selected_api_1 = MagicMock()
            selected_api_1.api_title = "Test API 1"
            selected_api_1.api_version = "1.0.0"

            selected_api_2 = MagicMock()
            selected_api_2.api_title = "Test API 2"
            selected_api_2.api_version = "2.0.0"

            state = {
                "selected_apis": [selected_api_1, selected_api_2],
                "api_summaries": [
                    {
                        "title": "Test API 1",
                        "version": "1.0.0",
                        "openapi_file": "test_api_1.yaml",
                    },
                    {
                        "title": "Test API 2",
                        "version": "2.0.0",
                        "openapi_file": "test_api_2.yaml",
                    },
                ],
            }

            result = openapi_manager.load_openapi_specifications(state)

            assert "api_specs" in result
            assert len(result["api_specs"]) == 2
            assert result["api_specs"][0]["info"]["title"] == "Test API 1"
            assert result["api_specs"][1]["info"]["title"] == "Test API 2"

    def test_load_openapi_specifications_missing_openapi_file(
        self, openapi_manager, temp_api_specs_dir
    ):
        """Test handling when openapi_file is missing from API summary."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            selected_api = MagicMock()
            selected_api.api_title = "Test API 1"
            selected_api.api_version = "1.0.0"

            state = {
                "selected_apis": [selected_api],
                "api_summaries": [
                    {
                        "title": "Test API 1",
                        "version": "1.0.0",
                        # Missing openapi_file
                    }
                ],
            }

            result = openapi_manager.load_openapi_specifications(state)

            assert "api_specs" in result
            assert len(result["api_specs"]) == 0  # No specs loaded due to missing file

    def test_load_openapi_specifications_spec_file_not_found(
        self, openapi_manager, temp_api_specs_dir
    ):
        """Test handling when OpenAPI spec file doesn't exist."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            selected_api = MagicMock()
            selected_api.api_title = "Test API 1"
            selected_api.api_version = "1.0.0"

            state = {
                "selected_apis": [selected_api],
                "api_summaries": [
                    {
                        "title": "Test API 1",
                        "version": "1.0.0",
                        "openapi_file": "nonexistent.yaml",
                    }
                ],
            }

            result = openapi_manager.load_openapi_specifications(state)

            assert "api_specs" in result
            assert len(result["api_specs"]) == 0  # No specs loaded due to missing file

    def test_load_openapi_specifications_invalid_yaml(
        self, openapi_manager, temp_api_specs_dir
    ):
        """Test handling of invalid YAML in OpenAPI spec file."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            # Create invalid YAML file
            invalid_yaml_file = os.path.join(temp_api_specs_dir, "invalid.yaml")
            with open(invalid_yaml_file, "w", encoding="utf-8") as f:
                f.write("invalid: yaml: content: [")

            selected_api = MagicMock()
            selected_api.api_title = "Test API 1"
            selected_api.api_version = "1.0.0"

            state = {
                "selected_apis": [selected_api],
                "api_summaries": [
                    {
                        "title": "Test API 1",
                        "version": "1.0.0",
                        "openapi_file": "invalid.yaml",
                    }
                ],
            }

            result = openapi_manager.load_openapi_specifications(state)

            assert "api_specs" in result
            assert len(result["api_specs"]) == 0  # No specs loaded due to invalid YAML

    def test_load_openapi_specifications_preserves_existing_state(
        self, openapi_manager, temp_api_specs_dir
    ):
        """Test that existing state is preserved when loading OpenAPI specs."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            selected_api = MagicMock()
            selected_api.api_title = "Test API 1"
            selected_api.api_version = "1.0.0"

            state = {
                "existing_key": "existing_value",
                "selected_apis": [selected_api],
                "api_summaries": [
                    {
                        "title": "Test API 1",
                        "version": "1.0.0",
                        "openapi_file": "test_api_1.yaml",
                    }
                ],
            }

            result = openapi_manager.load_openapi_specifications(state)

            assert result["existing_key"] == "existing_value"
            assert "api_specs" in result

    def test_load_openapi_specifications_version_mismatch(
        self, openapi_manager, temp_api_specs_dir
    ):
        """Test handling when API version doesn't match summary."""
        with patch("nalai.services.openapi_service.settings") as mock_settings:
            mock_settings.api_specs_path = temp_api_specs_dir

            selected_api = MagicMock()
            selected_api.api_title = "Test API 1"
            selected_api.api_version = "2.0.0"  # Different version

            state = {
                "selected_apis": [selected_api],
                "api_summaries": [
                    {
                        "title": "Test API 1",
                        "version": "1.0.0",  # Different version
                        "openapi_file": "test_api_1.yaml",
                    }
                ],
            }

            result = openapi_manager.load_openapi_specifications(state)

            assert "api_specs" in result
            assert (
                len(result["api_specs"]) == 0
            )  # No specs loaded due to version mismatch

    def test_openapi_manager_implements_protocol(self, openapi_manager):
        """Test that OpenAPIManager implements the APIService protocol."""

        # Should not raise any errors when calling protocol methods
        state = {}
        openapi_manager.load_api_summaries(state)
        openapi_manager.load_openapi_specifications(state)

        # Verify it has the required methods (protocol compliance)
        assert hasattr(openapi_manager, "load_api_summaries")
        assert hasattr(openapi_manager, "load_openapi_specifications")
        assert callable(openapi_manager.load_api_summaries)
        assert callable(openapi_manager.load_openapi_specifications)
