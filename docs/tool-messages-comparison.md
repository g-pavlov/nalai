# Tool Messages and Content: OpenAI vs Our API

## Overview

Yes, OpenAI supports `"role": "tool"` in inputs, but there are significant differences in how each API handles tool-related messages and content.

## Tool Role Support

| **API** | **Tool Role Support** | **Notes** |
|---------|----------------------|-----------|
| **OpenAI API** | ✅ Supported in inputs | Can include tool messages in conversation history |
| **Our API** | ✅ Supported in inputs | Can include tool messages in conversation history |

## Tool Message Structure Comparison

### OpenAI's Tool Messages

OpenAI uses a **simple string-based approach** for tool message content:

```json
{
  "role": "tool",
  "content": "{\"temperature\": \"22°C\", \"condition\": \"Sunny\", \"humidity\": \"65%\"}"
}
```

**Key Characteristics:**
- `content` is a **stringified JSON**
- No explicit `tool_call_id` in the message structure
- Tool call correlation is implicit through conversation order

### Our API's Tool Messages

Our API uses a **structured array-based approach** for tool message content:

```json
{
  "type": "message",
  "role": "tool",
  "content": [
    {
      "type": "text",
      "text": "{\"temperature\": \"22°C\", \"condition\": \"Sunny\", \"humidity\": \"65%\"}"
    }
  ],
  "tool_call_id": "call_123"
}
```

**Key Characteristics:**
- `content` is an **array of ContentBlocks**
- Explicit `tool_call_id` field for correlation
- More structured and explicit approach

## Complete Tool Conversation Examples

### OpenAI API: Tool Conversation

```json
{
  "input": [
    {
      "role": "user",
      "content": "Get the weather for Paris"
    },
    {
      "role": "assistant",
      "content": "I'll get the weather information for Paris for you.",
      "tool_calls": [
        {
          "id": "call_123",
          "name": "get_weather",
          "args": {
            "city": "Paris",
            "country": "France"
          }
        }
      ]
    },
    {
      "role": "tool",
      "content": "{\"temperature\": \"22°C\", \"condition\": \"Sunny\", \"humidity\": \"65%\", \"wind_speed\": \"12 km/h\"}"
    }
  ]
}
```

### Our API: Tool Conversation

```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Get the weather for Paris"
        }
      ]
    },
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "I'll get the weather information for Paris for you."
        }
      ],
      "tool_calls": [
        {
          "id": "call_123",
          "name": "get_weather",
          "args": {
            "city": "Paris",
            "country": "France"
          },
          "type": "tool_call"
        }
      ]
    },
    {
      "type": "message",
      "role": "tool",
      "content": [
        {
          "type": "text",
          "text": "{\"temperature\": \"22°C\", \"condition\": \"Sunny\", \"humidity\": \"65%\", \"wind_speed\": \"12 km/h\"}"
        }
      ],
      "tool_call_id": "call_123"
    }
  ]
}
```

## Tool Call Structure Comparison

### OpenAI's Tool Calls

```json
{
  "id": "call_123",
  "name": "get_weather",
  "args": {
    "city": "Paris",
    "country": "France"
  }
}
```

**Characteristics:**
- No `type` field
- Simple structure with `id`, `name`, and `args`

### Our API's Tool Calls

```json
{
  "id": "call_123",
  "name": "get_weather",
  "args": {
    "city": "Paris",
    "country": "France"
  },
  "type": "tool_call"
}
```

**Characteristics:**
- Includes `type: "tool_call"` field
- More explicit and self-documenting

## Tool Call Correlation

### OpenAI's Approach

OpenAI relies on **implicit correlation** through conversation order:

1. Assistant message with `tool_calls` array
2. Tool message with stringified JSON content
3. Correlation is maintained by the order in the conversation

```json
[
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_123",
        "name": "get_weather",
        "args": {"city": "Paris"}
      }
    ]
  },
  {
    "role": "tool",
    "content": "{\"temperature\": \"22°C\"}"  // Implicitly correlates to call_123
  }
]
```

### Our API's Approach

Our API uses **explicit correlation** with `tool_call_id`:

```json
[
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_123",
        "name": "get_weather",
        "args": {"city": "Paris"},
        "type": "tool_call"
      }
    ]
  },
  {
    "role": "tool",
    "content": [
      {
        "type": "text",
        "text": "{\"temperature\": \"22°C\"}"
      }
    ],
    "tool_call_id": "call_123"  // Explicit correlation
  }
]
```

## Complex Tool Scenarios

### Multiple Tool Calls

#### OpenAI API
```json
{
  "input": [
    {
      "role": "user",
      "content": "Get weather for Paris and London"
    },
    {
      "role": "assistant",
      "content": "I'll get the weather for both cities.",
      "tool_calls": [
        {
          "id": "call_123",
          "name": "get_weather",
          "args": {"city": "Paris"}
        },
        {
          "id": "call_124",
          "name": "get_weather",
          "args": {"city": "London"}
        }
      ]
    },
    {
      "role": "tool",
      "content": "{\"temperature\": \"22°C\", \"condition\": \"Sunny\"}"
    },
    {
      "role": "tool",
      "content": "{\"temperature\": \"18°C\", \"condition\": \"Cloudy\"}"
    }
  ]
}
```

#### Our API
```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Get weather for Paris and London"
        }
      ]
    },
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "I'll get the weather for both cities."
        }
      ],
      "tool_calls": [
        {
          "id": "call_123",
          "name": "get_weather",
          "args": {"city": "Paris"},
          "type": "tool_call"
        },
        {
          "id": "call_124",
          "name": "get_weather",
          "args": {"city": "London"},
          "type": "tool_call"
        }
      ]
    },
    {
      "type": "message",
      "role": "tool",
      "content": [
        {
          "type": "text",
          "text": "{\"temperature\": \"22°C\", \"condition\": \"Sunny\"}"
        }
      ],
      "tool_call_id": "call_123"
    },
    {
      "type": "message",
      "role": "tool",
      "content": [
        {
          "type": "text",
          "text": "{\"temperature\": \"18°C\", \"condition\": \"Cloudy\"}"
        }
      ],
      "tool_call_id": "call_124"
    }
  ]
}
```

## Tool Decision Handling

### Our API: Structured Tool Decisions

Our API has a dedicated `ToolDecisionInput` type for handling tool decisions:

```json
{
  "input": [
    {
      "type": "tool_decision",
      "tool_call_id": "call_123",
      "decision": "accept"
    }
  ],
  "conversation_id": "conv_123"
}
```

### OpenAI API: Natural Language Tool Decisions

OpenAI relies on natural language for tool decisions:

```json
{
  "input": [
    {
      "role": "user",
      "content": "Accept the tool call"
    }
  ],
  "conversation_id": "conv_123"
}
```

## Pros and Cons Analysis

### OpenAI's Tool Message Approach

**Pros:**
- ✅ Simpler structure for tool messages
- ✅ Less verbose
- ✅ Familiar JSON string format
- ✅ Easier to parse tool results

**Cons:**
- ❌ Implicit tool call correlation
- ❌ No explicit `tool_call_id` in messages
- ❌ Relies on conversation order
- ❌ Harder to handle multiple tool calls out of order

### Our API's Tool Message Approach

**Pros:**
- ✅ Explicit tool call correlation with `tool_call_id`
- ✅ More structured and self-documenting
- ✅ Better for complex tool scenarios
- ✅ Consistent with overall message structure
- ✅ Dedicated tool decision types

**Cons:**
- ❌ More verbose for simple tool responses
- ❌ Requires array wrapper for content
- ❌ Steeper learning curve

## Real-World Impact

### Simple Tool Response

**OpenAI (Concise):**
```javascript
const toolMessage = {
  role: "tool",
  content: JSON.stringify({ result: "success", data: "123" })
};
```

**Our API (More Verbose):**
```javascript
const toolMessage = {
  type: "message",
  role: "tool",
  content: [
    {
      type: "text",
      text: JSON.stringify({ result: "success", data: "123" })
    }
  ],
  tool_call_id: "call_123"
};
```

### Complex Tool Scenario

**OpenAI (Implicit Correlation):**
```javascript
// Must maintain order: assistant -> tool -> tool
const conversation = [
  assistantMessageWithToolCalls,
  toolMessage1,  // Implicitly correlates to first tool call
  toolMessage2   // Implicitly correlates to second tool call
];
```

**Our API (Explicit Correlation):**
```javascript
// Can handle out-of-order tool responses
const conversation = [
  assistantMessageWithToolCalls,
  {
    role: "tool",
    tool_call_id: "call_124",  // Explicit correlation
    content: [...]
  },
  {
    role: "tool", 
    tool_call_id: "call_123",  // Can be out of order
    content: [...]
  }
];
```

## Recommendations

### For Our API

1. **Consider Optional String Content**: Allow string content for tool messages to reduce verbosity
2. **Maintain Explicit Correlation**: Keep `tool_call_id` for better tool call handling
3. **Add Tool Message Validation**: Ensure tool messages have corresponding tool calls

### For OpenAI Compatibility

1. **Support Implicit Correlation**: Handle tool messages without explicit `tool_call_id`
2. **Flexible Content Format**: Support both string and array content for tool messages
3. **Order-Based Correlation**: Maintain conversation order for tool call correlation

## Summary

Both APIs support tool roles in inputs, but with different approaches:

- **OpenAI**: Simple string-based content with implicit correlation
- **Our API**: Structured array-based content with explicit correlation

The choice depends on whether you prioritize simplicity (OpenAI) or explicitness (Our API) in tool handling.
