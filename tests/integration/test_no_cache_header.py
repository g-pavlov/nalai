#!/usr/bin/env python3
"""
Integration test for no-cache header functionality.

This script tests that the X-No-Cache header properly disables caching
for specific requests while keeping caching enabled for other requests.
"""

import time
from typing import Any

import pytest
import requests


@pytest.mark.integration
def test_no_cache_header():
    """Test that the X-No-Cache header properly disables caching."""

    base_url = "http://localhost:8000"
    timeout = 10  # 10 second timeout for requests

    def make_request(prompt: str, no_cache: bool = False) -> dict[str, Any]:
        """Make a request to the API assistant with optional no-cache header."""
        payload = {
            "input": {"messages": [{"content": prompt, "type": "human"}]},
            "config": {"model": {"name": "gpt-4.1", "platform": "openai"}},
        }

        headers = {"Content-Type": "application/json"}
        if no_cache:
            headers["X-No-Cache"] = "true"

        try:
            response = requests.post(
                f"{base_url}/nalai/invoke",
                json=payload,
                headers=headers,
                timeout=timeout,
            )

            if response.status_code != 200:
                raise Exception(
                    f"Request failed: {response.status_code} - {response.text}"
                )

            return response.json()
        except requests.exceptions.Timeout:
            pytest.skip(
                f"Server at {base_url} is not responding (timeout after {timeout}s)"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip(
                f"Cannot connect to server at {base_url}. Make sure the server is running with: make serve"
            )

    # Test prompt that should generate a response
    test_prompt = "what APIs are available?"

    print("\n🧪 Testing no-cache header functionality")
    print("-" * 50)

    # First request - should be cached (normal request)
    print(f"Request 1 (normal): {test_prompt}")
    start_time = time.time()
    response1 = make_request(test_prompt, no_cache=False)
    time1 = time.time() - start_time

    # Second request - should hit cache (normal request)
    print(f"Request 2 (normal): {test_prompt}")
    start_time = time.time()
    response2 = make_request(test_prompt, no_cache=False)
    time2 = time.time() - start_time

    # Third request - should bypass cache (no-cache header)
    print(f"Request 3 (no-cache): {test_prompt}")
    start_time = time.time()
    response3 = make_request(test_prompt, no_cache=True)
    time3 = time.time() - start_time

    # Fourth request - should hit cache again (normal request)
    print(f"Request 4 (normal): {test_prompt}")
    start_time = time.time()
    response4 = make_request(test_prompt, no_cache=False)
    time4 = time.time() - start_time

    print("\nResponse times:")
    print(f"Request 1 (normal): {time1:.2f}s")
    print(f"Request 2 (normal): {time2:.2f}s")
    print(f"Request 3 (no-cache): {time3:.2f}s")
    print(f"Request 4 (normal): {time4:.2f}s")

    # Verify that responses have content
    assert "output" in response1, "Response 1 missing output"
    assert "output" in response2, "Response 2 missing output"
    assert "output" in response3, "Response 3 missing output"
    assert "output" in response4, "Response 4 missing output"

    # Verify that the no-cache request took longer (indicating cache bypass)
    # The no-cache request should be slower than the cached requests
    assert time3 > time2, (
        f"No-cache request ({time3:.2f}s) should be slower than cached request ({time2:.2f}s)"
    )

    print("\n✅ No-cache header test passed!")
    print(f"   - Normal requests: {time1:.2f}s, {time2:.2f}s, {time4:.2f}s")
    print(f"   - No-cache request: {time3:.2f}s")
    print("   - Cache bypass confirmed: no-cache request was slower")


if __name__ == "__main__":
    # Run the test directly if called as script
    test_no_cache_header()
