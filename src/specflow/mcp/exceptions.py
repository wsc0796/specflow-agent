"""MCP server exceptions, each carrying a JSON-RPC error code."""

from __future__ import annotations


class McpError(Exception):
    """Base MCP error with a JSON-RPC error code."""

    code = -32603  # Internal error

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class McpParseError(McpError):
    """Incoming message could not be parsed as JSON."""

    code = -32700


class McpInvalidRequestError(McpError):
    """Incoming message is not a valid JSON-RPC request."""

    code = -32600


class McpMethodNotFoundError(McpError):
    """Requested JSON-RPC method does not exist."""

    code = -32601


class McpInvalidParamsError(McpError):
    """Method arguments failed validation."""

    code = -32602


class McpNotInitializedError(McpError):
    """Request received before the client completed initialization."""

    code = -32002


class McpSchemaMissingError(McpError):
    """A registered Tool has no MCP inputSchema; server configuration error."""

    code = -32603
