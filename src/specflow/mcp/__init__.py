"""Minimal MCP server exposing the Tool Framework over JSON-RPC."""

from specflow.mcp.adapter import McpToolCatalog, McpToolDefinition, tool_call_from_request
from specflow.mcp.exceptions import (
    McpError,
    McpInvalidParamsError,
    McpInvalidRequestError,
    McpMethodNotFoundError,
    McpNotInitializedError,
    McpParseError,
    McpSchemaMissingError,
)
from specflow.mcp.server import McpServer, run_stdio

__all__ = [
    "McpError",
    "McpInvalidParamsError",
    "McpInvalidRequestError",
    "McpMethodNotFoundError",
    "McpNotInitializedError",
    "McpParseError",
    "McpSchemaMissingError",
    "McpServer",
    "McpToolCatalog",
    "McpToolDefinition",
    "run_stdio",
    "tool_call_from_request",
]
