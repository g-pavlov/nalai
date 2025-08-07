"""
Prompts module for API Assistant.

Contains system prompts and prompt templates for different models.
"""

import os
from pathlib import Path

from .prompts import load_prompt_template


def get_system_prompt(model_name: str, prompt_type: str) -> str:
    """
    Get system prompt for a specific model and type.

    Args:
        model_name: Name of the model (e.g., 'anthropic-claude-3-5-sonnet', 'llama-4')
        prompt_type: Type of prompt ('call_model' or 'select_relevant_apis')

    Returns:
        The system prompt content
    """
    prompt_dir = Path(__file__).parent
    prompt_file = prompt_dir / f"system_prompt_{model_name}_{prompt_type}"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    with open(prompt_file, encoding="utf-8") as f:
        return f.read()


__all__ = [
    "get_system_prompt",
    "load_prompt_template",
]
