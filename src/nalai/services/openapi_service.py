"""
API service for managing API specifications and summaries.

This service handles loading and management of API specifications,
summaries, and related metadata.
"""

import logging
import os
from typing import Any

import yaml

from ..config import settings
from ..core.services import APIService as APIServiceProtocol

logger = logging.getLogger(__name__)


class OpenAPIManager(APIServiceProtocol):
    """Service for managing API operations."""

    def load_api_summaries(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Load API summaries from the configured data path.
        """
        summaries_file_path = os.path.join(
            settings.api_specs_path, "api_summaries.yaml"
        )

        if not os.path.exists(summaries_file_path):
            raise FileNotFoundError(
                f"API summaries file not found: {summaries_file_path}"
            )

        logger.debug(f"Loading API summaries from: {summaries_file_path}")
        with open(summaries_file_path, encoding="utf-8") as summaries_file:
            api_summaries = yaml.safe_load(summaries_file)
            state["api_summaries"] = api_summaries
            return state

    def load_openapi_specifications(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Load OpenAPI specifications for selected APIs.
        """
        selected_apis = state.get("selected_apis", [])
        if not selected_apis:
            return state

        api_summaries = state.get("api_summaries", [])
        loaded_api_specs = []

        for selected_api in selected_apis:
            api_title = selected_api.api_title
            api_version = selected_api.api_version

            # Find the corresponding API summary to get the openapi_file
            openapi_file_path = None
            for api_summary in api_summaries:
                if api_summary.get("title") == api_title and str(
                    api_summary.get("version")
                ) == str(api_version):
                    openapi_file_path = api_summary.get("openapi_file")
                    break

            if not openapi_file_path:
                logger.warning(f"No openapi_file found for {api_title} v{api_version}")
                continue

            spec_file_path = os.path.join(settings.api_specs_path, openapi_file_path)

            if not os.path.exists(spec_file_path):
                logger.error(f"API spec file not found: {spec_file_path}")
                continue

            logger.debug(f"Loading API spec from: {spec_file_path}")
            try:
                with open(spec_file_path, encoding="utf-8") as spec_file:
                    api_spec = yaml.safe_load(spec_file)
                    loaded_api_specs.append(api_spec)
            except Exception as error:
                logger.error(f"Failed to load API spec for {api_title}: {error}")

        state["api_specs"] = loaded_api_specs
        return state
