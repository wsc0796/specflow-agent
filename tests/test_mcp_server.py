import io
import json
import sys

import pytest

from specflow.mcp.exceptions import (
    McpInvalidParamsError,
    McpInvalidRequestError,
    McpMethodNotFoundError,
    McpNotInitializedError,
)
from specflow.mcp.server import McpServer, run_stdio
from specflow.tools import (
    ToolCall,
    ToolMetadata,
    ToolRegistry,
    ToolResult,
)

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


_INITIALIZE_REQUEST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18"},
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


@pytest.fixture
def server(registry) -> McpServer:
    return McpServer(registry)


class TestHandshake:
    def test_initialize_echoes_protocol_version(self, server) -> None:
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        )
        assert response["protocolVersion"] == "2025-06-18"
        assert response["capabilities"] == {"tools": {"listChanged": False}}
        assert response["serverInfo"]["name"] == "specflow-agent"

    def test_initialize_requires_protocol_version(self, server) -> None:
        with pytest.raises(McpInvalidParamsError):
            server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    def test_methods_rejected_before_initialized(self, server) -> None:
        with pytest.raises(McpNotInitializedError):
            server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    def test_initialized_notification_unlocks_server(self, server) -> None:
        server.handle_message(_INITIALIZE_REQUEST)
        notification = server.handle_message(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        assert notification is None
        response = server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert len(response["tools"]) == 2


class TestToolsList:
    def test_lists_defined_tools(self, server) -> None:
        server.handle_message(_INITIALIZE_REQUEST)
        server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        response = server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert [tool["name"] for tool in response["tools"]] == ["fake_echo", "fake_failure"]
        assert response["tools"][0]["inputSchema"] == FAKE_SCHEMAS["fake_echo"]


class TestToolsCall:
    def test_successful_call(self, server) -> None:
        _initialize(server)
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "fake_echo", "arguments": {"message": "hi"}},
            }
        )
        assert response["isError"] is False
        assert json.loads(response["content"][0]["text"]) == {"echo": {"message": "hi"}}

    def test_failed_call_returns_is_error(self, server) -> None:
        _initialize(server)
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "fake_failure", "arguments": {}},
            }
        )
        assert response["isError"] is True
        assert response["content"][0]["text"] == "simulated failure"

    def test_unknown_tool_is_error_not_exception(self, server) -> None:
        _initialize(server)
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "missing_tool", "arguments": {}},
            }
        )
        assert response["isError"] is True

    def test_call_requires_name(self, server) -> None:
        _initialize(server)
        with pytest.raises(McpInvalidParamsError):
            server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {}})

    def test_call_rejects_invalid_tool_name(self, server) -> None:
        _initialize(server)
        with pytest.raises(McpInvalidParamsError):
            server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "Bad Name", "arguments": {}},
                }
            )


class TestProtocolErrors:
    def test_unknown_method(self, server) -> None:
        _initialize(server)
        with pytest.raises(McpMethodNotFoundError):
            server.handle_message(
                {"jsonrpc": "2.0", "id": 4, "method": "tools/unknown", "params": {}}
            )

    def test_ping_returns_empty_result(self, server) -> None:
        _initialize(server)
        assert server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "ping"}) == {}

    def test_wrong_jsonrpc_version(self, server) -> None:
        with pytest.raises(McpInvalidRequestError):
            server.handle_message({"jsonrpc": "1.0", "id": 4, "method": "ping"})

    def test_non_dict_message(self, server) -> None:
        with pytest.raises(McpInvalidRequestError):
            server.handle_message(["not", "an", "object"])

    def test_unknown_notification_ignored(self, server) -> None:
        assert (
            server.handle_message({"jsonrpc": "2.0", "method": "notifications/cancelled"}) is None
        )


class TestRunStdio:
    def test_full_roundtrip(self, registry, monkeypatch) -> None:
        script = "\n".join(
            [
                '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}',
                '{"jsonrpc":"2.0","method":"notifications/initialized"}',
                '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
                '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fake_echo","arguments":{"message":"hi"}}}',
                "not json",
            ]
        )
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(script))
        monkeypatch.setattr(sys, "stdout", out)
        run_stdio(registry)
        responses = [json.loads(line) for line in out.getvalue().strip().splitlines()]
        assert len(responses) == 4
        assert responses[0]["result"]["protocolVersion"] == "2025-06-18"
        assert [tool["name"] for tool in responses[1]["result"]["tools"]] == [
            "fake_echo",
            "fake_failure",
        ]
        assert responses[2]["result"]["isError"] is False
        assert json.loads(responses[2]["result"]["content"][0]["text"]) == {
            "echo": {"message": "hi"}
        }
        assert responses[3]["error"]["code"] == -32700


def _initialize(server: McpServer) -> None:
    server.handle_message(_INITIALIZE_REQUEST)
    server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
