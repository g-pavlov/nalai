You're right—omitting fields like `background`, `include`, `instructions`, `parallel_tool_calls`, etc. could mislead. Here's a **comprehensive, field-level** comparison, formatted as you asked:

* Left column = **OpenAI fields** (Responses / Conversations).
* Middle = **your analogue** (from your OpenAPI).
* Then **Status** (`match` / `partial` / `not supported`) and short notes.
* Final table lists **your extra fields** (not in OpenAI).

I'm keeping "match" where the top-level structure/semantics line up (no string-by-string nitpicks).

# Responses.create — request

| OpenAI field                                                             | Your analogue                                                | Status  | Notes                                                                                                                |
| ------------------------------------------------------------------------ | ------------------------------------------------------------ | ------- | -------------------------------------------------------------------------------------------------------------------- |
| `background`                                                             | —                                                            | not supported     | Not supported at the moment. Used to support long-running async "background mode". ([OpenAI Platform][7], [OpenAI][8])                             |
| `conversation`                                                           | `conversation_id`                                            | partial | Same concept but need to match the property name and potentially its structure to accept object|str. The object has a single property - id: str (the conversation id) ([OpenAI Platform][4])                                                       |
| `include` (e.g., return file-search results inline)                      | —                                                            | not supported     | By design - the agent controls this, not the client. ([OpenAI Platform][14])                               |
| `input` str or item-list (message or item or ref)                                | `input` (str or list)                                        | match | Supports both string (implicit human) and structured message arrays with optional `type: "message"` field, equivalent to OpenAI's format. ([OpenAI Platform][2])                                       |
| `instructions` (system-level prompt)                                     | —                                                            | not supported     | By design - the agent should not accept system prompts. ([OpenAI Platform][3])                     |
| `max_output_tokens`                                                      | `model_settings.max_tokens`                                  | not supported     | By design - the agent controls this, not the client.  ([Microsoft Learn][12])                                                            |
| `max_tool_calls`                                                         | -                                                            | not supported     | By design - the agent controls this, not the client.                                                             |
| `metadata` (request-level)                                               | —                                                            | not supported     | Useful for tagging responses; not in our request model. Not supported at the moment. ([OpenAI Community][5])                                     |
| `model`                                                                  | `model`                                                      | match   | Same purpose. ([OpenAI Platform][1])                                                                                 |
| `parallel_tool_calls`                                                    | —                                                            | not supported     | By design - the agent controls this, not the client. ([OpenAI Platform][10])                                             |
| `previous_response_id`                                                   | `previous_response_id`                                        | match | Same response-level branching semantics. OpenAI chains by **response**, not message. ([OpenAI Platform][4]) |
| `prompt`                                                                 | —                                                            | not supported     | Not supported at the moment                              |
| `prompt_cache_key`                                                       | —                                                            | not supported     | Not supported at the moment                              |
| `reasoning`                                                              | —                                        | not supported     | By design - the agent controls this, not the client. ([OpenAI Platform][16])                                                          |
| `response_format` (e.g., `json_schema`)                                  | —                                                            | not supported     | By design - the agent controls this, not the client. ([OpenAI Platform][11])                                                        |
| `safety_identifier`                                                      | —                                                            | not supported     | Not supported.    |
| `service_tier`                                                           | —                                                            | not supported     | By design - the agent controls this, not the client. ([OpenAI Platform][15])                                                          |
| `store`                                                                  | `store`                                                      | match   | Same persistence toggle. ([OpenAI Platform][6])                                                                      |
| `stream` (boolean / config)                                              | `stream: "full" \| "events" \| "off"`                        | partial | Transport aligns (SSE); value shape differs. Need to change to supporting stream as in OpenAI API, together with `stream_options` with the currently implemented semantics of `stream` in the agent. ([OpenAI Platform][17])                                                 |
| `temperature`                                                            | `model_settings.temperature`                                 | not supported     | By design - the agent controls this, not the client. ([OpenAI Platform][13])                                                    |
| `text`                                                                   | —                                                            | not supported     | By design - the agent controls this, not the client.   |
| `tool_choice`                                                            | —                                                            | not supported     | By design - tool_choice is predefine by the agent's use of the model, not its client. ([OpenAI Platform][9])                          |
| `tools[]` (built-ins + function calling + MCP)                           | —                                                            | not supported     | By design - the agent tools are predefined. It's used to declare request-level tools to be wire-compatible. ([OpenAI Platform][9])                                            |
| `tools:web_search / file_search / code_interpreter / computer_use / MCP` | —                                                            | not supported     | By design - Not used by the agent ([OpenAI Platform][9])                                              |
| `top_logprobs`                                                           | —                                                            | not supported     | By design - the agent controls this, not the client.   |
| `top_p`                                                                  | —                            | not supported     |  By design - the agent controls this, not the client. ([OpenAI Platform][13])                          |
| `truncation`                                                             | —                                                            | not supported     | By design - the agent controls this, not the client.   |

**Refs:** OpenAI Responses create & streaming, tools, structured outputs, conversation state, background mode. ([OpenAI Platform][1])

---

# Responses.create — response object

| OpenAI field                                                                                 | Your analogue                                       | Status        | Notes                                                  |
| -------------------------------------------------------------------------------------------- | --------------------------------------------------- | ------------- | ------------------------------------------------------ |
| `background`                                                                                 | -                                                   | not supported | — Not supported at the moment by design                                                 |
| `conversation`                                                                               | `conversation_id`                                       | partial | — need to align the structure and field names ([OpenAI Platform][4])                               |
| `created_at`                                                                                 | `created_at`                                            | match   | — ([OpenAI Platform][1])                               |
| `error`                                                                                      | -                                                   | partial | — In metadata.error. String not an object. Need to align the structure and placement                            |
| `id`                                                                                         | `id`                                                    | match   | — ([OpenAI Platform][1])                               |
| `incomplete_details`                                                                         | -                                                   | not supported | — Need to align the structure and placement                            |
| `instructions`                                                                               | -                                                   | not supported | — By design                            |
| `max_output_tokens`                                                                               | -                                                   | not supported | — By design                            |
| `max_tool_calls`                                                                               | -                                                   | not supported | — By design                            |
| `metadata`                                                                                   | `metadata`                              | not supported   | Same concept - different purpose, needs alignment ([OpenAI Platform][1]) |
| `model`                                                                                      | `model`                                                 | match   | — ([OpenAI Platform][1])                               |
| `object`                                                                               | -                                                   | not supported | — needs alignment. no useful purpose                            |
| `output[]` (typed items: text/image/audio/tool\_calls)                                       | `output[]` (MessageOutput with `content[]` text blocks) | partial | Extend content types to match. ([OpenAI Platform][2])  |
| `parallel_tool_calls`                                                                               | -                                                   | not supported | — By design                            |
| `previous_response_id`                                                                               | -                                                   | not supported | — Needs to be added                            |
| `prompt`                                                                               | -                                                   | not supported | — By design                            |
| `prompt_cache_key`                                                                               | -                                                   | not supported | — By design                            |
| `reasoning`                                                                               | -                                                   | not supported | — By design                            |
| `safety_identifier`                                                                               | -                                                   | not supported | — By design                            |
| `service_tier`                                                                               | -                                                   | not supported | — By design                            |
| `status`  (completed, failed, in_progress, cancelled, queued, or incomplete)                 | `status` (`completed`/`processing`/`error`/...)         | partial | Enum names may differ. ([OpenAI Platform][1])          |
| `temperature`                                                                               | -                                                   | not supported | — By design                            |
| `text`                                                                               | -                                                   | not supported | — By design                            |
| `tool_choice`                                                                               | -                                                   | not supported | — By design                            |
| `tools`                                                                               | -                                                   | not supported | — By design                            |
| `top_logprobs`                                                                               | -                                                   | not supported | — By design                            |
| `top_p`                                                                               | -                                                   | not supported | — By design                            |
| `truncation`                                                                               | -                                                   | not supported | — By design                            |
| `usage`                                                                                      | `usage`                                                 | match   | — ([OpenAI Platform][1])                               |
| Streaming events (`response.created`, `response.output_text.delta`, `response.completed`, …) | Same event names in SSE example                         | match   | Taxonomy aligns. ([OpenAI Platform][17], [GitHub][18]) |

**Refs:** Responses object & events. ([OpenAI Platform][17], [GitHub][18])

---

# Conversations — endpoints & fields

| OpenAI (Conversations)                                          | Your analogue                                    | Status  | Notes                                                                                                                               |
| --------------------------------------------------------------- | ------------------------------------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `DELETE /v1/conversations/{id}`                                 | `DELETE /api/v1/conversations/{conversation_id}` | match   | — ([OpenAI Platform][4])                                                                                                            |
| `GET /v1/conversations` (list)                                  | `GET /api/v1/conversations`                      | match   | Listing aligns; pagination may differ. ([OpenAI Platform][4])                                                                       |
| `GET /v1/conversations/{id}`                                    | `GET /api/v1/conversations/{conversation_id}`    | match   | Same idea (messages + metadata). ([OpenAI Platform][4])                                                                             |
| `items[]` (messages, tool calls, tool outputs, reasoning items) | `messages[]`                                     | partial | You cover messages; OpenAI "items" also include richer types (e.g., reasoning items). ([OpenAI Platform][4], [OpenAI Cookbook][19]) |
| `POST /v1/conversations` (create)                               | — (implicit via `/responses`)                    | partial | Add explicit POST for drop-in parity. ([OpenAI Platform][4])                                                                        |
| `title` / metadata updates (`PATCH`)                            | —                                                | gap     | Consider `PATCH` to edit title/metadata. ([OpenAI Platform][4])                                                                     |

---


# Your extensions (present in your API, not in OpenAI)

| Your field                                        | OpenAI analogue                | Status    | Notes                                                                              |
| ------------------------------------------------- | ------------------------------ | --------- | ---------------------------------------------------------------------------------- |
| `disable_cache`                                   | —                              | extension | Vendor-specific toggle.                                                            |
| `interrupt` (response-level)                      | —                              | extension | Custom interrupt surface; OpenAI uses events/state. ([OpenAI Platform][17])        |
| `model_settings` (container)                      | Top-level params               | extension | Holds `temperature`/`max_tokens`; different shape.                                 |
| `previous_response_id`                             | `previous_response_id`         | match | Same response-level branching semantics. OpenAI chains by response id. ([OpenAI Platform][4]) |
| `ToolDecisionInput` (accept/reject/edit/feedback) | `tool_choice` (different flow) | extension | Post-emit decision step not in OpenAI spec. ([OpenAI Platform][9])                 |
| Conversation `preview`, `last_accessed`, `status` | —                              | extension | Extra convenience fields beyond OpenAI's minimal metadata.                         |

---


**Sources:** OpenAI Responses API (create, streaming), tools (web/file/MCP), function calling & parallel calls, structured outputs, conversation state, background mode, reasoning controls, service tier. ([OpenAI Platform][1])

[1]: https://platform.openai.com/docs/api-reference/responses/create?utm_source=chatgpt.com "OpenAI Platform"
[2]: https://platform.openai.com/docs/guides/migrate-to-responses?utm_source=chatgpt.com "Migrating to Responses API - OpenAI API"
[3]: https://platform.openai.com/docs/guides/text?api-mode=responses&prompt-example=prompt&utm_source=chatgpt.com "Text generation - OpenAI API"
[4]: https://platform.openai.com/docs/guides/conversation-state?utm_source=chatgpt.com "Conversation state - OpenAI API"
[5]: https://community.openai.com/t/does-the-metadata-field-in-response-api-appear-in-webhook-payloads/1347054?utm_source=chatgpt.com "Does the metadata field in Response API appear in webhook payloads?"
[6]: https://platform.openai.com/docs/guides/your-data?utm_source=chatgpt.com "Data controls in the OpenAI platform - OpenAI API"
[7]: https://platform.openai.com/docs/guides/background?utm_source=chatgpt.com "Background mode - OpenAI API"
[8]: https://openai.com/index/new-tools-and-features-in-the-responses-api/?utm_source=chatgpt.com "New tools and features in the Responses API - OpenAI"
[9]: https://platform.openai.com/docs/guides/tools?api-mode=responses&utm_source=chatgpt.com "OpenAI Platform"
[10]: https://platform.openai.com/docs/guides/function-calling/configuring-parallel-function-calling?utm_source=chatgpt.com "Function calling - OpenAI API"
[11]: https://platform.openai.com/docs/guides/structured-outputs?utm_source=chatgpt.com "Structured model outputs - OpenAI API"
[12]: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/reasoning?utm_source=chatgpt.com "Azure OpenAI reasoning models - GPT-5 series, o3-mini, o1, o1-mini ..."
[13]: https://platform.openai.com/docs/advanced-usage/parameter-details?utm_source=chatgpt.com "Advanced usage - OpenAI API"
[14]: https://platform.openai.com/docs/guides/tools-file-search?utm_source=chatgpt.com "File search - OpenAI API"
[15]: https://platform.openai.com/docs/guides/flex-processing?api-mode=responses&utm_source=chatgpt.com "Flex processing - OpenAI API"
[16]: https://platform.openai.com/docs/guides/reasoning?api-mode=responses&lang=javascript&utm_source=chatgpt.com "Reasoning models - OpenAI API"
[17]: https://platform.openai.com/docs/guides/streaming-responses?utm_source=chatgpt.com "Streaming API responses - OpenAI API"
[18]: https://github.com/openai/openai-agents-python/blob/main/docs/streaming.md?utm_source=chatgpt.com "openai-agents-python/docs/streaming.md at main - GitHub"
[19]: https://cookbook.openai.com/examples/responses_api/reasoning_items?utm_source=chatgpt.com "Better performance from reasoning models using the Responses API"
