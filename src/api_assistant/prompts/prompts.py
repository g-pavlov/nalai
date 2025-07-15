"""Default prompts utilities used by agents."""

import os
from typing import Literal

# Model ID to prompt template mapping
MODEL_PROMPT_MAPPING = {
    "anthropic.claude-3-5-sonnet-20240620-v1:0": "large",
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0": "large",
    "gpt-4.1": "large",
    "gpt-4o": "large",
    "gpt-4o-mini": "large",
    "gpt-3.5-turbo": "large",
    "llama3.1:8b": "llama-small",
    "llama3-groq-tool-use:8b": "llama-small",
}

# Supported model IDs
SUPPORTED_MODEL_IDS = Literal[
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-3.5-turbo",
    "llama3.1:8b",
    "llama3-groq-tool-use:8b",
]

# Supported prompt types
SUPPORTED_PROMPT_TYPES = Literal["system_prompt"]


def load_prompt_template(
    model_id: SUPPORTED_MODEL_IDS,
    variant: str,
    prompt_type: SUPPORTED_PROMPT_TYPES = "system_prompt",
    custom_template_path: str = None,
) -> str:
    """
    Load a prompt template file based on model ID and variant.
    Args:
        model_id: The model identifier
        variant: The prompt variant (e.g., 'call_model', 'select_relevant_apis')
        prompt_type: The type of prompt (default: 'system_prompt')
        custom_template_path: Optional custom path to template directory
    Returns:
        The prompt template content as a string
    Raises:
        ValueError: If the prompt template file is not found
    """
    # Get the prompt template name for the model
    template_name = MODEL_PROMPT_MAPPING.get(model_id, model_id)

    # Create the filename based on convention
    template_filename = f"{prompt_type}_{template_name}_{variant}"

    # Determine the template file path
    if custom_template_path:
        template_file_path = os.path.join(custom_template_path, template_filename)
    else:
        # Get the directory of this file and look in templates subdirectory
        current_directory = os.path.dirname(os.path.abspath(__file__))
        template_file_path = os.path.join(
            current_directory, "templates", template_filename
        )

    # Try to open and read the template file
    try:
        with open(template_file_path, encoding="utf-8") as template_file:
            template_content = template_file.read()
        return template_content
    except FileNotFoundError:
        raise ValueError(
            f"Prompt template file '{template_filename}' not found at '{template_file_path}'"
        ) from None


# Backward compatibility alias
load_prompt = load_prompt_template


def format_template_with_variables(template_string: str, **variables) -> str:
    """Format template string with variables, handling nested braces.
    Safely replaces template variables while preserving literal braces
    in the template content.
    Args:
        template_string: Template with {variable} placeholders
        **variables: Variables to substitute
    Returns:
        str: Formatted template with variables replaced
    """
    import re

    placeholder_map = {}
    for key in variables:
        token = f"__PLACEHOLDER_{key.upper()}__"
        placeholder_map[token] = key
        template_string = re.sub(rf"{{\s*{re.escape(key)}\s*}}", token, template_string)

    # Escape all remaining braces
    template_string = template_string.replace("{", "{{").replace("}", "}}")

    # Restore placeholders to {variable}
    for token, key in placeholder_map.items():
        template_string = template_string.replace(token, f"{{{key}}}")

    # Now .format() will only substitute {variable}, all other braces are safe
    formatted_string = template_string.format(**variables)

    # DO NOT unescape all braces at the end!
    return formatted_string
