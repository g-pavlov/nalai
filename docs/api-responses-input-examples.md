# /api/v1/responses Input Examples

This document provides comprehensive examples for all input options available for the `/api/v1/responses` endpoint.

## Table of Contents

1. [Basic String Input](#basic-string-input)
2. [Structured Message Input](#structured-message-input)
3. [Stateful Conversations](#stateful-conversations)
4. [Stateless Conversations](#stateless-conversations)
5. [Tool Decision Input](#tool-decision-input)
6. [Model Configuration](#model-configuration)
7. [Streaming Options](#streaming-options)
8. [Complete Examples](#complete-examples)

## Basic String Input

The simplest form of input - a plain string that gets converted to an implicit human message.

### Example 1: Simple String Input
```json
{
  "input": "Hello, how can you help me today?",
  "stream": "off"
}
```

### Example 2: String Input with Model
```json
{
  "input": "Explain quantum computing in simple terms",
  "model": "openai/gpt-4",
  "stream": "off"
}
```

### Example 3: String Input with Model Settings
```json
{
  "input": "Write a short poem about AI",
  "model": "ollama/llama3.1:8b",
  "model_settings": {
    "temperature": 0.8,
    "max_tokens": 200
  },
  "stream": "off"
}
```

## Structured Message Input

Using structured message objects for more complex conversation scenarios.

### Example 1: Single Human Message
```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What's the weather like today?"
        }
      ]
    }
  ],
  "stream": "off"
}
```

### Example 2: Human Message with Multiple Content Blocks
```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Please analyze this data and provide insights: "
        },
        {
          "type": "text",
          "text": "Sales increased by 15% in Q3, customer satisfaction is 4.2/5"
        }
      ]
    }
  ],
  "stream": "off"
}
```

### Example 3: AI Message with Tool Calls
```json
{
  "input": [
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "I'll help you update the product information."
        }
      ],
      "tool_calls": [
        {
          "id": "call_123",
          "name": "put_http_requests",
          "args": {
            "url": "http://api.example.com/products/123",
            "input_data": {
              "name": "Updated Product",
              "price": 29.99
            }
          },
          "type": "tool_call"
        }
      ]
    }
  ],
  "stream": "off"
}
```

### Example 4: Tool Message Response
```json
{
  "input": [
    {
      "type": "message",
      "role": "tool",
      "content": [
        {
          "type": "text",
          "text": "{\"id\": \"123\", \"name\": \"Updated Product\", \"price\": 29.99, \"updated\": true}"
        }
      ],
      "tool_call_id": "call_123"
    }
  ],
  "stream": "off"
}
```

## Stateful Conversations

For continuing existing conversations with minimal history.

### Example 1: New Conversation (No conversation_id)
```json
{
  "input": "Start a new conversation about machine learning",
  "conversation_id": null,
  "store": true,
  "stream": "off"
}
```

### Example 2: Continue Conversation (With conversation_id)
```json
{
  "input": "Can you explain neural networks in more detail?",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "store": true,
  "stream": "off"
}
```

### Example 3: Continue with History (AI + Tool Messages)
```json
{
  "input": [
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "I'll fetch the current user data for you."
        }
      ],
      "tool_calls": [
        {
          "id": "call_456",
          "name": "get_http_requests",
          "args": {
            "url": "http://api.example.com/users/123"
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
          "text": "{\"id\": \"123\", \"name\": \"John Doe\", \"email\": \"john@example.com\"}"
        }
      ],
      "tool_call_id": "call_456"
    },
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Now update the user's email to jane@example.com"
        }
      ]
    }
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "store": true,
  "stream": "off"
}
```

### Example 4: Response Branching (With previous_response_id)
```json
{
  "input": "Let me try a different approach",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "previous_response_id": "resp_789",
  "store": true,
  "stream": "off"
}
```

## Stateless Conversations

For full conversation replay without storage constraints.

### Example 1: Full Conversation Replay
```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Hello, I need help with API integration"
        }
      ]
    },
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "I'd be happy to help you with API integration! What specific questions do you have?"
        }
      ]
    },
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "How do I handle authentication in REST APIs?"
        }
      ]
    },
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "There are several authentication methods for REST APIs. The most common are:"
        }
      ]
    }
  ],
  "store": false,
  "stream": "off"
}
```

### Example 2: Complex Tool Conversation
```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Create a new user account"
        }
      ]
    },
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "I'll help you create a new user account. I need some information first."
        }
      ],
      "tool_calls": [
        {
          "id": "call_789",
          "name": "post_http_requests",
          "args": {
            "url": "http://api.example.com/users",
            "input_data": {
              "name": "New User",
              "email": "newuser@example.com"
            }
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
          "text": "{\"id\": \"456\", \"name\": \"New User\", \"email\": \"newuser@example.com\", \"created\": true}"
        }
      ],
      "tool_call_id": "call_789"
    },
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "Great! I've successfully created a new user account with ID 456."
        }
      ]
    },
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Now update the user's profile with additional information"
        }
      ]
    }
  ],
  "store": false,
  "stream": "off"
}
```

## Tool Decision Input

For resuming interrupted tool calls with user decisions.

### Example 1: Accept Tool Call
```json
{
  "input": [
    {
      "type": "tool_decision",
      "tool_call_id": "call_123",
      "decision": "accept"
    }
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "stream": "off"
}
```

### Example 2: Reject Tool Call
```json
{
  "input": [
    {
      "type": "tool_decision",
      "tool_call_id": "call_123",
      "decision": "reject",
      "message": "I don't want to proceed with this action"
    }
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "stream": "off"
}
```

### Example 3: Edit Tool Call Arguments
```json
{
  "input": [
    {
      "type": "tool_decision",
      "tool_call_id": "call_123",
      "decision": "edit",
      "args": {
        "url": "http://api.example.com/products/456",
        "input_data": {
          "name": "Modified Product Name",
          "price": 39.99
        }
      }
    }
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "stream": "off"
}
```

### Example 4: Provide Feedback
```json
{
  "input": [
    {
      "type": "tool_decision",
      "tool_call_id": "call_123",
      "decision": "feedback",
      "message": "Please use a different API endpoint for this operation"
    }
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "stream": "off"
}
```

## Model Configuration

### Example 1: Platform/Model Format
```json
{
  "input": "Explain machine learning concepts",
  "model": "openai/gpt-4",
  "stream": "off"
}
```

### Example 2: Model with Settings
```json
{
  "input": "Write a creative story",
  "model": "ollama/llama3.1:8b",
  "model_settings": {
    "temperature": 0.9,
    "max_tokens": 500
  },
  "stream": "off"
}
```

### Example 3: AWS Bedrock Model
```json
{
  "input": "Analyze this business data",
  "model": "aws_bedrock/claude-3-sonnet",
  "model_settings": {
    "temperature": 0.1,
    "max_tokens": 1000
  },
  "stream": "off"
}
```

### Example 4: Default Model with Settings
```json
{
  "input": "Generate a summary",
  "model_settings": {
    "temperature": 0.3,
    "max_tokens": 200
  },
  "stream": "off"
}
```

## Streaming Options

### Example 1: Full Streaming (Default)
```json
{
  "input": "Tell me a story",
  "stream": "full"
}
```
**Headers:** `Accept: text/event-stream`

### Example 2: Events Only Streaming
```json
{
  "input": "Explain quantum physics",
  "stream": "events"
}
```
**Headers:** `Accept: text/event-stream`

### Example 3: Non-Streaming
```json
{
  "input": "What is AI?",
  "stream": "off"
}
```
**Headers:** `Accept: application/json`

## Complete Examples

### Example 1: Full E-commerce Integration
```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "I need to manage my e-commerce inventory. Can you help me?"
        }
      ]
    },
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "I can help you manage your e-commerce inventory! I have access to inventory management APIs."
        }
      ],
      "tool_calls": [
        {
          "id": "call_inventory_1",
          "name": "get_http_requests",
          "args": {
            "url": "http://api.example.com/inventory"
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
          "text": "{\"products\": [{\"id\": \"123\", \"name\": \"Widget\", \"stock\": 50}, {\"id\": \"456\", \"name\": \"Gadget\", \"stock\": 25}]}"
        }
      ],
      "tool_call_id": "call_inventory_1"
    },
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Update the stock for Widget to 75 units"
        }
      ]
    }
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "model": "openai/gpt-4",
  "model_settings": {
    "temperature": 0.1
  },
  "store": true,
  "disable_cache": false,
  "stream": "off"
}
```

### Example 2: Customer Support Chat
```json
{
  "input": "I'm having trouble with my account login",
  "conversation_id": "support-chat-123",
  "model": "openai/gpt-4",
  "model_settings": {
    "temperature": 0.7,
    "max_tokens": 300
  },
  "store": true,
  "stream": "full"
}
```

### Example 3: Data Analysis Request
```json
{
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Analyze this sales data and provide insights"
        }
      ]
    }
  ],
  "model": "aws_bedrock/claude-3-sonnet",
  "model_settings": {
    "temperature": 0.2,
    "max_tokens": 800
  },
  "store": false,
  "disable_cache": true,
  "stream": "events"
}
```

## Error Examples

### Example 1: Invalid Transport (406 Error)
```json
{
  "input": "Hello",
  "stream": "full"
}
```
**Headers:** `Accept: application/json` ❌

### Example 2: Invalid Message Sequence (422 Error)
```json
{
  "input": [
    {
      "type": "message",
      "role": "assistant",
      "content": [{"type": "text", "text": "This should fail"}]
    }
  ],
  "stream": "off"
}
```

### Example 3: Content Too Large (422 Error)
```json
{
  "input": "A".repeat(11000),  // 11KB - exceeds 10KB limit
  "stream": "off"
}
```

### Example 4: Invalid Model Settings (422 Error)
```json
{
  "input": "Hello",
  "model_settings": {
    "temperature": 3.0  // Exceeds 2.0 limit
  },
  "stream": "off"
}
```

## Response Examples

### Successful Response (200)
```json
{
  "id": "resp_789",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "previous_response_id": null,
  "model": "openai/gpt-4",
  "output": [
    {
      "id": "msg_123",
      "role": "human",
      "content": [{"type": "text", "text": "Hello"}]
    },
    {
      "id": "msg_456",
      "role": "assistant",
      "content": [{"type": "text", "text": "Hello! How can I help you today?"}],
      "tool_calls": null,
      "invalid_tool_calls": [],
      "finish_reason": "stop",
      "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 15,
        "total_tokens": 25
      }
    }
  ],
  "created_at": "2024-01-15T10:30:00Z",
  "status": "completed",
  "interrupts": null,
  "metadata": null,
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

### Interrupted Response (200)
```json
{
  "id": "resp_790",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "previous_response_id": null,
  "model": "openai/gpt-4",
  "output": [
    {
      "id": "msg_124",
      "role": "human",
      "content": [{"type": "text", "text": "Update product stock"}]
    },
    {
      "id": "msg_457",
      "role": "assistant",
      "content": [],
      "tool_calls": [
        {
          "id": "call_789",
          "name": "put_http_requests",
          "args": {
            "url": "http://api.example.com/products/123",
            "input_data": {"stock": 100}
          },
          "type": "tool_call"
        }
      ],
      "invalid_tool_calls": [],
      "finish_reason": "tool_calls",
      "usage": {
        "prompt_tokens": 20,
        "completion_tokens": 30,
        "total_tokens": 50
      }
    }
  ],
  "created_at": "2024-01-15T10:31:00Z",
  "status": "interrupted",
  "interrupts": [
    {
      "type": "tool_call",
      "tool_call_id": "call_789",
      "action": "pending",
      "args": {
        "value": [
          {
            "action_request": {
              "action": "put_http_requests",
              "args": {
                "url": "http://api.example.com/products/123",
                "input_data": {"stock": 100}
              }
            },
            "config": {
              "allow_accept": true,
              "allow_edit": true,
              "allow_respond": true
            },
            "description": "Update product stock level"
          }
        ]
      }
    }
  ],
  "metadata": null,
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 30,
    "total_tokens": 50
  }
}
```

## Best Practices

### 1. Choose the Right Input Format
- **String input**: Simple, single-turn conversations
- **Structured input**: Complex conversations with tool calls
- **Tool decisions**: Resuming interrupted tool calls

### 2. Use Appropriate Streaming
- **`full`**: Real-time interaction with token streaming
- **`events`**: Event-based updates without token streaming
- **`off`**: Complete response in single JSON

### 3. Manage Conversation State
- **`store: true`**: For ongoing conversations
- **`store: false`**: For one-time analysis or testing

### 4. Optimize Model Settings
- **Low temperature (0.1-0.3)**: Factual, consistent responses
- **High temperature (0.7-0.9)**: Creative, varied responses
- **Appropriate max_tokens**: Balance completeness vs cost

### 5. Handle Errors Gracefully
- **Check status codes**: 200, 400, 403, 404, 406, 422, 500
- **Validate input**: Ensure proper message sequences
- **Monitor usage**: Track token consumption and costs
