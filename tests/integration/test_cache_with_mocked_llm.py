#!/usr/bin/env python3
"""
Reliable unit test for caching functionality with mocked LLM responses.
Uses a simple mock chat model that always returns non-empty responses.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import time
import unittest
from unittest.mock import patch
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from src.api_assistant.server.app import app
from src.api_assistant.core.schemas import SelectedApis, SelectApi

class SimpleMockChatModel(BaseChatModel):
    """Simple mock chat model that always returns a non-empty response."""
    
    def __init__(self):
        super().__init__()
        self.metadata = {
            "context_window": 32000,
            "model_id": "test-model",
            "model_platform": "test",
            "messages_token_count_supported": True,
        }
        self._structured_output_schema = None
    
    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        """Generate a response - always returns the same non-empty content."""
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content="This is a cached answer from the mock LLM.")
                )
            ]
        )
    
    def with_structured_output(self, schema):
        """Return a mock that returns structured output."""
        mock_with_structured = SimpleMockChatModel()
        mock_with_structured._structured_output_schema = schema
        mock_with_structured.metadata = self.metadata
        
        # Override _generate to return structured output
        def _generate_structured(messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
            if schema == SelectedApis:
                # Return an AIMessage with selected_apis attribute
                mock_message = AIMessage(content="")
                # Add selected_apis as an attribute
                mock_message.selected_apis = []
                return ChatResult(
                    generations=[
                        ChatGeneration(
                            message=mock_message
                        )
                    ]
                )
            else:
                # Fallback to regular AIMessage
                return ChatResult(
                    generations=[
                        ChatGeneration(
                            message=AIMessage(content="Structured response from mock LLM.")
                        )
                    ]
                )
        
        mock_with_structured._generate = _generate_structured
        return mock_with_structured
    
    def bind_tools(self, tools):
        """Return self to handle tool binding requests."""
        return self
    
    @property
    def _llm_type(self) -> str:
        return "mock"

class TestCacheWithMockedLLM(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _make_request(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "input": {
                "messages": [{"content": prompt, "type": "human"}]
            }
        }
        response = self.client.post("/api-assistant/invoke", json=payload)
        return response.json()

    @patch('src.api_assistant.services.model_service.ModelService.get_model_from_config')
    def test_cache_hit_with_mocked_content(self, mock_get_model):
        # Create a simple mock chat model
        mock_model = SimpleMockChatModel()
        mock_get_model.return_value = mock_model
        
        prompt = "What is the capital of France?"
        
        # First request (should go through full workflow)
        start_time = time.time()
        response1 = self._make_request(prompt)
        first_time = time.time() - start_time
        
        # Second request (should be a cache hit)
        start_time = time.time()
        response2 = self._make_request(prompt)
        second_time = time.time() - start_time

        # Parse content from response
        def get_content(resp):
            msgs = resp.get("output", {}).get("messages", [])
            return msgs[-1]["content"] if msgs else None
        
        content1 = get_content(response1)
        content2 = get_content(response2)

        # Verify both responses have the expected content
        self.assertEqual(content1, "This is a cached answer from the mock LLM.")
        self.assertEqual(content2, "This is a cached answer from the mock LLM.")
        
        # Verify cache hit is much faster (should be at least 50% faster)
        self.assertLess(second_time, first_time * 0.5, 
                       f"Cache hit should be faster. First: {first_time:.3f}s, Second: {second_time:.3f}s")

if __name__ == "__main__":
    unittest.main(argv=[''], exit=False, verbosity=2) 