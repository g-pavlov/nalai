"""
Shared constants for the API Assistant package.

This module defines constants used across the package to ensure consistency
and prevent typos in node names, workflow actions, and other shared values.
"""

# Workflow node names (used for all node-related operations)
NODE_CHECK_CACHE = "check_cache"
NODE_LOAD_API_SUMMARIES = "load_api_summaries"
NODE_SELECT_RELEVANT_APIS = "select_relevant_apis"
NODE_LOAD_API_SPECS = "load_api_specs"
NODE_CALL_MODEL = "call_model"
NODE_CALL_API = "call_api"
NODE_HUMAN_REVIEW = "human_review"
