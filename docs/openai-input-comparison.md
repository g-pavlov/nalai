# OpenAI vs Our API: Input Structure Comparison

## Top-Level Input Structure

| **Aspect** | **OpenAI API** | **Our API** | **Notes** |
|------------|----------------|-------------|-----------|
| **Field Name** | `"input"` | `"input"` | ✅ Identical |
| **String Input** | `"input": "plain text prompt"` | `"input": "plain text prompt"` | ✅ Identical |
| **Array Input** | `"input": [Message, ...]` | `"input": [MessageInputUnion, ...]` | ✅ Similar concept |
| **String Semantics** | Model interprets as user message | Converted to implicit human message | ✅ Identical behavior |

## Message Object Structure

| **Aspect** | **OpenAI API** | **Our API** | **Notes** |
|------------|----------------|-------------|-----------|
| **Role Types** | `"system" \| "user" \| "assistant" \| "tool"` | `"user" \| "assistant" \| "tool"` | ❌ Our API missing `"system"` |
| **Type Field** | Not present | `"type": "message"` (optional) | 🔄 Our API more explicit |
| **Content Structure** | `string \| ContentPart[]` | `ContentBlock[]` | 🔄 Different naming |

## Content Types Comparison

| **Content Type** | **OpenAI API** | **Our API** | **Support** |
|------------------|----------------|-------------|-------------|
| **Text** | `{ "type": "text", "text": "hello world" }` | `{ "type": "text", "text": "hello world" }` | ✅ Identical |
| **Image URL** | `{ "type": "image_url", "image_url": { "url": "..." } }` | ❌ Not supported | ❌ Missing in our API |
| **Image File ID** | `{ "type": "image_file", "file_id": "file_abc123" }` | ❌ Not supported | ❌ Missing in our API |
| **File Reference** | `{ "type": "input_file", "file_id": "file_def456" }` | ❌ Not supported | ❌ Missing in our API |
| **Audio Input** | `{ "type": "input_audio", "audio_url": { "url": "..." } }` | ❌ Not supported | ❌ Missing in our API |

## Tool Integration

| **Aspect** | **OpenAI API** | **Our API** | **Notes** |
|------------|----------------|-------------|-----------|
| **Tool Message Content** | `"content": "JSON string"` | `"content": [{"type": "text", "text": "JSON string"}]` | 🔄 Different structure |
| **Tool Call Type Field** | Not present | `"type": "tool_call"` | ✅ Our API more explicit |
| **Tool Call ID in Messages** | Not in message | `"tool_call_id": "..."` | ✅ Our API more explicit |

## Key Differences Summary

| **Aspect** | **OpenAI API** | **Our API** | **Impact** |
|------------|----------------|-------------|------------|
| **System Messages** | ✅ Supported | ❌ Not supported | Our API lacks system message support |
| **Multimodal Content** | ✅ Full support (text, image, file, audio) | ❌ Text only | Our API limited to text content |
| **Content Structure** | `string \| ContentPart[]` | `ContentBlock[]` | Different naming and structure |
| **Tool Message Content** | Stringified JSON | ContentBlock array | Different approach to tool responses |
| **Tool Call Type Field** | Not present | `"type": "tool_call"` | Our API more explicit |
| **Message Type Field** | Not present | `"type": "message"` (optional) | Our API more explicit |

## Missing Features in Our API

1. **System Messages** - Cannot set conversation context/instructions
2. **Multimodal Content** - Cannot handle images, files, or audio
3. **Simpler Content Structure** - Always requires ContentBlock array

## Strengths of Our API

1. **Explicit Type Fields** - More self-documenting
2. **Structured Content Blocks** - More extensible for future content types
3. **Tool Call ID in Messages** - Better correlation between tool calls and responses
