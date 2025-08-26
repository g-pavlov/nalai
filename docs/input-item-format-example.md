# Input Message Format Examples

The API now supports a new input format that allows you to specify input messages as an array with different content types. This format is more flexible and follows a standardized structure.

## Input Message Structure

Each input message has the following properties:

- **role**: string [Required] - The role of the message input. One of `user` or `assistant`.
- **type**: string [Optional] - The type of the message input. Always `'message'`.
- **content**: string [Required] - Text input to the model, used to generate a response. Can also contain previous assistant responses.

## Examples

### 1. Simple User Message (Stateless)

```json
{
  "input": [
    {
      "role": "user",
      "type": "message",
      "content": "Hello, how are you?"
    }
  ],
  "stream": "off",
  "store": false
}
```

### 2. Conversation with History (Stateless)

```json
{
  "input": [
    {
      "role": "user",
      "type": "message",
      "content": "What is the capital of France?"
    },
    {
      "role": "assistant",
      "type": "message",
      "content": "The capital of France is Paris."
    },
    {
      "role": "user",
      "type": "message",
      "content": "What about Germany?"
    }
  ],
  "stream": "off",
  "store": false
}
```

### 3. Stateful Conversation (New Message)

```json
{
  "input": [
    {
      "role": "user",
      "type": "message",
      "content": "Hello, how are you?"
    }
  ],
  "stream": "off",
  "store": true
}
```

### 4. Stateful Conversation (Continue with History)

```json
{
  "input": [
    {
      "role": "assistant",
      "type": "message",
      "content": "I'm doing well, thank you for asking! How can I help you today?"
    },
    {
      "role": "user",
      "type": "message",
      "content": "Can you help me with a coding problem?"
    }
  ],
  "stream": "off",
  "store": true
}
```

## Validation Rules

### Stateless Conversations (`store: false`)
- Must start with a user message
- Can have multiple messages in alternating user/assistant pattern
- No conversation history is maintained

### Stateful Conversations (`store: true`)
- Must have exactly one user message (the new input)
- Can have at most one assistant message (the last response)
- The user message must be the last message in the array
- Conversation history is maintained and stored

## Error Cases

### Invalid Role
```json
{
  "input": [
    {
      "role": "system",
      "type": "message",
      "content": "You are a helpful assistant"
    }
  ],
  "stream": "off",
  "store": false
}
```
**Error**: `Unsupported role 'system' at position 0. Must be 'user' or 'assistant'`

### Empty Content
```json
{
  "input": [
    {
      "role": "user",
      "type": "message",
      "content": ""
    }
  ],
  "stream": "off",
  "store": false
}
```
**Error**: `Message content cannot be empty at position 0`

### Invalid Stateful Conversation
```json
{
  "input": [
    {
      "role": "user",
      "type": "message",
      "content": "First message"
    },
    {
      "role": "user",
      "type": "message",
      "content": "Second message"
    }
  ],
  "stream": "off",
  "store": true
}
```
**Error**: `In stateful conversations, the human message must be the last message (new input)`

## Comparison with Existing Formats

### String Input (Legacy)
```json
{
  "input": "Hello, how are you?",
  "stream": "off",
  "store": false
}
```

### Structured Message Input (Existing)
```json
{
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Hello, how are you?"
        }
      ]
    }
  ],
  "stream": "off",
  "store": false
}
```

### Input Message Format (New)
```json
{
  "input": [
    {
      "role": "user",
      "type": "message",
      "content": "Hello, how are you?"
    }
  ],
  "stream": "off",
  "store": false
}
```

The new InputMessage format provides a simpler, more standardized way to specify input messages while maintaining compatibility with existing formats.
