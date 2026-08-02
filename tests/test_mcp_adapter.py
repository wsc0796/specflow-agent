import json

import pytest

from specflow.mcp.adapter import (
    McpToolCatalog,
    McpToolDefinition,
    tool_call_from_request,
    tool_result_to_mcp,
)
from specflow.mcp.exceptions import McpInvalidParamsError, McpSchemaMissingError
from specflow.tools import ToolCall, ToolMetadata, ToolRegistry, ToolResult
from specflow.tools.repository_tools import RepositoryToolSet

FAKE_SCHEMAS = {
    "fake_echo": {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "additionalProperties": False,
    },
    "fake_failure": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


class FakeEchoTool:
    input_schema: dict = FAKE_SCHEMAS["fake_echo"]

    def __init__(self, name: str = "fake_echo") -> None:
        self._metadata = ToolMetadata(
            name=name,
            version="1.0.0",
            description="Echo structured test arguments.",
            input_model="FakeEchoInput",
            output_model="FakeEchoOutput",
            deterministic=True,
            read_only=True,
        )

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult.success(
            call_id=call.call_id,
            tool_name=call.tool_name,
            output={"echo": dict(call.arguments)},
        )


class FakeFailureTool(FakeEchoTool):
    input_schema: dict = FAKE_SCHEMAS["fake_failure"]

    def __init__(self) -> None:
        super().__init__("fake_failure")

    def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult.failed(
            call_id=call.call_id,
            tool_name=call.tool_name,
            error_type="RuntimeError",
            error_message="simulated failure",
        )


@pytest.fixture
def registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    registry.register(FakeFailureTool())
    return registry


class FakeNoSchemaTool(FakeEchoTool):
    input_schema = None

    def __init__(self) -> None:
        super().__init__("fake_no_schema")


class TestMcpToolDefinition:
    def test_rejects_non_object_schema(self) -> None:
        with pytest.raises(McpSchemaMissingError):
            McpToolDefinition(name="t", description="d", input_schema={"type": "array"})

    def test_rejects_missing_properties(self) -> None:
        with pytest.raises(McpSchemaMissingError):
            McpToolDefinition(
                name="t",
                description="d",
                input_schema={"type": "object", "additionalProperties": False},
            )

    def test_rejects_unknown_arguments_allowed(self) -> None:
        with pytest.raises(McpSchemaMissingError):
            McpToolDefinition(
                name="t",
                description="d",
                input_schema={"type": "object", "properties": {}},
            )

    def test_as_dict_shape(self) -> None:
        definition = McpToolDefinition(
            name="fake_echo",
            description="Echo structured test arguments.",
            input_schema=FAKE_SCHEMAS["fake_echo"],
        )
        assert definition.as_dict() == {
            "name": "fake_echo",
            "description": "Echo structured test arguments.",
            "inputSchema": FAKE_SCHEMAS["fake_echo"],
        }


class TestMcpToolCatalog:
    def test_definitions_in_stable_name_order(self, registry) -> None:
        catalog = McpToolCatalog(registry)
        assert [entry["name"] for entry in catalog.as_dict()] == ["fake_echo", "fake_failure"]

    def test_missing_schema_raises_at_construction(self) -> None:
        registry = ToolRegistry()
        registry.register(FakeNoSchemaTool())
        with pytest.raises(McpSchemaMissingError, match="fake_no_schema"):
            McpToolCatalog(registry)

    def test_has(self, registry) -> None:
        catalog = McpToolCatalog(registry)
        assert catalog.has("fake_echo")
        assert not catalog.has("missing")

    def test_len(self, registry) -> None:
        assert len(McpToolCatalog(registry)) == 2

    def test_catalog_schema_is_the_tool_owned_schema(self, registry) -> None:
        """Single source: tools/list must return exactly the Tool-owned schema."""
        catalog = McpToolCatalog(registry)
        by_name = {entry["name"]: entry["inputSchema"] for entry in catalog.as_dict()}
        assert by_name["fake_echo"] == FakeEchoTool.input_schema
        assert by_name["fake_failure"] == FakeFailureTool.input_schema


class TestToolCallFromRequest:
    def test_builds_valid_call(self) -> None:
        call = tool_call_from_request(call_id="7", tool_name="fake_echo", arguments={"a": 1})
        assert call.call_id == "7"
        assert call.tool_name == "fake_echo"
        assert dict(call.arguments) == {"a": 1}

    def test_defaults_arguments_to_empty(self) -> None:
        call = tool_call_from_request(call_id="7", tool_name="fake_echo", arguments=None)
        assert dict(call.arguments) == {}

    def test_rejects_invalid_tool_name(self) -> None:
        with pytest.raises(McpInvalidParamsError):
            tool_call_from_request(call_id="7", tool_name="Bad Name", arguments=None)

    def test_rejects_non_object_arguments(self) -> None:
        with pytest.raises(McpInvalidParamsError):
            tool_call_from_request(call_id="7", tool_name="fake_echo", arguments=["x"])


class TestToolResultToMcp:
    def test_success_result(self) -> None:
        result = ToolResult.success(
            call_id="7",
            tool_name="fake_echo",
            output={"echo": {"a": 1}},
        )
        body = tool_result_to_mcp(result)
        assert body["isError"] is False
        assert json.loads(body["content"][0]["text"]) == {"echo": {"a": 1}}

    def test_failed_result(self) -> None:
        result = ToolResult.failed(
            call_id="7",
            tool_name="fake_echo",
            error_type="RuntimeError",
            error_message="boom",
        )
        body = tool_result_to_mcp(result)
        assert body["isError"] is True
        assert body["content"][0]["text"] == "boom"


class TestRealToolSchemas:
    def test_repository_tool_set_schemas_registered(self, tmp_path) -> None:
        """Every Tool exposed by the real RepositoryToolSet owns an inputSchema."""
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        tool_set = RepositoryToolSet(tmp_path)
        names = {tool.metadata.name for tool in tool_set.tools}
        assert names == {"list_files", "read_file", "search_code"}
        for tool in tool_set.tools:
            assert isinstance(tool.input_schema, dict)
            assert tool.input_schema.get("type") == "object"
            assert tool.input_schema.get("additionalProperties") is False

    def test_real_catalog_schemas_match_tool_owned_schemas(self, tmp_path) -> None:
        """The MCP catalog must mirror the Tool layer with zero hand-written copies."""
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        registry = ToolRegistry()
        RepositoryToolSet(tmp_path).register_into(registry)
        catalog = McpToolCatalog(registry)
        by_name = {entry["name"]: entry["inputSchema"] for entry in catalog.as_dict()}
        for metadata in registry.metadata():
            assert by_name[metadata.name] == registry.input_schema(metadata.name)
