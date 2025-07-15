from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class DummyArgs(BaseModel):
    foo: str = Field(..., description="A foo string")
    bar: int = Field(..., description="A bar integer")


class DummyTool(BaseTool):
    name: str = "dummy_tool"
    description: str = "A dummy tool for testing."
    args_schema: type[DummyArgs] = DummyArgs

    def _run(self, foo: str, bar: int) -> str:
        return f"foo={foo}, bar={bar}"


def test_basetool_schema_generation():
    """Test that BaseTool with args_schema generates proper schema."""
    tool = DummyTool()

    # Check that the tool has the expected schema
    assert tool.args_schema == DummyArgs
    assert tool.name == "dummy_tool"

    # Check the schema structure
    schema = tool.args_schema.model_json_schema()
    assert "foo" in schema["properties"]
    assert "bar" in schema["properties"]
    assert schema["properties"]["foo"]["type"] == "string"
    assert schema["properties"]["bar"]["type"] == "integer"

    print("Tool schema:", schema)
    print("Tool args_schema:", tool.args_schema)
    print("Tool name:", tool.name)
    print("Tool description:", tool.description)


def test_basetool_vs_structured_tool():
    """Compare BaseTool with StructuredTool approach."""
    from langchain_core.tools import StructuredTool

    # BaseTool approach (current implementation)
    basetool = DummyTool()

    # StructuredTool approach (recommended for OpenAI)
    def dummy_function(foo: str, bar: int) -> str:
        return f"foo={foo}, bar={bar}"

    structured_tool = StructuredTool.from_function(
        func=dummy_function, name="dummy_tool", description="A dummy tool for testing."
    )

    print("\n=== BaseTool ===")
    print("Args schema:", basetool.args_schema)
    print(
        "Schema:",
        basetool.args_schema.model_json_schema() if basetool.args_schema else "None",
    )

    print("\n=== StructuredTool ===")
    print("Args schema:", getattr(structured_tool, "args_schema", "None"))
    print(
        "Schema:",
        structured_tool.args_schema.model_json_schema()
        if hasattr(structured_tool, "args_schema")
        else "None",
    )

    # The key difference: StructuredTool generates proper OpenAI function calling schemas
    # while BaseTool with args_schema may not work correctly with OpenAI models
