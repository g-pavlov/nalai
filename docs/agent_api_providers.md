# Agent API Providers Comparison

> A comprehensive analysis of agent API design patterns across major providers, focusing on stateful conversation management, streaming implementations, and interrupt/resume patterns.



## Table of Contents

- [Executive Summary](#executive-summary)
- [Protocol Design Trends](#protocol-design-trends)
- [Provider Overview](#provider-overview)
- [Core Operations](#core-operations)
  - [Overview](#overview)
  - [RPC/HTTP Operations ("REST")](#rpchttp-operations-rest)
  - [Streaming Operations (RPC with Streaming)](#streaming-operations-rpc-with-streaming)
- [Advanced Patterns](#advanced-patterns)
  - [Interrupts & Resume](#interrupts--resume)
  - [State Management](#state-management)
- [Implementation Notes](#implementation-notes)
- [Documentation References](#documentation-references)

---

## Executive Summary

**Purpose**: This document studies the competitive landscape of API designs as a foundation for building **competitive-analysis-driven API design for our agent platform**. This research serves as the strategic foundation for making data-driven decisions about our API architecture, feature prioritization, and competitive positioning in the agent API market.



### Providers Landscape Trends
**Commodity Features (Widely Available)**
- **Basic transports**: REST for request/response + SSE for streaming (universal)
- **Tool/function calling**: Round-trip tool call → tool result pattern (standardized)
- **Streaming granularity**: Token/text deltas with typed event frames
- **Stateless continuation**: Send prior messages in every request (universal)

**Emerging Differentiators (Product Design Choices)**
- **Server-side conversation state**: First-class IDs with admin lifecycle (Mistral Conversations, AWS Sessions, OpenAI response chains)
- **Typed streaming beyond text**: Tool/handoff/approval frames for orchestration
- **Interrupts/approval & resume**: Formal return control contracts (AWS), MCP approvals (OpenAI), agent handoffs (Mistral)
- **Conversation lifecycle APIs**: List/get/history/restart operations (Mistral, AWS)

**Quickly Becoming Commodity**
- **Typed SSE event schemas**: Spreading across all providers
- **Tool calling with partial/parallel arguments**: Expect parity soon

**True Differentiators (Harder to Copy)**
- **First-class state with admin lifecycle**: Auditability, listability, restart-from-entry
- **Governed interrupts with explicit resume contracts**: HITL and compliance codification
- **Rich, typed streaming for orchestration**: Reduces glue code for UIs and observability
- **Multi-modal streaming with content negotiation**: Transport validation with 406 enforcement
- **Transient conversation support**: Memory-only execution with persistence control

### Research Focus

Our agent is positioned closer to  **providers offering stateful conversation management** (OpenAI Responses, AWS Bedrock Agents, Mistral Conversations) on the competitive landscape. This research will focus primarily on them.

---

## Provider Overview

### OpenAI Responses — Unified Agent Surface
- **Philosophy**: Single endpoint design with response-chain anchoring
- **Key Features**: 
  - Single `/v1/responses` endpoint for all operations
  - Response-chain anchoring instead of conversation objects
  - Typed SSE events with MCP integration
  - Per-response deletion (no conversation lifecycle)

### AWS Bedrock Agents — Enterprise-Grade Lifecycle
- **Philosophy**: Comprehensive session management with strong enterprise controls
- **Key Features**:
  - Comprehensive session management (list/end/delete)
  - Return-control mechanism for human-in-the-loop
  - Chunked JSON streaming (not SSE)
  - Strong action-group orchestration

### Mistral Conversations — First-Class Conversation Objects
- **Philosophy**: Rich conversation lifecycle with flexible execution modes
- **Key Features**:
  - Rich conversation lifecycle (start/append/restart/list/history)
  - Dedicated streaming endpoints with `#stream` suffix
  - Flexible handoff execution (server vs client)
  - Clean resume via entries (FunctionResultEntry)

---

## Protocol Desing Trends

A quick, stateful-only snapshot (OpenAI **Responses**, **Mistral Conversations**, **AWS Bedrock Agents**) showing where designs **converge** and where they **differentiate** — now with terse code to make it concrete.

### Convergence (must-have basics most vendors share)

* **REST + streaming pair**
  * Same endpoint family 
  * Add `Accept: text/event-stream` (or provider flag) to stream
  * A plain JSON envelope for non-streaming. ([OpenAI Platform][20], [Mistral AI Documentation][21], [AWS Documentation][2])
* **Typed event streams**
  * Streams carry *start / delta / done* and *tool/interrupt markers*, not just raw text. ([OpenAI GitHub Pages][22], [GitHub][23], [AWS Documentation][2])
* **Resume on the same endpoint:** 
  * No special “resume URL”
  * You **POST the same endpoint** with a state handle and a payload that carries **tool results / approvals**. ([OpenAI Platform][6], [Mistral AI Documentation][7], [AWS Documentation][3])
* **Tool calls are standard interrupts**
  * The model asks for a tool
  * Your app runs it
  * You **resume** with a follow-up call including the result. ([OpenAI Platform][24], [Mistral AI Documentation][3], [AWS Documentation][11])


### Differentiators (opportunities to stand out)

* **State handle model**

  * **OpenAI**: **response chain** → `previous_response_id` (no conversation “list” API). ([OpenAI Platform][6])
  * **Mistral**: **conversation object** → `conversation_id` with **start / append / list / get / history / restart**. ([Mistral AI Documentation][1])
  * **AWS**: **session object** → `sessionId` in URL with **list / end / delete** lifecycle. ([AWS Documentation][4])
* **Streaming protocol**

  * **OpenAI & Mistral**: **SSE** with semantic event names — easy to multiplex in UIs. ([OpenAI Platform][20], [GitHub][23])
  * **AWS**: **HTTP chunked JSON** with structured parts (`chunk.bytes`, `trace`, `returnControl`). ([AWS Documentation][2])
* **Interrupt semantics & resume contract**

  * **AWS**: explicit **return-control** (`invocationId` + result array) → strong, auditable resume shape. ([AWS Documentation][11], [Boto3 Documentation][25])
  * **OpenAI**: **tool/MCP approval** events; resume by posting a **tool result/approval** with `previous_response_id`. ([OpenAI Platform][24], [Microsoft Learn][12])
  * **Mistral**: **tool.execution / agent.handoff** events; resume by **appending an entry** to the same conversation (choose `handoff_execution: "client" | "server"`). ([Mistral AI Documentation][3])
* **Lifecycle breadth**

  * **Mistral**: rich **list / history / restart-from-entry**. ([Mistral AI Documentation][21])
  * **AWS**: **list / end / delete** sessions. ([AWS Documentation][4])
  * **OpenAI**: **get/delete per response**; you maintain your own “conversation list”. ([OpenAI Platform][6], [OpenAI Community][14])

---

## Core Operations

### Overview

**RPC-over-HTTP Foundation:**  
All major providers use RPC-over-HTTP despite marketing as "REST APIs" - fundamentally data-driven interaction protocols, not resource-oriented designs.

**Streaming:**   
- **SSE (Server-Sent Events)**: Consumer APIs (OpenAI, Mistral, Anthropic, Cohere, Groq/OpenRouter)
- **HTTP Chunked JSON**: Enterprise cloud providers (AWS Bedrock, Google Vertex/Gemini)

**Request Body Standardization:** Universal patterns across providers:  
- **Message Arrays**: `inputs[]`, `input[]` for conversation content
- **Structured Content**: `type` and `role` fields
- **Streaming Flags**: `"stream": true` (except AWS uses `streamingConfigurations` object)
- **Storage Flags**: `"store": true` for persistence control

**URL Design Philosophy:** Three distinct approaches reflecting target markets:
- **Single Endpoint** (OpenAI): `/v1/responses` - pure RPC design
- **Resource-Oriented** (Mistral): `/v1/conversations/{id}` - REST-like with RPC operations  
- **Enterprise Hierarchical** (AWS): `/agents/{agentId}/sessions/{sessionId}/text` - deep nesting

**Response Structure Consistency:** Providers maintain consistent patterns across REST and streaming:
- **Object-Based** (Mistral): Wrapper objects with `"object"` type field
- **Direct Content** (OpenAI/AWS): Direct response objects without wrappers

**Authentication Market Segmentation:**  
- **Bearer Tokens**: Consumer/developer APIs
- **Cloud Native**: Enterprise cloud providers (AWS SigV4, Google OAuth2)

**Pagination Patterns:**  
- **Offset-Based** (Mistral): `?page=0&page_size=100` with `data[]` array
- **Token-Based** (AWS): `?maxResults=20&nextToken=...` with `nextToken` for continuation

**Interrupt/Resume Convergence:**
- **No separate resume endpoints**: All providers resume on same endpoint family
- **Special payloads**: Tool results, MCP approvals, or return-control results
- **Interrupt types**: Tool execution, agent handoffs, return-control, MCP approvals

**State Model Approaches:**
- **Stateless**: Client-held history (Anthropic, Cohere, Groq/OpenRouter, Google)
- **Stateful**: Three variants:
  1. **Response Chain** (OpenAI) - `previous_response_id`
  2. **Session Handle** (AWS Bedrock) - `sessionId` with lifecycle
  3. **Conversation Object** (Mistral) - `conversation_id` with rich operations

### RPC/HTTP Operations ("REST")

#### Start New Conversation

| Provider | Request | Response | Documentation |
|----------|---------|----------|---------------|
| **Mistral — Conversations** | **Request:**<br>`POST https://api.mistral.ai/v1/conversations`<br><br>**Headers:**<br>`Authorization: Bearer MISTRAL_API_KEY`<br>`Content-Type: application/json`<br>`Accept: application/json`<br><br>**Body:**<br>`{ "agent_id": "ag_12345", "inputs": [{ "type": "message.input", "role": "user", "content": "Plan a 3-day NYC trip" }], "store": true, "stream": false, "name": "conv-my-uuid" }` | **Response:**<br>`200 OK`<br>`Content-Type: application/json`<br><br>`{ "object": "conversation.response", "conversation_id": "conv_...", "outputs": [{ "object": "entry", "type": "message.output", "id": "msg_...", "role": "assistant", "model": "mistral-...", "content": "..." }], "usage": { "prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ... } }` | [docs.mistral.ai][1] |
| **AWS Bedrock — Agents Runtime** | **Request:**<br>`POST https://bedrock-agent-runtime.{region}.amazonaws.com/agents/{agentId}/agentAliases/{agentAliasId}/sessions/{sessionId}/text`<br><br>**Headers (SigV4):**<br>`Authorization: AWS4-HMAC-SHA256 Credential=..., SignedHeaders=..., Signature=...`<br>`X-Amz-Date: 20250821T120000Z`<br>`x-amz-source-arn: arn:aws:bedrock:{region}:{account}:agent/{agentId}`<br>`Content-Type: application/json`<br><br>**Body:**<br>`{ "inputText": "Plan a 3-day NYC trip", "enableTrace": true, "streamingConfigurations": { "streamFinalResponse": true } }` | **Response:**<br>`200 OK`<br>`x-amz-bedrock-agent-session-id: {sessionId}`<br>`x-amz-bedrock-agent-memory-id: {memoryId}`<br>`Content-Type: application/json`<br><br>`{ "chunk": { "bytes": "...base64 or string...", "attribution": { "citations": [...] } }, "trace": { ... }, "returnControl": { ... } }` | [AWS Documentation][2] |
| **OpenAI — Responses API** | **Request:**<br>`POST https://api.openai.com/v1/responses`<br><br>**Headers:**<br>`Authorization: Bearer OPENAI_API_KEY`<br>`Content-Type: application/json`<br>`Accept: application/json`<br><br>**Body:**<br>`{ "model": "gpt-4.1-mini", "input": [{ "role": "user", "content": [{ "type": "text", "text": "Plan a 3-day NYC trip" }] }], "store": true }` | **Response:**<br>`200 OK`<br>`Content-Type: application/json`<br><br>Response object `{ id:"resp_...", output:[...], ... }` | [OpenAI Platform][6], [Conversation State][9] |

#### Continue Existing Conversation

| Provider | Request | Response | Documentation |
|----------|---------|----------|---------------|
| **Mistral — Conversations** | **Request:**<br>`POST https://api.mistral.ai/v1/conversations/{conversation_id}`<br><br>**Headers:**<br>`Authorization: Bearer MISTRAL_API_KEY`<br>`Content-Type: application/json`<br>`Accept: application/json`<br><br>**Body:**<br>`{ "inputs": [{ "type": "message.input", "role": "user", "content": "Add museum options" }], "store": true, "stream": false }` | **Response:**<br>Same format as "Start New" with new `outputs[]` | [docs.mistral.ai][1] |
| **AWS Bedrock — Agents Runtime** | **Request:**<br>`POST https://.../agents/{agentId}/agentAliases/{agentAliasId}/sessions/{sessionId}/text`<br><br>**Headers:**<br>(SigV4) as above<br><br>**Body (re-use the same `sessionId`):**<br>`{ "inputText": "Add museum options", "streamingConfigurations": { "streamFinalResponse": true } }` | **Response:**<br>Same shapes as "Start New" | [AWS Documentation][2] |
| **OpenAI — Responses API** | **Request:**<br>`POST https://api.openai.com/v1/responses`<br><br>**Headers:**<br>Same as start (REST)<br><br>**Body:**<br>`{ "model": "gpt-4.1-mini", "previous_response_id": "resp_abc123", "input": [{ "role": "user", "content": [{ "type": "text", "text": "Add museum options" }] }] }` | **Response:**<br>Same shapes as start REST | [OpenAI Platform][6], [Conversation State][9] |

#### List Conversations

| Provider | Request | Response | Documentation |
|----------|---------|----------|---------------|
| **Mistral — Conversations** | **Request:**<br>`GET https://api.mistral.ai/v1/conversations?page=0&page_size=100`<br><br>**Headers:**<br>`Authorization: Bearer MISTRAL_API_KEY` | **Response:**<br>`200 OK`<br>`Content-Type: application/json`<br><br>`{ "data": [{ "id": "conv_...", "created_at": "...", ... }], "page": 0, "page_size": 100 }`<br><br>Also: `GET /v1/conversations/{id}`, `/history` (entries), `/messages` | [docs.mistral.ai][1] |
| **AWS Bedrock — Agents Runtime** | **Request:**<br>`POST https://bedrock-agent-runtime.{region}.amazonaws.com/sessions?maxResults=20&nextToken=...`<br><br>**Headers:**<br>(SigV4) | **Response:**<br>`200 OK`<br>JSON list of `{ sessionId, sessionStatus, createdAt, lastUpdatedAt }` with `nextToken` | [List Sessions][4] |
| **OpenAI — Responses API** | **Request:**<br>*(none for "conversations")* | **Response:**<br>*(No public list-all responses/conversations—manage your own index.)* | - |

#### Delete Conversation

| Provider | Request | Response | Documentation |
|----------|---------|----------|---------------|
| **Mistral — Conversations** | **Request:**<br>*(none documented)* | **Response:**<br>*(Conversations delete isn't in the public API docs.)* | - |
| **AWS Bedrock — Agents Runtime** | **Request (end):**<br>`PATCH https://bedrock-agent-runtime.{region}.amazonaws.com/sessions/{sessionId}`<br><br>**Request (delete):**<br>`DELETE https://bedrock-agent-runtime.{region}.amazonaws.com/sessions/{sessionId}`<br><br>**Headers:**<br>(SigV4) | **Response:**<br>End → `200 OK` JSON `{ sessionStatus: "ENDED" }`<br>Delete → `200 OK` empty body | [End Session][5] |
| **OpenAI — Responses API** | **Request:**<br>`DELETE https://api.openai.com/v1/responses/{response_id}`<br><br>**Headers:**<br>`Authorization: Bearer OPENAI_API_KEY` | **Response:**<br>`200 OK` (deletes **one** stored response; not a whole "thread") | [Delete][10] |

### Streaming Operations (RPC with Streaming)

#### Start New Conversation

| Provider | Request | Response | Documentation |
|----------|---------|----------|---------------|
| **Mistral — Conversations** | **Request:**<br>`POST https://api.mistral.ai/v1/conversations#stream`<br><br>**Headers:**<br>`Authorization: Bearer MISTRAL_API_KEY`<br>`Content-Type: application/json`<br>`Accept: text/event-stream`<br><br>**Body:**<br>`{ "agent_id": "ag_12345", "inputs": [{ "type": "message.input", "role": "user", "content": "Plan a 3-day NYC trip" }], "store": true, "stream": true }` | **Response:**<br>`200 OK`<br>`Content-Type: text/event-stream`<br>`Transfer-Encoding: chunked`<br><br>**SSE Events:**<br>`event: conversation.response.started`<br>`data: {"type":"conversation.response.started","conversation_id":"conv_..."}`<br><br>`event: message.output.delta`<br>`data: {"type":"message.output.delta","id":"msg_...","role":"assistant","content":"..."}`<br><br>`event: conversation.response.done`<br>`data: {"type":"conversation.response.done","usage":{...}}` | [docs.mistral.ai][1] |
| **AWS Bedrock — Agents Runtime** | **Request:**<br>*Same as REST* (Bedrock streams via chunked responses)<br><br>**Headers:**<br>Same as REST<br><br>**Body:**<br>*Same as REST* (streaming controlled by `streamingConfigurations`) | **Response:**<br>`200 OK`<br>`Transfer-Encoding: chunked`<br>`Content-Type: application/json`<br><br>**Chunked stream** with final text in `chunk.bytes` | [AWS Documentation][2] |
| **OpenAI — Responses API** | **Request:**<br>`POST https://api.openai.com/v1/responses`<br><br>**Headers:**<br>`Authorization: Bearer OPENAI_API_KEY`<br>`Content-Type: application/json`<br>`Accept: text/event-stream`<br><br>**Body:**<br>`{ "model": "gpt-4.1-mini", "input": [{ "role": "user", "content": [{ "type": "text", "text": "Plan a 3-day NYC trip" }] }], "stream": true, "store": true }` | **Response:**<br>`200 OK`<br>`Content-Type: text/event-stream`<br>`Transfer-Encoding: chunked`<br><br>**Typed SSE events:**<br>`response.created`, `response.output_text.delta`, `response.completed` | [OpenAI Platform][6], [Streaming][7], [GitHub][8] |

#### Continue Existing Conversation

| Provider | Request | Response | Documentation |
|----------|---------|----------|---------------|
| **Mistral — Conversations** | **Request:**<br>`POST https://api.mistral.ai/v1/conversations/{conversation_id}#stream`<br><br>**Headers:**<br>`Authorization: Bearer MISTRAL_API_KEY`<br>`Content-Type: application/json`<br>`Accept: text/event-stream`<br><br>**Body:**<br>`{ "inputs": [{ "type": "message.input", "role": "user", "content": "Add museum options" }], "store": true, "stream": true }` | **Response:**<br>SSE events (`message.output.delta`, `conversation.response.done`, tool events) | [docs.mistral.ai][1] |
| **AWS Bedrock — Agents Runtime** | **Request:**<br>*Same as "Continue (REST)"*<br><br>**Headers/Body:**<br>Same as continue REST | **Response:**<br>`200 OK`<br>`Transfer-Encoding: chunked`<br><br>Chunked response | [AWS Documentation][2] |
| **OpenAI — Responses API** | **Request:**<br>`POST https://api.openai.com/v1/responses`<br><br>**Headers:**<br>Same as start stream (`Accept: text/event-stream`)<br><br>**Body:**<br>Same as continue REST, plus `"stream": true` | **Response:**<br>SSE events as above | [OpenAI Platform][6], [Streaming][7], [GitHub][8] |

---

## Advanced Patterns

### Interrupts & Resume

> **Industry Standard**: No separate "resume endpoints" - all providers resume on the same endpoint family with special payloads for tool results, MCP approvals, or return-control results.

#### REST Interrupts & Resume

| Provider | Interrupt Types | Resume Pattern | Documentation |
|----------|----------------|----------------|---------------|
| **Mistral — Conversations** | **Interrupts:** Tool execution (`tool.execution.*`) and agent handoffs (`agent.handoff.*`)<br><br>**Server-handled:** Default `handoff_execution:"server"` — platform executes internally<br><br>**Client-handled:** Set `handoff_execution:"client"` for explicit resume path | **Resume (REST):**<br>`POST https://api.mistral.ai/v1/conversations/{conversation_id}`<br><br>**Body:**<br>`{ "inputs": [{ "object": "entry", "type": "function.result", "name": "get_weather", "output": { "tempC": 21 } }], "store": true, "stream": false }` | [Agents Handoffs][3] |
| **AWS Bedrock — Agents Runtime** | **Interrupts:** Return-control from action groups (HITL/your code path)<br><br>**Signal:** `returnControl` with `invocationInputs[]` and `invocationId` | **Resume (REST):**<br>`POST .../sessions/{sessionId}/text`<br><br>**Body:**<br>`{ "sessionState": { "invocationId": "79e0...", "returnControlInvocationResults": [{ "functionResult": { "actionGroup": "WeatherAPIs", "function": "getWeather", "responseBody": { "TEXT": { "body": "It's rainy in Seattle today." } } } }] } }` | [Return Control][11] |
| **OpenAI — Responses API** | **Interrupts:** Tool calls (your tools or built-in) and MCP approvals for remote MCP servers | **Resume (REST):**<br>`POST https://api.openai.com/v1/responses`<br><br>**Body (tool result):**<br>`{ "model": "gpt-4.1", "previous_response_id": "resp_abc123", "input": [{ "type": "tool_result", "tool_call_id": "call_789", "output": { "data": "..." } }] }`<br><br>**Body (MCP approval):**<br>Create new response with `mcp_approval_response` item | [Microsoft Learn][12], [OpenAI Cookbook][13] |

#### Streaming Interrupts & Resume

| Provider | Interrupt Types | Resume Pattern | Documentation |
|----------|----------------|----------------|---------------|
| **Mistral — Conversations** | **Interrupts:** Tool execution (`tool.execution.*`) and agent handoffs (`agent.handoff.*`)<br><br>**Server-handled:** Default `handoff_execution:"server"` — platform executes internally<br><br>**Client-handled:** Set `handoff_execution:"client"` for explicit resume path | **Resume (Streaming):**<br>Same URL/body as REST with `Accept: text/event-stream` and `"stream": true`<br><br>**Response:**<br>`conversation.response.started` → deltas → `done` | [Agents Handoffs][3] |
| **AWS Bedrock — Agents Runtime** | **Interrupts:** Return-control from action groups (HITL/your code path)<br><br>**Signal:** `returnControl` with `invocationInputs[]` and `invocationId` | **Resume (Streaming):**<br>Same URL/body as REST; optionally enable `"streamingConfigurations": { "streamFinalResponse": true }` | [Return Control][11] |
| **OpenAI — Responses API** | **Interrupts:** Tool calls (your tools or built-in) and MCP approvals for remote MCP servers | **Resume (Streaming):**<br>Stream surfaces tool/approval events; stop consuming and immediately POST resume call as REST<br><br>**Response:**<br>New stream continues the turn | [Microsoft Learn][12], [OpenAI Cookbook][13] |

### State Management

**Key Architectural Decisions:**
- **No Separate Resume Endpoints**: Industry standard - resume on same endpoint family with special payloads
- **Interrupt Patterns**: Tool calls, MCP approvals, return-control, and agent handoffs
- **Event Semantics**: Typed SSE events vs structured chunked JSON
- **Auth Posture**: Bearer tokens (most) vs AWS SigV4 vs Google OAuth2

---

## Implementation Notes

> * **RPC Nature**: All these "REST" APIs are fundamentally RPC protocols - expect function-call semantics rather than resource-oriented design.
> * **Mistral streaming** has explicit `#stream` endpoints for **start** and **append**; the SSE stream includes a `conversation.response.started` event that carries the `conversation_id`, letting you capture it even on the first streamed turn. ([docs.mistral.ai][1])  
> * **AWS Bedrock**: you *start* a session by picking a new `sessionId` in the URL; you *continue* by reusing it; *end then delete* via **EndSession** → **DeleteSession**. Streaming is a **chunked** JSON stream (not SSE). ([AWS Documentation][2]) . 
> * **OpenAI Responses**: continuation is by one **`previous_response_id`** (a single stored response), not a conversation object; delete is **per response**. ([OpenAI Platform][6]) . 
> * **Industry Standard**: No separate "resume endpoints" - all providers resume on the same endpoint family with special payloads for tool results, MCP approvals, or return-control results.
> * **Streaming Patterns**: The `"stream": true` pattern is universal, but Mistral's additional URL requirements (`#stream`) and Accept headers show inconsistent design thinking.

---

## Documentation References

[1]: https://docs.mistral.ai/api/ "Mistral AI API"
[2]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_InvokeAgent.html "AWS Bedrock InvokeAgent"
[3]: https://docs.mistral.ai/agents/handoffs/ "Agents Handoffs | Mistral AI"
[4]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_ListSessions.html "AWS Bedrock ListSessions"
[5]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_EndSession.html "AWS Bedrock EndSession"
[6]: https://platform.openai.com/docs/guides/migrate-to-responses?utm_source=chatgpt.com "OpenAI Responses API"
[7]: https://platform.openai.com/docs/guides/streaming-responses?utm_source=chatgpt.com "OpenAI Streaming"
[8]: https://openai.github.io/openai-agents-python/streaming/?utm_source=chatgpt.com "OpenAI Agents SDK"
[9]: https://platform.openai.com/docs/guides/conversation-state?utm_source=chatgpt.com "OpenAI Conversation State"
[10]: https://platform.openai.com/docs/api-reference/responses/delete?utm_source=chatgpt.com "OpenAI Delete Response"
[11]: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-returncontrol.html "Return control to the agent developer by sending elicited information in an InvokeAgent response - Amazon Bedrock"
[12]: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses "Azure OpenAI Responses API - Azure OpenAI | Microsoft Learn"
[13]: https://cookbook.openai.com/examples/mcp/mcp_tool_guide?utm_source=chatgpt.com "Guide to Using the Responses API's MCP Tool"
[14]: https://docs.anthropic.com/en/docs/build-with-claude/streaming?utm_source=chatgpt.com "Streaming Messages - Anthropic"
[15]: https://docs.cohere.com/reference/chat-stream-v1?utm_source=chatgpt.com "Chat with Streaming Outputs (API V1) | Cohere"
[16]: https://ai.google.dev/api/generate-content "Generating content | Gemini API | Google AI for Developers"
[17]: https://cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-textgen-with-txt-stream?utm_source=chatgpt.com "Generate streaming text content with Generative Model - Google Cloud"
[18]: https://console.groq.com/docs/openai?utm_source=chatgpt.com "OpenAI Compatibility - GroqDocs"
[19]: https://openrouter.ai/docs/api-reference/streaming?utm_source=chatgpt.com "API Streaming | Real-time Model Responses in OpenRouter | OpenRouter"
[20]: https://platform.openai.com/docs/guides/streaming-responses?utm_source=chatgpt.com "Streaming API responses - OpenAI"
[21]: https://docs.mistral.ai/agents/agents_basics/?utm_source=chatgpt.com "Agents & Conversations | Mistral AI"
[22]: https://openai.github.io/openai-agents-python/streaming/?utm_source=chatgpt.com "Streaming - OpenAI Agents SDK"
[23]: https://github.com/mistralai/client-python/blob/master/docs/sdks/agents/README.md?utm_source=chatgpt.com "client-python/docs/sdks/agents/README.md at main - GitHub"
[24]: https://platform.openai.com/docs/guides/tools-remote-mcp?utm_source=chatgpt.com "Remote MCP - OpenAI API"
[25]: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agent-runtime/client/invoke_agent.html?utm_source=chatgpt.com "invoke_agent - Boto3 1.40.12 documentation"
[26]: https://community.openai.com/t/responses-api-question-about-managing-conversation-state-with-previous-response-id/1141633?utm_source=chatgpt.com "Responses API: Question about managing conversation state with previous ..."
