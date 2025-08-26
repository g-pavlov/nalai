# Input Formats: Side-by-Side Comparison

This document provides a direct side-by-side comparison of input formats between our `/api/v1/responses` API and Mistral's Beta Conversations API.

## Table of Contents

1. [Basic String Input](#basic-string-input)
2. [Structured Message Input](#structured-message-input)
3. [Tool Calls](#tool-calls)
4. [Tool Decisions](#tool-decisions)
5. [Conversation Management](#conversation-management)
6. [Model Configuration](#model-configuration)
7. [Complete Request Examples](#complete-request-examples)

## Basic String Input

### Simple String Input

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Hello, how can you help me?",<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": "Hello, how can you help me?"<br>}``` |

### String Input with Model

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Explain quantum computing",<br>  "model": "openai/gpt-4",<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "model": "mistral-large-latest",<br>  "inputs": "Explain quantum computing"<br>}``` |

### String Input with Settings

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Write a creative story",<br>  "model": "ollama/llama3.1:8b",<br>  "model_settings": {<br>    "temperature": 0.8,<br>    "max_tokens": 200<br>  },<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "model": "mistral-large-latest",<br>  "inputs": "Write a creative story",<br>  "completionArgs": {<br>    "temperature": 0.8,<br>    "max_tokens": 200<br>  }<br>}``` |

## Structured Message Input

### Single Human Message

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "message",<br>      "role": "user",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "What's the weather like?"<br>        }<br>      ]<br>    }<br>  ],<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": [<br>    {<br>      "role": "user",<br>      "content": "What's the weather like?",<br>      "object": "entry",<br>      "type": "message.input"<br>    }<br>  ]<br>}``` |

### Multiple Content Blocks

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "message",<br>      "role": "user",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "Please analyze this data: "<br>        },<br>        {<br>          "type": "text",<br>          "text": "Sales increased by 15% in Q3"<br>        }<br>      ]<br>    }<br>  ],<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": [<br>    {<br>      "role": "user",<br>      "content": "Please analyze this data: Sales increased by 15% in Q3",<br>      "object": "entry",<br>      "type": "message.input"<br>    }<br>  ]<br>}``` |

### AI Message with Tool Calls

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "message",<br>      "role": "assistant",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "I'll help you update the product."<br>        }<br>      ],<br>      "tool_calls": [<br>        {<br>          "id": "call_123",<br>          "name": "put_http_requests",<br>          "args": {<br>            "url": "http://api.example.com/products/123",<br>            "input_data": {<br>              "name": "Updated Product",<br>              "price": 29.99<br>            }<br>          },<br>          "type": "tool_call"<br>        }<br>      ]<br>    }<br>  ],<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": [<br>    {<br>      "role": "assistant",<br>      "content": "I'll help you update the product.",<br>      "object": "entry",<br>      "type": "message.output",<br>      "tool_calls": [<br>        {<br>          "id": "call_123",<br>          "name": "put_http_requests",<br>          "args": {<br>            "url": "http://api.example.com/products/123",<br>            "input_data": {<br>              "name": "Updated Product",<br>              "price": 29.99<br>            }<br>          }<br>        }<br>      ]<br>    }<br>  ]<br>}``` |

### Tool Message Response

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "message",<br>      "role": "tool",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "{\"id\": \"123\", \"name\": \"Updated Product\", \"price\": 29.99, \"updated\": true}"<br>        }<br>      ],<br>      "tool_call_id": "call_123"<br>    }<br>  ],<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": [<br>    {<br>      "role": "tool",<br>      "content": "{\"id\": \"123\", \"name\": \"Updated Product\", \"price\": 29.99, \"updated\": true}",<br>      "object": "entry",<br>      "type": "tool.execution.done",<br>      "tool_call_id": "call_123"<br>    }<br>  ]<br>}``` |

## Tool Calls

### Tool Call Structure

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "id": "call_123",<br>  "name": "get_http_requests",<br>  "args": {<br>    "url": "http://api.example.com/data"<br>  },<br>  "type": "tool_call"<br>}``` | ```json<br>{<br>  "id": "call_123",<br>  "name": "websearch",<br>  "args": {<br>    "query": "latest AI news"<br>  }<br>}``` |

### Tool Call in Message

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "type": "message",<br>  "role": "assistant",<br>  "content": [<br>    {<br>      "type": "text",<br>      "text": "I'll search for that information."<br>    }<br>  ],<br>  "tool_calls": [<br>    {<br>      "id": "call_456",<br>      "name": "get_http_requests",<br>      "args": {<br>        "url": "http://api.example.com/search?q=AI+news"<br>      },<br>      "type": "tool_call"<br>    }<br>  ]<br>}``` | ```json<br>{<br>  "role": "assistant",<br>  "content": "I'll search for that information.",<br>  "object": "entry",<br>  "type": "message.output",<br>  "tool_calls": [<br>    {<br>      "id": "call_456",<br>      "name": "websearch",<br>      "args": {<br>        "query": "AI news"<br>      }<br>    }<br>  ]<br>}``` |

## Tool Decisions

### Accept Tool Call

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "tool_decision",<br>      "tool_call_id": "call_123",<br>      "decision": "accept"<br>    }<br>  ],<br>  "conversation_id": "conv_123",<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "conversation_id": "conv_123",<br>  "inputs": [<br>    {<br>      "role": "user",<br>      "content": "Accept the tool call",<br>      "object": "entry",<br>      "type": "message.input"<br>    }<br>  ]<br>}``` |

### Reject Tool Call

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "tool_decision",<br>      "tool_call_id": "call_123",<br>      "decision": "reject",<br>      "message": "I don't want to proceed"<br>    }<br>  ],<br>  "conversation_id": "conv_123",<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "conversation_id": "conv_123",<br>  "inputs": [<br>    {<br>      "role": "user",<br>      "content": "I don't want to proceed with this action",<br>      "object": "entry",<br>      "type": "message.input"<br>    }<br>  ]<br>}``` |

### Edit Tool Call

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "tool_decision",<br>      "tool_call_id": "call_123",<br>      "decision": "edit",<br>      "args": {<br>        "url": "http://api.example.com/products/456",<br>        "input_data": {<br>          "name": "Modified Product",<br>          "price": 39.99<br>        }<br>      }<br>    }<br>  ],<br>  "conversation_id": "conv_123",<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "conversation_id": "conv_123",<br>  "inputs": [<br>    {<br>      "role": "user",<br>      "content": "Please modify the tool call to use product ID 456 with price 39.99",<br>      "object": "entry",<br>      "type": "message.input"<br>    }<br>  ]<br>}``` |

## Conversation Management

### New Conversation

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Start a new conversation",<br>  "conversation_id": null,<br>  "store": true,<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": "Start a new conversation"<br>}``` |

### Continue Conversation

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Continue the conversation",<br>  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",<br>  "store": true,<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "conversation_id": "conv_456",<br>  "inputs": "Continue the conversation"<br>}``` |

### Branch from Response/Entry

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Try a different approach",<br>  "conversation_id": "conv_123",<br>  "previous_response_id": "resp_789",<br>  "store": true,<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "conversation_id": "conv_123",<br>  "from_entry_id": "entry_789",<br>  "inputs": "Try a different approach"<br>}``` |

### Ephemeral Conversation

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Temporary question",<br>  "conversation_id": "conv_123",<br>  "store": false,<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "conversation_id": "conv_123",<br>  "inputs": "Temporary question",<br>  "store": false<br>}``` |

## Model Configuration

### Using Agent

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Hello",<br>  "stream": "off"<br>}<br>// Agent configured in system``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": "Hello"<br>}``` |

### Using Model Directly

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Hello",<br>  "model": "openai/gpt-4",<br>  "stream": "off"<br>}<br>// Tools configured in agent``` | ```json<br>{<br>  "model": "mistral-large-latest",<br>  "inputs": "Hello",<br>  "tools": [<br>    {<br>      "type": "websearch",<br>      "name": "websearch"<br>    }<br>  ]<br>}``` |

### Model with Settings

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "Generate a story",<br>  "model": "ollama/llama3.1:8b",<br>  "model_settings": {<br>    "temperature": 0.9,<br>    "max_tokens": 500<br>  },<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "model": "mistral-large-latest",<br>  "inputs": "Generate a story",<br>  "completionArgs": {<br>    "temperature": 0.9,<br>    "max_tokens": 500<br>  }<br>}``` |

## Complete Request Examples

### E-commerce Integration

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "message",<br>      "role": "user",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "I need to manage my inventory"<br>        }<br>      ]<br>    },<br>    {<br>      "type": "message",<br>      "role": "assistant",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "I can help you manage your inventory!"<br>        }<br>      ],<br>      "tool_calls": [<br>        {<br>          "id": "call_inventory_1",<br>          "name": "get_http_requests",<br>          "args": {<br>            "url": "http://api.example.com/inventory"<br>          },<br>          "type": "tool_call"<br>        }<br>      ]<br>    },<br>    {<br>      "type": "message",<br>      "role": "tool",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "{\"products\": [...]}"<br>        }<br>      ],<br>      "tool_call_id": "call_inventory_1"<br>    },<br>    {<br>      "type": "message",<br>      "role": "user",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "Update Widget stock to 75 units"<br>        }<br>      ]<br>    }<br>  ],<br>  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",<br>  "model": "openai/gpt-4",<br>  "model_settings": {<br>    "temperature": 0.1<br>  },<br>  "store": true,<br>  "disable_cache": false,<br>  "stream": "off"<br>}``` | ```json<br>{<br>  "agent_id": "agent_123",<br>  "inputs": [<br>    {<br>      "role": "user",<br>      "content": "I need to manage my inventory",<br>      "object": "entry",<br>      "type": "message.input"<br>    },<br>    {<br>      "role": "assistant",<br>      "content": "I can help you manage your inventory!",<br>      "object": "entry",<br>      "type": "message.output",<br>      "tool_calls": [<br>        {<br>          "id": "call_inventory_1",<br>          "name": "get_inventory",<br>          "args": {}<br>        }<br>      ]<br>    },<br>    {<br>      "role": "tool",<br>      "content": "{\"products\": [...]}",<br>      "object": "entry",<br>      "type": "tool.execution.done",<br>      "tool_call_id": "call_inventory_1"<br>    },<br>    {<br>      "role": "user",<br>      "content": "Update Widget stock to 75 units",<br>      "object": "entry",<br>      "type": "message.input"<br>    }<br>  ]<br>}``` |

### Customer Support Chat

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": "I'm having trouble with my account login",<br>  "conversation_id": "support-chat-123",<br>  "model": "openai/gpt-4",<br>  "model_settings": {<br>    "temperature": 0.7,<br>    "max_tokens": 300<br>  },<br>  "store": true,<br>  "stream": "full"<br>}``` | ```json<br>{<br>  "agent_id": "support_agent",<br>  "inputs": "I'm having trouble with my account login",<br>  "completionArgs": {<br>    "temperature": 0.7,<br>    "max_tokens": 300<br>  },<br>  "stream": true<br>}``` |

### Data Analysis Request

| **Our API** | **Mistral API** |
|-------------|-----------------|
| ```json<br>{<br>  "input": [<br>    {<br>      "type": "message",<br>      "role": "user",<br>      "content": [<br>        {<br>          "type": "text",<br>          "text": "Analyze this sales data and provide insights"<br>        }<br>      ]<br>    }<br>  ],<br>  "model": "aws_bedrock/claude-3-sonnet",<br>  "model_settings": {<br>    "temperature": 0.2,<br>    "max_tokens": 800<br>  },<br>  "store": false,<br>  "disable_cache": true,<br>  "stream": "events"<br>}``` | ```json<br>{<br>  "model": "mistral-large-latest",<br>  "inputs": [<br>    {<br>      "role": "user",<br>      "content": "Analyze this sales data and provide insights",<br>      "object": "entry",<br>      "type": "message.input"<br>    }<br>  ],<br>  "completionArgs": {<br>    "temperature": 0.2,<br>    "max_tokens": 800<br>  },<br>  "store": false,<br>  "stream": true<br>}``` |

## Key Differences Summary

| **Aspect** | **Our API** | **Mistral API** | **Notes** |
|------------|-------------|-----------------|-----------|
| **Field Names** | `input` | `inputs` | Different naming |
| **Content Structure** | `ContentBlock[]` with `type` and `text` | Plain text in `content` | Our API more structured |
| **Object Field** | Not present | `object: "entry"` | Mistral more standardized |
| **Type Field** | `type: "message"` (optional) | `type: "message.input/output"` | Different semantics |
| **Tool Call Type** | `type: "tool_call"` | No type field | Our API more explicit |
| **Tool Execution** | Tool messages | `type: "tool.execution.*"` | Different approach |
| **Branching** | `previous_response_id` | `from_entry_id` | Different granularity |
| **Model Access** | Agent-only | Agent OR direct model | Mistral more flexible |
| **Settings Field** | `model_settings` | `completionArgs` | Different naming |
| **Streaming** | `"full"\|"events"\|"off"` | `true\|false` | Our API more granular |

## Key Similarities Summary

| **Aspect** | **Both APIs** | **Notes** |
|------------|---------------|-----------|
| **String Input** | ✅ Supported | Simple text messages |
| **Structured Input** | ✅ Supported | Typed message arrays |
| **Tool Calls** | ✅ Similar structure | `tool_calls` array with `id`, `name`, `args` |
| **Tool Call ID** | ✅ Identical | `tool_call_id` correlation |
| **Store Flag** | ✅ Identical | `store: boolean` semantics |
| **Conversation ID** | ✅ Supported | Conversation management |
| **Streaming** | ✅ Supported | Real-time responses |
| **Model Overrides** | ✅ Supported | Parameter customization |

This side-by-side comparison shows that while both APIs serve similar purposes, they have different design philosophies and implementation details. Our API is more structured and granular, while Mistral's API is more standardized and flexible.
