"""
Integration test for chunk accumulation with streaming tool calls.

This test simulates the OpenAI streaming behavior where tool call arguments
are streamed piece by piece, causing invalid_tool_call errors until complete.
"""

import json
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from nalai.core.tool_node import ChunkAccumulatingToolNode
from nalai.server.streaming_processor import StreamingEventProcessor


class TestChunkAccumulationIntegration:
    """Integration test for chunk accumulation with streaming tool calls."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock HTTP tool
        self.mock_http_tool = Mock()
        self.mock_http_tool.name = "http_request"
        self.mock_http_tool.invoke.return_value = "HTTP response data"

        # Create the tool node
        self.tool_node = ChunkAccumulatingToolNode([self.mock_http_tool])

        # Create the streaming processor
        self.processor = StreamingEventProcessor(self.tool_node)

    @pytest.mark.parametrize(
        "streaming_events, expected_emitted_events, tool_call_id, expected_args, tool_result_name, tool_result_output, final_content_snippet",
        [
            # Single tool call, OpenAI streaming style
            (
                [
                    # Initial tool call
                    {
                        "event": "on_chat_model_stream",
                        "data": {
                            "chunk": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "name": "http_request",
                                        "args": {},
                                        "id": "call_abc123",
                                        "type": "tool_call",
                                    }
                                ],
                                "invalid_tool_calls": [],
                                "tool_call_chunks": [
                                    {
                                        "name": "http_request",
                                        "args": "",
                                        "id": "call_abc123",
                                        "index": 0,
                                        "type": "tool_call_chunk",
                                    }
                                ],
                            }
                        },
                    },
                    # Piece by piece JSON building (real OpenAI behavior)
                    {
                        "event": "on_chat_model_stream",
                        "data": {
                            "chunk": {
                                "content": "",
                                "tool_calls": [],
                                "invalid_tool_calls": [
                                    {
                                        "name": None,
                                        "args": '{"url": "https://api.example.com/products"',
                                        "id": None,
                                        "error": None,
                                        "type": "invalid_tool_call",
                                    }
                                ],
                                "tool_call_chunks": [
                                    {
                                        "name": None,
                                        "args": '{"url": "https://api.example.com/products"',
                                        "id": None,
                                        "index": 0,
                                        "type": "tool_call_chunk",
                                    }
                                ],
                            }
                        },
                    },
                    {
                        "event": "on_chat_model_stream",
                        "data": {
                            "chunk": {
                                "content": "",
                                "tool_calls": [],
                                "invalid_tool_calls": [
                                    {
                                        "name": None,
                                        "args": ', "method": "GET"',
                                        "id": None,
                                        "error": None,
                                        "type": "invalid_tool_call",
                                    }
                                ],
                                "tool_call_chunks": [
                                    {
                                        "name": None,
                                        "args": ', "method": "GET"',
                                        "id": None,
                                        "index": 0,
                                        "type": "tool_call_chunk",
                                    }
                                ],
                            }
                        },
                    },
                    {
                        "event": "on_chat_model_stream",
                        "data": {
                            "chunk": {
                                "content": "",
                                "tool_calls": [],
                                "invalid_tool_calls": [
                                    {
                                        "name": None,
                                        "args": ', "headers": {"Authorization": "Bearer token"',
                                        "id": None,
                                        "error": None,
                                        "type": "invalid_tool_call",
                                    }
                                ],
                                "tool_call_chunks": [
                                    {
                                        "name": None,
                                        "args": ', "headers": {"Authorization": "Bearer token"',
                                        "id": None,
                                        "index": 0,
                                        "type": "tool_call_chunk",
                                    }
                                ],
                            }
                        },
                    },
                    {
                        "event": "on_chat_model_stream",
                        "data": {
                            "chunk": {
                                "content": "",
                                "tool_calls": [],
                                "invalid_tool_calls": [
                                    {
                                        "name": None,
                                        "args": "}}",
                                        "id": None,
                                        "error": None,
                                        "type": "invalid_tool_call",
                                    }
                                ],
                                "tool_call_chunks": [
                                    {
                                        "name": None,
                                        "args": "}}",
                                        "id": None,
                                        "index": 0,
                                        "type": "tool_call_chunk",
                                    }
                                ],
                            }
                        },
                    },
                    # Tool result event
                    {
                        "event": "on_tool_end",
                        "data": {
                            "name": "http_request",
                            "tool_call_id": "call_abc123",
                            "output": "HTTP response data",
                        },
                    },
                    # Final LLM response with content
                    {
                        "event": "on_chat_model_stream",
                        "data": {
                            "chunk": {
                                "content": "Here are the products from the API: HTTP response data",
                                "tool_calls": [],
                                "invalid_tool_calls": [],
                                "tool_call_chunks": [],
                            }
                        },
                    },
                ],
                [
                    {
                        "event": "on_tool_end",
                        "data": {
                            "name": "http_request",
                            "tool_call_id": "call_abc123",
                            "output": "HTTP response data",
                        },
                    },
                    {
                        "event": "on_chat_model_stream",
                        "data": {
                            "chunk": {
                                "content": "Here are the products from the API: HTTP response data"
                            }
                        },
                    },
                ],
                "call_abc123",
                {
                    "url": "https://api.example.com/products",
                    "method": "GET",
                    "headers": {"Authorization": "Bearer token"},
                },
                "http_request",
                "HTTP response data",
                "Here are the products",
            ),
            # Add more table-driven cases here for multiple tool calls, Bedrock/Ollama, etc.
        ],
    )
    def test_streaming_event_processor_table(
        self,
        streaming_events,
        expected_emitted_events,
        tool_call_id,
        expected_args,
        tool_result_name,
        tool_result_output,
        final_content_snippet,
    ):
        # Reset processor and tool node
        self.processor.clear_buffers()
        self.tool_node.clear_buffers()
        emitted_events = []
        for _i, event in enumerate(streaming_events):
            result = self.processor.process_event(event)
            if result is not None:
                emitted_events.append(result)
        # Check emitted events match expected
        assert len(emitted_events) == len(expected_emitted_events)
        for actual, expected in zip(
            emitted_events, expected_emitted_events, strict=False
        ):
            assert actual["event"] == expected["event"]
            if actual["event"] == "on_tool_end":
                assert actual["data"]["name"] == tool_result_name
                assert actual["data"]["tool_call_id"] == tool_call_id
                assert tool_result_output in actual["data"]["output"]
            if actual["event"] == "on_chat_model_stream":
                assert final_content_snippet in actual["data"]["chunk"]["content"]
        # Check tool call buffer
        tool_node_buffers = self.tool_node.get_buffered_tool_calls()
        assert tool_call_id in tool_node_buffers
        parsed_args = json.loads(tool_node_buffers[tool_call_id])
        assert parsed_args == expected_args

    def test_multiple_tool_calls_streaming(self):
        """Test handling multiple tool calls streaming simultaneously."""
        # Simulate two tool calls streaming at the same time (real behavior)
        streaming_events = [
            # Initial tool calls
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "",
                        "tool_calls": [
                            {
                                "name": "http_request",
                                "args": {},
                                "id": "call_1",
                                "type": "tool_call",
                            },
                            {
                                "name": "http_request",
                                "args": {},
                                "id": "call_2",
                                "type": "tool_call",
                            },
                        ],
                        "invalid_tool_calls": [],
                        "tool_call_chunks": [
                            {
                                "name": "http_request",
                                "args": "",
                                "id": "call_1",
                                "index": 0,
                                "type": "tool_call_chunk",
                            },
                            {
                                "name": "http_request",
                                "args": "",
                                "id": "call_2",
                                "index": 1,
                                "type": "tool_call_chunk",
                            },
                        ],
                    }
                },
            },
            # Tool call 1 chunks
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "",
                        "tool_calls": [],
                        "invalid_tool_calls": [
                            {
                                "name": None,
                                "args": '{"url": "https://api1.com"',
                                "id": None,
                                "error": None,
                                "type": "invalid_tool_call",
                            }
                        ],
                        "tool_call_chunks": [
                            {
                                "name": None,
                                "args": '{"url": "https://api1.com"',
                                "id": None,
                                "index": 0,
                                "type": "tool_call_chunk",
                            }
                        ],
                    }
                },
            },
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "",
                        "tool_calls": [],
                        "invalid_tool_calls": [
                            {
                                "name": None,
                                "args": "}",
                                "id": None,
                                "error": None,
                                "type": "invalid_tool_call",
                            }
                        ],
                        "tool_call_chunks": [
                            {
                                "name": None,
                                "args": "}",
                                "id": None,
                                "index": 0,
                                "type": "tool_call_chunk",
                            }
                        ],
                    }
                },
            },
            # Tool call 2 chunks
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "",
                        "tool_calls": [],
                        "invalid_tool_calls": [
                            {
                                "name": None,
                                "args": '{"url": "https://api2.com"',
                                "id": None,
                                "error": None,
                                "type": "invalid_tool_call",
                            }
                        ],
                        "tool_call_chunks": [
                            {
                                "name": None,
                                "args": '{"url": "https://api2.com"',
                                "id": None,
                                "index": 1,
                                "type": "tool_call_chunk",
                            }
                        ],
                    }
                },
            },
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "",
                        "tool_calls": [],
                        "invalid_tool_calls": [
                            {
                                "name": None,
                                "args": "}",
                                "id": None,
                                "error": None,
                                "type": "invalid_tool_call",
                            }
                        ],
                        "tool_call_chunks": [
                            {
                                "name": None,
                                "args": "}",
                                "id": None,
                                "index": 1,
                                "type": "tool_call_chunk",
                            }
                        ],
                    }
                },
            },
            # Tool results
            {
                "event": "on_tool_end",
                "data": {
                    "name": "http_request",
                    "tool_call_id": "call_1",
                    "output": "API1 response",
                },
            },
            {
                "event": "on_tool_end",
                "data": {
                    "name": "http_request",
                    "tool_call_id": "call_2",
                    "output": "API2 response",
                },
            },
            # Final LLM response
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "Combined results: API1 response and API2 response",
                        "tool_calls": [],
                        "invalid_tool_calls": [],
                        "tool_call_chunks": [],
                    }
                },
            },
        ]

        # Process events
        emitted_events = []
        for event in streaming_events:
            result = self.processor.process_event(event)
            if result is not None:
                emitted_events.append(result)

        # Verify we got the meaningful events
        assert len(emitted_events) == 4, (
            f"Expected 4 meaningful events, got {len(emitted_events)}"
        )

        # Check tool results
        tool_events = [e for e in emitted_events if e["event"] == "on_tool_end"]
        assert len(tool_events) == 2
        assert tool_events[0]["data"]["tool_call_id"] == "call_1"
        assert tool_events[1]["data"]["tool_call_id"] == "call_2"

        # Check final content
        content_events = [
            e
            for e in emitted_events
            if e["event"] == "on_chat_model_stream" and e["data"]["chunk"]["content"]
        ]
        assert len(content_events) == 1
        assert "Combined results" in content_events[0]["data"]["chunk"]["content"]

        # Check for complete tool calls in the tool node's buffer
        tool_node_buffers = self.tool_node.get_buffered_tool_calls()
        assert "call_1" in tool_node_buffers
        assert "call_2" in tool_node_buffers
        assert json.loads(tool_node_buffers["call_1"]) == {"url": "https://api1.com"}
        assert json.loads(tool_node_buffers["call_2"]) == {"url": "https://api2.com"}

    def test_bedrock_ollama_behavior_simulation(self):
        """
        Test that Bedrock/Ollama behavior (complete tool calls) works normally
        without needing chunk accumulation.
        """
        # Simulate Bedrock/Ollama behavior - complete tool call in one chunk
        streaming_events = [
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "",
                        "tool_calls": [
                            {
                                "name": "http_request",
                                "args": {
                                    "url": "https://api.example.com",
                                    "method": "POST",
                                    "data": {"key": "value"},
                                },
                                "id": "call_xyz789",
                                "type": "tool_call",
                            }
                        ],
                        "invalid_tool_calls": [],
                        "tool_call_chunks": [
                            {
                                "name": "http_request",
                                "args": '{"url": "https://api.example.com", "method": "POST", "data": {"key": "value"}}',
                                "id": "call_xyz789",
                                "index": 0,
                                "type": "tool_call_chunk",
                            }
                        ],
                    }
                },
            },
            # Tool result
            {
                "event": "on_tool_end",
                "data": {
                    "name": "http_request",
                    "tool_call_id": "call_xyz789",
                    "output": "POST response data",
                },
            },
            # Final LLM response
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "content": "POST request completed successfully",
                        "tool_calls": [],
                        "invalid_tool_calls": [],
                        "tool_call_chunks": [],
                    }
                },
            },
        ]

        # Process events
        emitted_events = []
        for event in streaming_events:
            result = self.processor.process_event(event)
            if result is not None:
                emitted_events.append(result)

        # Verify we got the meaningful events
        assert len(emitted_events) == 3, (
            f"Expected 3 meaningful events, got {len(emitted_events)}"
        )

        # Check tool result
        tool_events = [e for e in emitted_events if e["event"] == "on_tool_end"]
        assert len(tool_events) == 1
        assert tool_events[0]["data"]["tool_call_id"] == "call_xyz789"

        # Check final content
        content_events = [
            e
            for e in emitted_events
            if e["event"] == "on_chat_model_stream" and e["data"]["chunk"]["content"]
        ]
        assert len(content_events) == 1
        assert "POST request completed" in content_events[0]["data"]["chunk"]["content"]

        # Should have complete tool call in the tool node's buffer
        tool_node_buffers = self.tool_node.get_buffered_tool_calls()
        assert "call_xyz789" in tool_node_buffers
        parsed_args = json.loads(tool_node_buffers["call_xyz789"])
        assert parsed_args == {
            "url": "https://api.example.com",
            "method": "POST",
            "data": {"key": "value"},
        }

    def test_non_streaming_invoke_behavior(self):
        """Test that non-streaming (invoke) requests with complete tool call dicts work immediately."""
        tool_call_id = "invoke_123"
        complete_args = {"url": "https://api.example.com/invoke", "method": "GET"}
        # Use AIMessage for the state
        ai_msg = AIMessage(
            content="call tool",
            tool_calls=[
                {"id": tool_call_id, "name": "http_request", "args": complete_args}
            ],
        )
        state = {"messages": [ai_msg]}
        result = self.tool_node.__call__(state)
        # The tool should have been executed immediately
        assert any(
            (
                hasattr(m, "name")
                and m.name == "http_request"
                and getattr(m, "tool_call_id", None) == tool_call_id
            )
            for m in result["messages"]
        )

    def test_tool_execution_after_accumulation(self):
        """Test that accumulated tool calls are properly executed."""
        # Simulate accumulating a complete tool call
        tool_call_id = "call_test123"
        complete_args = {
            "url": "https://api.example.com/test",
            "method": "GET",
            "headers": {"Content-Type": "application/json"},
        }

        # Accumulate the complete tool call
        self.tool_node.accumulate_chunk(
            {"id": tool_call_id, "args": json.dumps(complete_args)}
        )

        # Execute the tool
        result = self.tool_node._execute_tool(
            "http_request", complete_args, tool_call_id
        )

        # Verify execution
        assert result.content == "HTTP response data"
        assert result.name == "http_request"
        assert result.tool_call_id == tool_call_id

        # Verify tool was called with correct arguments
        self.mock_http_tool.invoke.assert_called_once_with(complete_args)

    def test_error_handling_incomplete_json(self):
        """Test handling of malformed JSON that never becomes complete."""
        # Simulate accumulating malformed JSON
        malformed_chunks = [
            {"id": "call_bad", "args": '{"url": "https://api.com"'},
            {"id": "call_bad", "args": ', "method": "GET"'},
            {
                "id": "call_bad",
                "args": ', "data": {"incomplete": true',
            },  # Missing closing brace
        ]

        # Process chunks
        for chunk in malformed_chunks:
            event = {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": {
                        "tool_call_chunks": [chunk],
                        "invalid_tool_calls": [{"id": chunk["id"], "error": "Invalid"}],
                    }
                },
            }

            self.processor.process_event(event)

        # Should still be accumulating (no complete tool calls)
        complete_calls = self.processor._check_for_complete_tool_calls()
        assert len(complete_calls) == 0

        # Should have accumulated the malformed JSON
        accumulated = self.processor.tool_call_buffers.get("call_bad", "")
        assert (
            accumulated
            == '{"url": "https://api.com", "method": "GET", "data": {"incomplete": true'
        )

        # Should not be valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(accumulated)


def test_seamless_model_compatibility():
    """
    Test that the solution works seamlessly with all models:
    - OpenAI: Accumulates chunks until valid JSON
    - Bedrock/Ollama: Works normally (no accumulation needed)
    - Non-streaming: Works with complete dict
    """
    # Create tool node and processor
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    mock_tool.invoke.return_value = "Success"

    tool_node = ChunkAccumulatingToolNode([mock_tool])
    processor = StreamingEventProcessor(tool_node)

    # Test OpenAI-style streaming (incomplete chunks)
    openai_chunks = [
        {"id": "call_openai", "args": '{"param": "value"'},
        {"id": "call_openai", "args": "}"},
    ]

    for chunk in openai_chunks:
        event = {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": {
                    "tool_call_chunks": [chunk],
                    "invalid_tool_calls": [{"id": chunk["id"], "error": "Invalid"}],
                }
            },
        }
        processor.process_event(event)

    # Should have complete tool call in the tool node's buffer
    tool_node_buffers = tool_node.get_buffered_tool_calls()
    assert "call_openai" in tool_node_buffers
    assert json.loads(tool_node_buffers["call_openai"]) == {"param": "value"}

    # Test Bedrock/Ollama-style (complete in one chunk)
    bedrock_event = {
        "event": "on_chat_model_stream",
        "data": {
            "chunk": {
                "tool_call_chunks": [
                    {"id": "call_bedrock", "args": '{"param": "value"}'}
                ],
                "invalid_tool_calls": [],
            }
        },
    }

    processor.process_event(bedrock_event)
    tool_node_buffers = tool_node.get_buffered_tool_calls()
    assert "call_bedrock" in tool_node_buffers
    assert json.loads(tool_node_buffers["call_bedrock"]) == {"param": "value"}

    # Test non-streaming (invoke) style
    tool_call_id = "invoke_456"
    complete_args = {"param": "value"}
    ai_msg = AIMessage(
        content="call tool",
        tool_calls=[{"id": tool_call_id, "name": "test_tool", "args": complete_args}],
    )
    state = {"messages": [ai_msg]}
    result = tool_node.__call__(state)
    assert any(
        (
            hasattr(m, "name")
            and m.name == "test_tool"
            and getattr(m, "tool_call_id", None) == tool_call_id
        )
        for m in result["messages"]
    )
