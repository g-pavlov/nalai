import os
import tempfile

import pytest

from src.api_assistant.prompts.prompts import MODEL_PROMPT_MAPPING, load_prompt_template


class TestLoadPromptTemplate:
    def test_load_prompt_template_success(self):
        # Create a temporary template file
        model_id = list(MODEL_PROMPT_MAPPING.keys())[0]
        variant = "call_model"
        prompt_type = "system_prompt"
        template_name = MODEL_PROMPT_MAPPING[model_id]
        template_filename = f"{prompt_type}_{template_name}_{variant}"
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = os.path.join(temp_dir, template_filename)
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("Test template content")
            # Should load successfully from custom path
            result = load_prompt_template(
                model_id, variant, prompt_type, custom_template_path=temp_dir
            )
            assert result == "Test template content"

    def test_load_prompt_template_file_not_found(self):
        model_id = list(MODEL_PROMPT_MAPPING.keys())[0]
        variant = "nonexistent_variant"
        prompt_type = "system_prompt"
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Prompt template file.*not found"):
                load_prompt_template(
                    model_id, variant, prompt_type, custom_template_path=temp_dir
                )

    def test_load_prompt_template_filename_logic(self):
        # Test that the filename is constructed as expected
        model_id = "llama3.1:8b"
        variant = "select_relevant_apis"
        prompt_type = "system_prompt"
        template_name = MODEL_PROMPT_MAPPING[model_id]
        expected_filename = f"{prompt_type}_{template_name}_{variant}"
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = os.path.join(temp_dir, expected_filename)
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("Llama template content")
            result = load_prompt_template(
                model_id, variant, prompt_type, custom_template_path=temp_dir
            )
            assert result == "Llama template content"
