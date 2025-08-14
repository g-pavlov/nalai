# No-Cache Feature

## Overview

The no-cache feature allows clients to bypass the LLM response cache for specific requests while keeping caching enabled for other requests. This is useful when you need fresh responses for time-sensitive queries or when you want to ensure the latest model behavior.

## How It Works

### Client-Side (UI)

The simple UI includes a "No Cache" toggle that sends the `X-No-Cache` header when enabled:

```javascript
// Check if no-cache is enabled
const noCacheToggle = document.getElementById('noCacheToggle');
const isNoCacheEnabled = noCacheToggle.checked;

// Include header in request
const response = await fetch(`${API_BASE_URL}/nalai/${endpoint}`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        ...(isNoCacheEnabled && { 'X-No-Cache': 'true' })
    },
    // ... rest of request
});
```

### Server-Side

The server processes the `X-No-Cache` header in the request pipeline:

1. **Header Processing**: The `add_no_cache_header_to_config()` function in `runtime_config.py` extracts the header value
2. **Configuration**: Sets `cache_disabled: true` in the request configuration when the header is present
3. **Cache Bypass**: The agent checks this setting and skips cache lookup and storage when disabled

### Cache Behavior

When the no-cache header is present:

- **Cache Lookup**: Skipped - the agent proceeds directly to model invocation
- **Cache Storage**: Skipped - responses are not stored in cache
- **Logging**: Debug messages indicate cache bypass

## Usage

### Web UI

1. Open the nalAI web interface
2. Toggle the "No Cache" switch to ON
3. Send your message - it will bypass the cache
4. Toggle back to OFF for normal cached behavior

### API Usage

```bash
# Normal request (uses cache)
curl -X POST http://localhost:8000/nalai/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"messages": [{"content": "what APIs are available?", "type": "human"}]},
    "config": {"model": {"name": "gpt-4.1", "platform": "openai"}}
  }'

# No-cache request (bypasses cache)
curl -X POST http://localhost:8000/nalai/invoke \
  -H "Content-Type: application/json" \
  -H "X-No-Cache: true" \
  -d '{
    "input": {"messages": [{"content": "what APIs are available?", "type": "human"}]},
    "config": {"model": {"name": "gpt-4.1", "platform": "openai"}}
  }'
```

## Header Values

The `X-No-Cache` header accepts these values (case-insensitive):

- `"true"` - Disable cache for this request
- `"1"` - Disable cache for this request  
- `"yes"` - Disable cache for this request
- Any other value or missing header - Use normal cache behavior

## Implementation Details

### Files Modified

1. **`demo/ui/ai-chat.html`**
   - Added no-cache toggle switch
   - Added JavaScript to send header
   - Added status indicator

2. **`src/nalai/server/runtime_config.py`**
   - Added `add_no_cache_header_to_config()` function
   - Updated `default_modify_runtime_config()` to include header processing

3. **`src/nalai/core/agent.py`**
   - Updated `check_cache_with_similarity()` to check `cache_disabled` setting
   - Updated `generate_model_response()` to skip cache storage when disabled

### Configuration Flow

```
Request with X-No-Cache header
    ↓
runtime_config.py: add_no_cache_header_to_config()
    ↓
Sets configurable["cache_disabled"] = true
    ↓
agent.py: check_cache_with_similarity()
    ↓
Skips cache lookup when cache_disabled is true
    ↓
agent.py: generate_model_response()
    ↓
Skips cache storage when cache_disabled is true
```

## Testing

Run the integration test to verify functionality:

```bash
# Run the no-cache test
python tests/integration/test_no_cache_header.py

# Or run all integration tests
make test-integration
```

The test verifies that:
1. Normal requests use cache (faster subsequent requests)
2. No-cache requests bypass cache (slower, fresh responses)
3. Cache behavior resumes after no-cache requests

## Benefits

- **Fresh Responses**: Get latest model behavior when needed
- **Selective Control**: Choose per-request whether to use cache
- **Performance**: Maintain cache benefits for most requests
- **Debugging**: Easily test without cache interference
- **Time-Sensitive Data**: Bypass cache for real-time information needs 