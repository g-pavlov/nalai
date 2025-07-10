#!/usr/bin/env python3
"""
Integration test for cache functionality against a running server.

This script tests the cache by making requests to a running API assistant server
and measuring response times to verify cache hits.
"""

import json
import time
import requests
from typing import Dict, Any, List


def test_cache_integration():
    """Test cache integration with a running server."""
    
    base_url = "http://localhost:8000"
    
    # Test prompts that should generate responses with content
    test_cases = [
        {
            "name": "API Information",
            "prompts": [
                "what APIs are available?",
                "tell me about the available APIs",
                "show me the API documentation"
            ]
        },
        {
            "name": "Product Operations", 
            "prompts": [
                "how do I create a product?",
                "what's the process for adding products?",
                "explain product creation"
            ]
        },
        {
            "name": "Different Intents",
            "prompts": [
                "what APIs are available?",
                "how do I create a product?",
                "what is authentication?"
            ]
        }
    ]
    
    def make_request(prompt: str) -> Dict[str, Any]:
        """Make a request to the API assistant."""
        payload = {
            "input": {
                "messages": [{"content": prompt, "type": "human"}]
            }
        }
        
        response = requests.post(
            f"{base_url}/api-assistant/invoke",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Request failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def test_cache_hits(test_case: Dict[str, Any]):
        """Test cache hits for a set of similar prompts."""
        print(f"\n🧪 Testing: {test_case['name']}")
        print("-" * 50)
        
        prompts = test_case["prompts"]
        times = []
        responses = []
        
        # Make requests and measure times
        for i, prompt in enumerate(prompts):
            print(f"Request {i+1}: {prompt}")
            
            start_time = time.time()
            response = make_request(prompt)
            request_time = time.time() - start_time
            
            times.append(request_time)
            responses.append(response)
            
            # Extract content from response
            if "output" in response and "messages" in response["output"] and response["output"]["messages"]:
                last_message = response["output"]["messages"][-1]
                content = last_message.get("content", "")
                has_tool_calls = bool(last_message.get("tool_calls"))
                
                print(f"  ⏱️  Time: {request_time:.3f}s")
                print(f"  📝 Content: {content[:100]}{'...' if len(content) > 100 else ''}")
                print(f"  🔧 Tool calls: {len(last_message.get('tool_calls', []))}")
                
                # Check if response has content (should be cached)
                if content and content.strip():
                    print(f"  ✅ Has content - will be cached")
                else:
                    print(f"  ⚠️  Empty content - won't be cached")
            else:
                print(f"  ❌ Invalid response format")
                print(f"  Response keys: {list(response.keys())}")
        
        # Analyze cache behavior
        print(f"\n📊 Cache Analysis:")
        
        if len(times) >= 2:
            first_time = times[0]
            subsequent_times = times[1:]
            
            print(f"  First request: {first_time:.3f}s")
            print(f"  Subsequent requests: {[f'{t:.3f}s' for t in subsequent_times]}")
            
            # Check for cache hits (subsequent requests should be faster)
            cache_hits = 0
            for i, time_taken in enumerate(subsequent_times):
                if time_taken < first_time * 0.8:  # 20% faster threshold
                    cache_hits += 1
                    print(f"  ✅ Request {i+2}: Cache hit detected ({time_taken:.3f}s < {first_time*0.8:.3f}s)")
                else:
                    print(f"  ❌ Request {i+2}: No cache hit ({time_taken:.3f}s >= {first_time*0.8:.3f}s)")
            
            print(f"  📈 Cache hit rate: {cache_hits}/{len(subsequent_times)} ({cache_hits/len(subsequent_times)*100:.1f}%)")
            
            return cache_hits, len(subsequent_times)
        
        return 0, 0
    
    def test_exact_cache_hits():
        """Test exact cache hits with identical prompts."""
        print(f"\n🎯 Testing Exact Cache Hits")
        print("-" * 50)
        
        prompt = "test exact cache hit"
        
        # First request
        print(f"First request: {prompt}")
        start_time = time.time()
        response1 = make_request(prompt)
        first_time = time.time() - start_time
        
        # Second request (should be exact cache hit)
        print(f"Second request: {prompt}")
        start_time = time.time()
        response2 = make_request(prompt)
        second_time = time.time() - start_time
        
        print(f"  First request time: {first_time:.3f}s")
        print(f"  Second request time: {second_time:.3f}s")
        
        # Check if responses are identical (cache hit)
        if "output" in response1 and "output" in response2:
            messages1 = response1["output"]["messages"]
            messages2 = response2["output"]["messages"]
            
            if messages1 and messages2:
                content1 = messages1[-1].get("content", "")
                content2 = messages2[-1].get("content", "")
                
                if content1 == content2 and second_time < first_time * 0.5:
                    print(f"  ✅ Exact cache hit working! Speedup: {first_time/second_time:.2f}x")
                    return True
                else:
                    print(f"  ❌ Exact cache hit not working. Speedup: {first_time/second_time:.2f}x")
                    return False
            else:
                print(f"  ❌ No messages in response")
                return False
        else:
            print(f"  ❌ Invalid response format")
            return False
    
    # Main test execution
    print("🚀 Starting Cache Integration Tests")
    print("=" * 60)
    
    try:
        # Check server health
        health_response = requests.get(f"{base_url}/healthz")
        if health_response.status_code != 200:
            print(f"❌ Server not healthy: {health_response.status_code}")
            return
        
        print("✅ Server is healthy and ready for testing")
        
        # Test exact cache hits
        exact_cache_working = test_exact_cache_hits()
        
        # Test similarity cache hits
        total_cache_hits = 0
        total_requests = 0
        
        for test_case in test_cases:
            hits, request_count = test_cache_hits(test_case)
            total_cache_hits += hits
            total_requests += request_count
        
        # Summary
        print(f"\n📋 Test Summary")
        print("=" * 60)
        print(f"Exact cache hits: {'✅ Working' if exact_cache_working else '❌ Not working'}")
        
        if total_requests > 0:
            hit_rate = total_cache_hits / total_requests * 100
            print(f"Similarity cache hits: {total_cache_hits}/{total_requests} ({hit_rate:.1f}%)")
            
            if hit_rate > 50:
                print("✅ Similarity caching working well")
            elif hit_rate > 20:
                print("⚠️  Similarity caching partially working")
            else:
                print("❌ Similarity caching not working well")
        else:
            print("⚠️  No similarity cache tests run")
        
        print(f"\n🎉 Cache integration test completed!")
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {base_url}")
        print("Make sure the server is running with: make serve")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")


if __name__ == "__main__":
    test_cache_integration() 