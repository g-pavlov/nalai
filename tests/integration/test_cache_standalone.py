#!/usr/bin/env python3
"""
Standalone test script for cache service and similarity search.
Tests the cache functionality independently of the main workflow.
"""

import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from langchain_core.messages import HumanMessage

from nalai.services.cache_service import (
    CacheService,
    TokenSimilarityMatcher,
)


def test_similarity_matcher():
    """Test the token-based similarity matcher."""
    print("=== Testing TokenSimilarityMatcher ===")

    matcher = TokenSimilarityMatcher()

    # Test exact matches
    print("\n1. Exact matches:")
    similarity = matcher.similarity("create product", "create product")
    print(f"  'create product' vs 'create product': {similarity:.3f}")
    assert similarity == 1.0

    # Test similar intents with articles
    print("\n2. Similar intents with articles:")
    test_cases = [
        ("create product", "create a product"),
        ("create product", "create the product"),
        ("list products", "list all products"),
        ("get user", "get a user"),
    ]

    for intent1, intent2 in test_cases:
        similarity = matcher.similarity(intent1, intent2)
        print(f"  '{intent1}' vs '{intent2}': {similarity:.3f}")
        assert similarity > 0.7  # Should be quite similar

    # Test different intents
    print("\n3. Different intents:")
    test_cases = [
        ("create product", "list products"),
        ("create product", "delete product"),
        ("get user", "create order"),
    ]

    for intent1, intent2 in test_cases:
        similarity = matcher.similarity(intent1, intent2)
        print(f"  '{intent1}' vs '{intent2}': {similarity:.3f}")
        assert similarity < 0.6  # Should be less similar

    # Test semantic opposites (should return 0.0)
    print("\n4. Semantic opposites:")
    test_cases = [
        ("create product", "delete product"),
        ("add user", "remove user"),
        ("enable feature", "disable feature"),
    ]

    for intent1, intent2 in test_cases:
        similarity = matcher.similarity(intent1, intent2)
        print(f"  '{intent1}' vs '{intent2}': {similarity:.3f}")
        assert similarity == 0.0  # Should be detected as opposites

    print("\n✅ All similarity matcher tests passed!")


def test_cache_service():
    """Test the cache service functionality."""
    print("\n=== Testing CacheService ===")

    cache_service = CacheService(max_size=5, default_ttl_hours=1)

    # Test basic get/set
    print("\n1. Basic get/set operations:")
    messages = [HumanMessage(content="create a product")]
    response = "Product created successfully"
    tool_calls = [{"name": "create_product", "args": {"name": "Test Product"}}]

    # Set cache entry
    cache_service.set(messages, response, tool_calls)
    print(f"  Cached response for messages: '{messages[0].content}'")

    # Get cache entry
    result = cache_service.get(messages)
    assert result is not None
    cached_response, cached_tool_calls = result
    print(f"  Retrieved response: '{cached_response}'")
    print(f"  Retrieved tool calls: {cached_tool_calls}")
    assert cached_response == response
    assert cached_tool_calls == tool_calls

    # Test cache miss
    print("\n2. Cache miss test:")
    result = cache_service.get([HumanMessage(content="different intent")])
    assert result is None
    print("  Cache miss for different intent (expected)")

    # Test similarity search
    print("\n3. Similarity search test:")
    # Add some test entries
    cache_service.set([HumanMessage(content="create a product")], "Product created")
    cache_service.set([HumanMessage(content="create the product")], "Product created")
    cache_service.set([HumanMessage(content="list products")], "Products listed")

    # Find similar responses
    similar = cache_service.find_similar_cached_responses("create a product")
    print(f"  Found {len(similar)} similar responses for 'create a product':")
    for message_content, _response, _tool_calls, similarity in similar:
        print(f"    - '{message_content}' (similarity: {similarity:.3f}): '{response}'")

    # Should find at least the exact match "create product"
    assert len(similar) >= 1
    messages = [msg for msg, _, _, _ in similar]
    assert "create a product" in messages

    # Test with lower threshold to see more matches
    similar_lower = cache_service.find_similar_cached_responses(
        "create a product", similarity_threshold=0.5
    )
    print(
        f"  With lower threshold (0.5), found {len(similar_lower)} similar responses:"
    )
    for message_content, _response, _tool_calls, similarity in similar_lower:
        print(f"    - '{message_content}' (similarity: {similarity:.3f}): '{response}'")

    # Test cache size limit
    print("\n4. Cache size limit test:")
    for i in range(10):  # More than max_size (5)
        cache_service.set([HumanMessage(content=f"request {i}")], f"response {i}")

    print(f"  Cache size after adding 10 entries: {len(cache_service._cache)}")
    assert len(cache_service._cache) <= 5  # Should not exceed max size

    # Test cache statistics
    print("\n5. Cache statistics:")
    stats = cache_service.get_stats()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Total hits: {stats['total_hits']}")
    print(f"  Max size: {stats['max_size']}")

    # Test cache clearing
    print("\n6. Cache clearing:")
    cache_service.clear()
    assert len(cache_service._cache) == 0
    print("  Cache cleared successfully")

    print("\n✅ All cache service tests passed!")


def test_cache_hit_and_miss():
    """Test explicit cache hit and cache miss scenarios."""
    print("\n=== Testing Cache Hit and Miss ===")
    cache_service = CacheService(max_size=3, default_ttl_hours=1)

    # Cache a response
    messages = [HumanMessage(content="create a product")]
    response = "Product created successfully"
    cache_service.set(messages, response)
    print("  Cached response for 'create a product'.")

    # Test cache hit
    hit = cache_service.get(messages)
    if hit:
        print("  ✅ Cache hit: got response:", hit[0])
        assert hit[0] == response
    else:
        print("  ❌ Cache miss (unexpected)!")
        raise AssertionError()

    # Test cache miss (different messages)
    miss = cache_service.get([HumanMessage(content="add a product")])
    if miss is None:
        print("  ✅ Cache miss for different messages (expected).")
    else:
        print("  ❌ Unexpected cache hit for different messages!")
        raise AssertionError()

    print("✅ Cache hit and miss tests passed!\n")


def test_cache_with_real_scenarios():
    """Test cache with realistic scenarios."""
    print("\n=== Testing Real Scenarios ===")

    cache_service = CacheService(max_size=10, default_ttl_hours=1)

    # Scenario 1: User asks to create a product
    print("\n1. Scenario: Create a product")
    messages1 = [HumanMessage(content="create a product")]
    response1 = "I'll help you create a product. Here's how to do it..."

    cache_service.set(messages1, response1)
    print(f"  Cached response for: '{messages1[0].content}'")

    # Scenario 2: User asks the same thing with different phrasing
    print("\n2. Scenario: Same request, different phrasing")
    messages2 = [HumanMessage(content="generate a product")]

    result = cache_service.get(messages2)
    if result:
        print("  ✅ Cache hit! Found exact match")
    else:
        print("  ❌ Cache miss (expected since message is different)")

    # Scenario 3: Similar request with similarity search
    print("\n3. Scenario: Similar request with similarity search")
    messages3 = [HumanMessage(content="create a new product")]
    response3 = "I'll help you create a new product. Here's how..."
    cache_service.set(messages3, response3)

    # Now search for similar responses
    similar = cache_service.find_similar_cached_responses("create a product")
    print(f"  Found {len(similar)} similar responses for 'create a product':")
    for message_content, _response, _tool_calls, similarity in similar:
        print(f"    - '{message_content}' (similarity: {similarity:.3f})")

    # Scenario 4: Test cache hit counting
    print("\n4. Scenario: Cache hit counting")
    for _ in range(3):
        cache_service.get(messages1)

    intent_key = cache_service._extract_intent_key(messages1[0].content)
    entry = cache_service._cache[intent_key]
    print(f"  Cache entry hit count: {entry.hit_count}")
    assert entry.hit_count == 3

    print("\n✅ All real scenario tests passed!")


def main():
    """Run all cache tests."""
    print("🧪 Testing Cache Service and Similarity Search")
    print("=" * 50)

    try:
        test_similarity_matcher()
        test_cache_service()
        test_cache_hit_and_miss()
        test_cache_with_real_scenarios()

        print("\n" + "=" * 50)
        print("🎉 All tests passed! Cache service is working correctly.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
