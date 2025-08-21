# Conversation Checkpointing with LangGraph

This document explains how to properly leverage LangGraph's native checkpointing interface for robust conversation management without duplicating functionality.

## Overview

LangGraph checkpointing provides a powerful persistence layer that automatically saves conversation state at every step. We leverage this native functionality for:

1. **Reliable conversation access control** - Using thread_id as conversation identifier
2. **Reliable conversation listing and retrieval** - Using checkpoint state for conversation metadata
3. **Conversation history management** - Listing and resuming from specific checkpoints
4. **Conversation editing** - Modifying checkpoint content and resuming from edited state

## Key Concepts

### Thread ID as Conversation ID

We use LangGraph's `thread_id` as our conversation identifier with user-scoped format:
```
user:{user_id}:{conversation_id}
```

This provides:
- **Automatic isolation** - Each user's conversations are naturally separated
- **Access control** - Thread ownership determines conversation access
- **Persistence** - LangGraph automatically manages checkpoint storage

### Checkpoint State Structure

LangGraph checkpoints contain:
```python
{
    "v": 4,  # Version
    "ts": "2024-07-31T20:14:19.804150+00:00",  # Timestamp
    "id": "1ef4f797-8335-6428-8001-8a1503f9b875",  # Checkpoint ID
    "channel_values": {
        "messages": [...],  # Conversation messages
        "my_key": "meow",
        "node": "node"
    },
    "channel_versions": {...},
    "versions_seen": {...},
    "interrupts": [...],  # For interrupted conversations
    "completed": false  # Conversation completion status
}
```

## Usage Examples

### 1. List User Conversations

```python
# Get all conversations for a user
conversations = await agent.list_conversations(config)

# Each conversation includes:
# - conversation_id (from thread_id)
# - status (active/interrupted/completed)
# - preview (first message content)
# - created_at/last_accessed timestamps
```

### 2. Load Conversation State

```python
# Load conversation from latest checkpoint
messages, conversation_info = await agent.load_conversation(
    conversation_id="550e8400-e29b-41d4-a716-446655440000",
    config=config
)
```

### 3. List Conversation Checkpoints

```python
# Get all checkpoints for a conversation
checkpoints = await agent.list_conversation_checkpoints(
    conversation_id="550e8400-e29b-41d4-a716-446655440000",
    config=config
)

# Returns:
# [
#     {
#         "checkpoint_id": "1ef4f797-8335-6428-8001-8a1503f9b875",
#         "timestamp": "2024-07-31T20:14:19.804150+00:00",
#         "version": 4,
#         "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
#     },
#     ...
# ]
```

### 4. Resume from Specific Checkpoint

```python
# Resume conversation from a specific point in history
messages, conversation_info = await agent.resume_from_checkpoint(
    conversation_id="550e8400-e29b-41d4-a716-446655440000",
    checkpoint_id="1ef4f797-8335-6428-8001-8a1503f9b875",
    config=config
)
```

### 5. Edit Conversation History

```python
# Edit messages in a specific checkpoint
edited_messages = [
    HumanMessage(content="Hello, I have a question about APIs"),
    AIMessage(content="I'd be happy to help! What would you like to know?")
]

success = await agent.edit_conversation_checkpoint(
    conversation_id="550e8400-e29b-41d4-a716-446655440000",
    checkpoint_id="1ef4f797-8335-6428-8001-8a1503f9b875",
    edited_messages=edited_messages,
    config=config
)

# Now resume from the edited checkpoint
messages, conversation_info = await agent.resume_from_checkpoint(
    conversation_id="550e8400-e29b-41d4-a716-446655440000",
    checkpoint_id="1ef4f797-8335-6428-8001-8a1503f9b875",
    config=config
)
```

## API Endpoints

### List Conversations
```
GET /api/v1/conversations
```

### Load Conversation
```
GET /api/v1/conversations/{conversation_id}
```

### List Checkpoints
```
GET /api/v1/conversations/{conversation_id}/checkpoints
```

### Resume from Checkpoint
```
POST /api/v1/conversations/{conversation_id}/checkpoints/{checkpoint_id}/resume
```

### Edit Checkpoint
```
PUT /api/v1/conversations/{conversation_id}/checkpoints/{checkpoint_id}
```

## Benefits of This Approach

### 1. **No Duplication**
- Uses LangGraph's native checkpointing interface directly
- No custom persistence layer needed
- Leverages LangGraph's built-in state management

### 2. **Reliable Access Control**
- Thread ownership provides natural access control
- User-scoped thread IDs ensure isolation
- Access validation at every operation

### 3. **Conversation History**
- Automatic checkpoint creation at every step
- Full conversation history available
- Ability to resume from any point

### 4. **Editing Capabilities**
- Modify conversation history
- Resume from edited state
- Maintain conversation flow

### 5. **Scalability**
- LangGraph handles checkpoint storage
- Supports multiple backends (memory, file, PostgreSQL, Redis)
- Automatic cleanup and management

## Configuration

```bash
# Checkpointing backend
CHECKPOINTING_BACKEND=postgres
CHECKPOINTING_POSTGRES_URL=postgresql://user:pass@postgres:5432/nalai

# Access control
CHAT_THREAD_ACCESS_CONTROL_BACKEND=memory

# Optional: Enable monitoring
ENABLE_MONITORING=true
```

## Error Handling

The system provides comprehensive error handling:

- **AccessDeniedError** - User doesn't own the conversation
- **ConversationNotFoundError** - Conversation or checkpoint doesn't exist
- **ValidationError** - Invalid input parameters
- **InvocationError** - Operation failed

## Best Practices

1. **Always validate access** before any operation
2. **Use user-scoped thread IDs** for proper isolation
3. **Handle checkpoint not found** gracefully
4. **Log operations** for audit trails
5. **Test checkpoint editing** thoroughly before production

## Future Enhancements

1. **Bulk operations** - Edit multiple checkpoints at once
2. **Checkpoint branching** - Create conversation branches
3. **Checkpoint merging** - Combine conversation branches
4. **Advanced editing** - Partial message editing
5. **Checkpoint analytics** - Usage patterns and insights

This approach provides a robust, scalable conversation management system that fully leverages LangGraph's native capabilities without unnecessary duplication.
