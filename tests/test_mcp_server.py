import io
import json
import os
import subprocess
import sys
from pathlib import Path

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

    def test_unsupported_protocol_negotiates_server_version(self, server) -> None:
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "unsupported-version"},
            }
        )
        assert response["protocolVersion"] == "2025-06-18"

    def test_initialized_notification_cannot_bypass_initialize(self, server) -> None:
        with pytest.raises(McpNotInitializedError):
            server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        with pytest.raises(McpNotInitializedError):
            server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    def test_initialize_cannot_be_repeated(self, server) -> None:
        server.handle_message(_INITIALIZE_REQUEST)
        with pytest.raises(McpInvalidRequestError):
            server.handle_message(_INITIALIZE_REQUEST)

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
        assert response["structuredContent"]["error_type"] == "RuntimeError"

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

    def test_stdio_subprocess_smoke(self, tmp_path) -> None:
        """Real-process stdio smoke: initialize -> list -> call -> unknown tool."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "a.txt").write_text("hello from smoke", encoding="utf-8")
        (repo / ".env").write_text("API_KEY=SUBPROCESS_SECRET_MARKER", encoding="utf-8")
        (tmp_path / "outside.txt").write_text("outside repository", encoding="utf-8")
        script_dir = Path(sys.executable).parent
        executable = script_dir / ("specflow.exe" if os.name == "nt" else "specflow")
        assert executable.exists(), f"CLI entry point not found: {executable}"
        process = subprocess.Popen(
            [str(executable), "mcp", "--root", str(repo)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            script = "\n".join(
                [
                    '{"jsonrpc":"2.0","id":1,"method":"initialize",'
                    '"params":{"protocolVersion":"2025-06-18"}}',
                    '{"jsonrpc":"2.0","method":"notifications/initialized"}',
                    '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
                    (
                        '{"jsonrpc":"2.0","id":3,"method":"tools/call",'
                        '"params":{"name":"read_file","arguments":{"path":"a.txt"}}}'
                    ),
                    (
                        '{"jsonrpc":"2.0","id":4,"method":"tools/call",'
                        '"params":{"name":"unknown_tool","arguments":{}}}'
                    ),
                    (
                        '{"jsonrpc":"2.0","id":5,"method":"tools/call",'
                        '"params":{"name":"read_file","arguments":{"path":123}}}'
                    ),
                    (
                        '{"jsonrpc":"2.0","id":6,"method":"tools/call",'
                        '"params":{"name":"read_file","arguments":{"path":"../outside.txt"}}}'
                    ),
                    (
                        '{"jsonrpc":"2.0","id":7,"method":"tools/call",'
                        '"params":{"name":"read_file","arguments":{"path":".env"}}}'
                    ),
                ]
            )
            output, stderr = process.communicate(script + "\n", timeout=60)
        finally:
            if process.poll() is None:
                process.kill()
        responses = [json.loads(line) for line in output.strip().splitlines()]
        assert responses[0]["result"]["protocolVersion"] == "2025-06-18"
        tool_names = [tool["name"] for tool in responses[1]["result"]["tools"]]
        assert tool_names == ["list_files", "read_file", "search_code"]
        assert responses[2]["result"]["isError"] is False
        assert "hello from smoke" in responses[2]["result"]["content"][0]["text"]
        assert responses[3]["result"]["isError"] is True
        assert responses[3]["result"]["structuredContent"]["error_type"]
        assert responses[4]["result"]["isError"] is True
        assert responses[4]["result"]["structuredContent"]["error_type"]
        assert responses[5]["result"]["isError"] is True
        assert responses[5]["result"]["structuredContent"]["error_type"]
        assert responses[6]["result"]["isError"] is True
        assert responses[6]["result"]["structuredContent"]["error_type"]
        assert "SUBPROCESS_SECRET_MARKER" not in output
        assert process.returncode == 0
        assert stderr == ""


def _initialize(server: McpServer) -> None:
    server.handle_message(_INITIALIZE_REQUEST)
    server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
