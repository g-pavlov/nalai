"""
Experiment to test different tool definition approaches and their streaming behavior.

Based on: https://python.langchain.com/docs/how_to/tool_streaming/
"""

import json

from langchain_core.tools import BaseTool, StructuredTool, tool
from pydantic import BaseModel, Field


# Test 1: @tool decorator (recommended approach)
@tool
def add_tool_decorator(a: int, b: int) -> int:
    """Adds a and b."""
    return a + b


@tool
def multiply_tool_decorator(a: int, b: int) -> int:
    """Multiplies a and b."""
    return a * b


# Test 2: StructuredTool.from_function
def add_function(a: int, b: int) -> int:
    """Adds a and b."""
    return a + b


def multiply_function(a: int, b: int) -> int:
    """Multiplies a and b."""
    return a * b


add_structured_tool = StructuredTool.from_function(
    func=add_function, name="add_structured", description="Adds a and b."
)

multiply_structured_tool = StructuredTool.from_function(
    func=multiply_function,
    name="multiply_structured",
    description="Multiplies a and b.",
)


# Test 3: BaseTool subclass (our current approach)
class AddArgs(BaseModel):
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")


class AddBaseTool(BaseTool):
    name: str = "add_base"
    description: str = "Adds a and b."
    args_schema: type[AddArgs] = AddArgs

    def _run(self, a: int, b: int) -> int:
        return a + b


class MultiplyArgs(BaseModel):
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")


class MultiplyBaseTool(BaseTool):
    name: str = "multiply_base"
    description: str = "Multiplies a and b."
    args_schema: type[MultiplyArgs] = MultiplyArgs

    def _run(self, a: int, b: int) -> int:
        return a * b


# Test 4: BaseTool without args_schema
class AddBaseToolNoSchema(BaseTool):
    name: str = "add_base_no_schema"
    description: str = "Adds a and b."

    def _run(self, a: int, b: int) -> int:
        return a + b


class MultiplyBaseToolNoSchema(BaseTool):
    name: str = "multiply_base_no_schema"
    description: str = "Multiplies a and b."

    def _run(self, a: int, b: int) -> int:
        return a * b


def test_tool_schema_generation():
    """Test that different tool approaches generate proper schemas."""

    # Test @tool decorator
    print("\n=== @tool decorator ===")
    print(f"Name: {add_tool_decorator.name}")
    print(f"Description: {add_tool_decorator.description}")
    print(f"Args schema: {add_tool_decorator.args_schema}")

    # Test StructuredTool
    print("\n=== StructuredTool ===")
    print(f"Name: {add_structured_tool.name}")
    print(f"Description: {add_structured_tool.description}")
    print(f"Args schema: {add_structured_tool.args_schema}")

    # Test BaseTool with args_schema
    print("\n=== BaseTool with args_schema ===")
    add_base = AddBaseTool()
    print(f"Name: {add_base.name}")
    print(f"Description: {add_base.description}")
    print(f"Args schema: {add_base.args_schema}")

    # Test BaseTool without args_schema
    print("\n=== BaseTool without args_schema ===")
    add_base_no_schema = AddBaseToolNoSchema()
    print(f"Name: {add_base_no_schema.name}")
    print(f"Description: {add_base_no_schema.description}")
    print(f"Args schema: {add_base_no_schema.args_schema}")


def simulate_openai_streaming_response():
    """
    Simulate OpenAI's streaming tool call response based on the documentation.
    This shows what we're actually seeing in our system.
    """
    print("\n=== Simulating OpenAI Streaming Tool Calls ===")

    # This is what OpenAI actually streams (piece by piece)
    streaming_chunks = [
        # Initial tool call start
        {"name": "get_http_requests", "args": "", "id": "call_123", "index": 0},
        # Building JSON arguments piece by piece
        {"name": None, "args": '{"', "id": None, "index": 0},
        {"name": None, "args": "url", "id": None, "index": 0},
        {"name": None, "args": '":"', "id": None, "index": 0},
        {"name": None, "args": "http", "id": None, "index": 0},
        {"name": None, "args": "://", "id": None, "index": 0},
        {"name": None, "args": "localhost", "id": None, "index": 0},
        {"name": None, "args": ":", "id": None, "index": 0},
        {"name": None, "args": "800", "id": None, "index": 0},
        {"name": None, "args": "1", "id": None, "index": 0},
        {"name": None, "args": '"}', "id": None, "index": 0},
    ]

    print("OpenAI streams tool calls like this:")
    for i, chunk in enumerate(streaming_chunks):
        print(f"Chunk {i}: {chunk}")

    print("\nThis creates 'invalid_tool_calls' because each piece is incomplete JSON")


def test_tool_accumulation():
    """
    Test how different tool approaches handle accumulating streaming chunks.
    Based on the LangChain documentation pattern.
    """
    print("\n=== Testing Tool Call Accumulation ===")

    # Simulate the streaming chunks from the documentation
    chunks = [
        [],  # Empty initial
        [{"name": "Multiply", "args": "", "id": "call_1", "index": 0}],
        [{"name": None, "args": '{"a"', "id": None, "index": 0}],
        [{"name": None, "args": ": 3, ", "id": None, "index": 0}],
        [{"name": None, "args": '"b": 1', "id": None, "index": 0}],
        [{"name": None, "args": "2}", "id": None, "index": 0}],
    ]

    print("Accumulating tool_call_chunks (raw string):")
    accumulated_chunks = []
    for i, chunk in enumerate(chunks):
        if chunk:
            accumulated_chunks.extend(chunk)
        print(f"Step {i}: {accumulated_chunks}")

    print("\nAccumulating tool_calls (parsed dict):")
    # This is what LangChain does internally - it tries to parse the accumulated string
    accumulated_string = ""
    for chunk in chunks:
        if chunk and chunk[0].get("args"):
            accumulated_string += chunk[0]["args"]

    print(f"Final accumulated string: {accumulated_string}")

    # Try to parse it
    try:
        parsed = json.loads(accumulated_string)
        print(f"Successfully parsed: {parsed}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse: {e}")
        print("This is why we get 'invalid_tool_calls'")


def test_tool_compatibility():
    """
    Test which tool approaches are most compatible with streaming.
    """
    print("\n=== Tool Compatibility Analysis ===")

    toolsets = {
        "@tool decorator": [add_tool_decorator, multiply_tool_decorator],
        "StructuredTool": [add_structured_tool, multiply_structured_tool],
        "BaseTool with args_schema": [AddBaseTool(), MultiplyBaseTool()],
        "BaseTool without args_schema": [
            AddBaseToolNoSchema(),
            MultiplyBaseToolNoSchema(),
        ],
    }

    for approach, tools in toolsets.items():
        print(f"\n{approach}:")
        for tool_obj in tools:
            print(f"  - {tool_obj.name}: schema={tool_obj.args_schema is not None}")

    print("\nRecommendation based on LangChain docs:")
    print("✅ @tool decorator - Best for streaming")
    print("✅ StructuredTool - Good for streaming")
    print("⚠️  BaseTool with args_schema - May have streaming issues")
    print("❌ BaseTool without args_schema - Poor streaming support")


def test_actual_streaming_simulation():
    """
    Simulate the actual streaming behavior we're seeing with OpenAI models.
    This tests how different tool approaches handle the piece-by-piece streaming.
    """
    print("\n=== Actual Streaming Simulation ===")

    # Simulate the exact streaming chunks we're seeing in our system
    streaming_events = [
        # Initial tool call
        {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "get_http_requests",
                            "args": {},
                            "id": "call_123",
                            "type": "tool_call",
                        }
                    ],
                    "invalid_tool_calls": [],
                    "tool_call_chunks": [
                        {
                            "name": "get_http_requests",
                            "args": "",
                            "id": "call_123",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                }
            },
        },
        # Piece by piece JSON building
        {
            "event": "on_chat_model_stream",
            "data": {
                "chunk": {
                    "content": "",
                    "tool_calls": [],
                    "invalid_tool_calls": [
                        {
                            "name": None,
                            "args": '{"',
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": '{"',
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
                            "args": "url",
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": "url",
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
                            "args": '":"',
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": '":"',
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
                            "args": "http",
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": "http",
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
                            "args": "://",
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": "://",
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
                            "args": "localhost",
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": "localhost",
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
                            "args": ":",
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": ":",
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
                            "args": "800",
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": "800",
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
                            "args": "1",
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": "1",
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
                            "args": '"}',
                            "id": None,
                            "error": None,
                            "type": "invalid_tool_call",
                        }
                    ],
                    "tool_call_chunks": [
                        {
                            "name": None,
                            "args": '"}',
                            "id": None,
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                }
            },
        },
    ]

    print("Simulating the exact streaming events we're seeing:")
    total_invalid_calls = 0
    accumulated_args = ""

    for i, event in enumerate(streaming_events):
        chunk = event["data"]["chunk"]
        invalid_calls = chunk.get("invalid_tool_calls", [])
        tool_call_chunks = chunk.get("tool_call_chunks", [])

        print(f"\nEvent {i}:")
        print(f"  Invalid tool calls: {len(invalid_calls)}")
        print(f"  Tool call chunks: {len(tool_call_chunks)}")

        if invalid_calls:
            total_invalid_calls += len(invalid_calls)
            print(
                f"  Invalid call args: {[call.get('args', '') for call in invalid_calls]}"
            )

        if tool_call_chunks:
            for tcc in tool_call_chunks:
                if tcc.get("args"):
                    accumulated_args += tcc["args"]

    print("\nSummary:")
    print(f"  Total invalid tool calls: {total_invalid_calls}")
    print(f"  Final accumulated args: {accumulated_args}")

    # Try to parse the final accumulated string
    try:
        parsed = json.loads(accumulated_args)
        print(f"  Successfully parsed: {parsed}")
    except json.JSONDecodeError as e:
        print(f"  Failed to parse: {e}")

    print("\nThis is exactly what we're seeing in our system!")
    print("The issue is that OpenAI streams tool calls piece by piece,")
    print("and each piece becomes an 'invalid_tool_call' until the JSON is complete.")


def test_tool_definition_comparison():
    """
    Compare how different tool definition approaches handle the streaming issue.
    """
    print("\n=== Tool Definition Comparison ===")

    # Test our current approach vs recommended approaches
    current_tools = [AddBaseTool(), MultiplyBaseTool()]
    recommended_tools = [add_tool_decorator, multiply_tool_decorator]
    structured_tools = [add_structured_tool, multiply_structured_tool]

    print("Current approach (BaseTool with args_schema):")
    for tool_obj in current_tools:
        print(f"  - {tool_obj.name}: {type(tool_obj).__name__}")
        print(f"    Schema: {tool_obj.args_schema}")
        print(f"    Schema type: {type(tool_obj.args_schema).__name__}")

    print("\nRecommended approach (@tool decorator):")
    for tool_obj in recommended_tools:
        print(f"  - {tool_obj.name}: {type(tool_obj).__name__}")
        print(f"    Schema: {tool_obj.args_schema}")
        print(f"    Schema type: {type(tool_obj.args_schema).__name__}")

    print("\nStructuredTool approach:")
    for tool_obj in structured_tools:
        print(f"  - {tool_obj.name}: {type(tool_obj).__name__}")
        print(f"    Schema: {tool_obj.args_schema}")
        print(f"    Schema type: {type(tool_obj.args_schema).__name__}")

    print("\nKey insight:")
    print("All approaches generate schemas, but the schema types are different.")
    print("The @tool decorator and StructuredTool generate LangChain-specific schemas")
    print("while BaseTool uses our custom Pydantic models.")
    print("This difference may affect how LangChain handles streaming tool calls.")


if __name__ == "__main__":
    test_tool_schema_generation()
    simulate_openai_streaming_response()
    test_tool_accumulation()
    test_tool_compatibility()
    test_actual_streaming_simulation()
    test_tool_definition_comparison()
