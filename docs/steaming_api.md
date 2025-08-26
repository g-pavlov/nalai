# Streaming & Interrupts API — Specification

## 1. Endpoints

### Unified RPC Endpoint
* **Chat - Append, Insert, Resume with messages** — `POST /api/v1/responses`

Accepts **JSON** bodies and can respond as **JSON** or **SSE**, per negotiation below.

---

## 2. Content Negotiation & Streaming Modes

### Request Configuration
* **Request bodies:** `Content-Type: application/json`
* **Select streaming semantics** with **`stream`** (boolean):

  * **`full`** — **typed events + tokens** (LLM token deltas) **(default)**
  * **`events`** — typed events only; LLM reply is a **single** message event (no token deltas)
  * **`off`** — non-streaming; single JSON envelope

### Transport Negotiation
* **Negotiate transport** with `Accept`:

  * If `stream ∈ {"full","events"}` → **must** be `Accept: text/event-stream`, else **406 Not Acceptable**
  * If `stream = "off"` **and** `Accept: text/event-stream` → **406 Not Acceptable** (strict; no single-frame fallback)\

### Truth Matrix

| `Accept`            | `stream` | Behavior                       |
| ------------------- | -------- | ------------------------------ |
| `application/json`  | `off`    | 200 JSON                       |
| `application/json`  | `events` | **406** incompatible-transport |
| `application/json`  | `full`   | **406** incompatible-transport |
| `text/event-stream` | `events` | 200 SSE                        |
| `text/event-stream` | `full`   | 200 SSE                        |
| `text/event-stream` | `off`    | **406** incompatible-transport |


---

## 3. OpenAPI Snippets

### Key Request Schema

```yaml
# Request body schema
ResponseRequest:
  type: object
  required:
    - input
  properties:
    conversation_id:
      type: string
      format: uuid
      description: Conversation ID for continuation
    input:
      type: array
      description: Input messages
      items:
        oneOf:
          - $ref: '#/components/schemas/HumanMessageInput'
          - $ref: '#/components/schemas/ToolDecisionInput'
      minItems: 1
      maxItems: 100
    stream:
      type: string
      enum: ["full", "events", "off"]
      default: "off"
      description: |
        full   = typed events + tokens (token-by-token LLM deltas)  
        events = typed events only; LLM reply as one message event  
        off    = non-streaming JSON envelope

        Transport rules:  
        - stream in {full, events} requires Accept: text/event-stream (else 406)  
        - stream = off with Accept: text/event-stream → 406
    store:
      type: boolean
      default: true
      description: Whether to store the response
```


### Request Headers

```yaml
# Request headers
headers:
  Accept:
    description: Response format - text/event-stream for streaming, application/json for REST
    schema:
      type: string
      enum: ["text/event-stream", "application/json"]
    required: true
  Content-Type:
    description: Request body format
    schema:
      type: string
      enum: ["application/json"]
    required: true
```

### Error Responses

```yaml
# 406 - Incompatible transport
'406':
  description: Incompatible transport - streaming requested with JSON Accept or vice versa
  content:
    application/json:
      schema:
        type: object
        properties:
          detail:
            type: string
            example: "Incompatible transport: stream=full requires Accept: text/event-stream"

# 422 - Validation error
'422':
  description: Validation error
  content:
    application/json:
      schema:
        type: object
        properties:
          detail:
            type: array
            items:
              type: object
              properties:
                loc: [string|integer]
                msg: string
                type: string
```

---

## 4. Request/Response Examples

### 4.1 Valid Combinations (200 OK)

#### A. `Accept: application/json` + `stream: "off"` → 200 JSON

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/responses" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello, can you help me with my ecommerce store?"
          }
        ]
      }
    ],
    "stream": "off",
    "store": true
  }'
```

**Response (200 OK):**
```json
{
  "output": {
    "id": "resp_789abc",
    "conversation": "conv_12345678-1234-1234-1234-123456789abc",
    "model": "gpt-4",
    "output": [
      {
        "id": "msg_123",
        "role": "assistant",
        "content": [
          {
            "type": "text",
            "text": "Hello! I'd be happy to help you with your ecommerce store. What specific aspects would you like assistance with?"
          }
        ]
      }
    ],
    "usage": {
      "prompt_tokens": 15,
      "completion_tokens": 25,
      "total_tokens": 40
    },
    "created_at": "2024-01-15T10:30:00Z",
    "status": "completed"
  }
}
```

#### B. `Accept: text/event-stream` + `stream: "full"` → 200 SSE

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/responses" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "What products do you recommend?"
          }
        ]
      }
    ],
    "stream": "full",
    "store": true
  }'
```

**Response (200 OK):**
```
event: response.created
data: {"id": "resp_def456", "conversation": "conv_12345678-1234-1234-1234-123456789abc"}

event: response.output_text.delta
data: {"id": "resp_def456", "conversation": "conv_12345678-1234-1234-1234-123456789abc", "content": "Based"}

event: response.output_text.delta
data: {"id": "resp_def456", "conversation": "conv_12345678-1234-1234-1234-123456789abc", "content": " on"}

event: response.output_text.delta
data: {"id": "resp_def456", "conversation": "conv_12345678-1234-1234-1234-123456789abc", "content": " your"}

event: response.output_text.delta
data: {"id": "resp_def456", "conversation": "conv_12345678-1234-1234-1234-123456789abc", "content": " store"}

event: response.completed
data: {"id": "resp_def456", "conversation": "conv_12345678-1234-1234-1234-123456789abc", "usage": {"prompt_tokens": 12, "completion_tokens": 18, "total_tokens": 30}}
```

#### C. `Accept: text/event-stream` + `stream: "events"` → 200 SSE

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/responses" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Show me the latest orders"
          }
        ]
      }
    ],
    "stream": "events",
    "store": true
  }'
```

**Response (200 OK):**
```
event: response.created
data: {"id": "resp_ghi789", "conversation": "conv_12345678-1234-1234-1234-123456789abc"}

event: response.message
data: {"id": "resp_ghi789", "conversation": "conv_12345678-1234-1234-1234-123456789abc", "content": "Here are your latest orders:", "role": "assistant"}

event: response.completed
data: {"id": "resp_ghi789", "conversation": "conv_12345678-1234-1234-1234-123456789abc", "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}}
```

### 4.2 Invalid Combinations (406 Not Acceptable)

#### A. `Accept: application/json` + `stream: "full"` → 406 Error

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/responses" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello"
          }
        ]
      }
    ],
    "stream": "full",
    "store": true
  }'
```

**Response (406 Not Acceptable):**
```json
{
  "detail": "Incompatible transport: stream=full requires Accept: text/event-stream"
}
```

#### B. `Accept: application/json` + `stream: "events"` → 406 Error

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/responses" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello"
          }
        ]
      }
    ],
    "stream": "events",
    "store": true
  }'
```

**Response (406 Not Acceptable):**
```json
{
  "detail": "Incompatible transport: stream=events requires Accept: text/event-stream"
}
```

#### C. `Accept: text/event-stream` + `stream: "off"` → 406 Error

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/responses" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello"
          }
        ]
      }
    ],
    "stream": "off",
    "store": true
  }'
```

**Response (406 Not Acceptable):**
```json
{
  "detail": "Incompatible transport: stream=off requires Accept: application/json"
}
```


