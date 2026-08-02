"""Minimal MCP server: JSON-RPC 2.0 over newline-delimited stdio.

Implements only the three methods the Tool Framework needs — initialize,
tools/list, tools/call — plus ping and the initialized notification, matching
the MCP protocol (2025-06-18).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from specflow import __version__
from specflow.mcp.adapter import McpToolCatalog, tool_call_from_request, tool_result_to_mcp
from specflow.mcp.exceptions import (
    McpError,
    McpInvalidParamsError,
    McpInvalidRequestError,
    McpMethodNotFoundError,
    McpNotInitializedError,
    McpParseError,
)
from specflow.tools.executor import ToolExecutor
from specflow.tools.registry import ToolRegistry

JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2025-06-18"


class McpServer:
    """Stateful MCP server exposing one ToolRegistry."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._executor = ToolExecutor(registry)
        self._catalog = McpToolCatalog(registry)
        self._initialized = False

    def handle_message(self, message: object) -> dict[str, Any] | None:
        """Handle one decoded JSON-RPC message.

        Returns the `result` payload for a response, or None for a notification.
        Protocol failures are raised as McpError; callers wrap the payload in
        the JSON-RPC envelope.
        """
        if not isinstance(message, dict) or message.get("jsonrpc") != JSONRPC_VERSION:
            raise McpInvalidRequestError("Message must be a JSON-RPC 2.0 object")
        method = message.get("method")
        request_id = message.get("id")
        if not isinstance(method, str):
            raise McpInvalidRequestError("JSON-RPC message must carry a string method")
        params = message.get("params")

        if method == "initialize":
            return self._handle_initialize(params)
        if request_id is None:
            if method == "notifications/initialized":
                self._initialized = True
            return None
        if not self._initialized:
            raise McpNotInitializedError("Server not initialized; call initialize first")
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self._catalog.as_dict()}
        if method == "tools/call":
            return self._handle_tools_call(request_id, params)
        raise McpMethodNotFoundError(f"Method not found: {method}")

    def _handle_initialize(self, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict) or not isinstance(params.get("protocolVersion"), str):
            raise McpInvalidParamsError("initialize params must include protocolVersion")
        return {
            "protocolVersion": params["protocolVersion"],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "specflow-agent", "version": __version__},
        }

    def _handle_tools_call(self, request_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            raise McpInvalidParamsError("tools/call params must include a string name")
        call = tool_call_from_request(
            call_id=str(request_id),
            tool_name=params["name"],
            arguments=params.get("arguments"),
        )
        return tool_result_to_mcp(self._executor.execute(call))


def error_response(request_id: Any, error: McpError) -> dict[str, Any]:
    """Build a JSON-RPC error response for a request id."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": error.code, "message": error.message},
    }


def run_stdio(registry: ToolRegistry) -> None:
    """Serve the registry over stdin/stdout until EOF."""
    server = McpServer(registry)
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = error_response(None, McpParseError(str(exc)))
        else:
            try:
                payload = server.handle_message(message)
            except McpError as exc:
                response = error_response(
                    message.get("id") if isinstance(message, dict) else None,
                    exc,
                )
            else:
                if payload is None:
                    continue
                response = {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": message.get("id") if isinstance(message, dict) else None,
                    "result": payload,
                }
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
