"""Adapter between the Tool Framework and the MCP protocol.

The Tool layer owns each tool's input JSON Schema (``Tool.input_schema``);
this adapter only reads it, so `tools/list` can never drift from the real
validation.  Requests are mapped onto the existing ``ToolCall``/``ToolResult``
contract, so no Tool logic is re-implemented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from specflow.mcp.exceptions import McpInvalidParamsError, McpSchemaMissingError
from specflow.tools.exceptions import ToolValidationError
from specflow.tools.models import ToolCall, ToolResult, ToolStatus
from specflow.tools.registry import ToolRegistry


@dataclass(frozen=True)
class McpToolDefinition:
    """One MCP tool definition: stable metadata plus a JSON Schema."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise McpSchemaMissingError("MCP tool name must be a non-empty string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise McpSchemaMissingError(f"MCP tool description missing: {self.name}")
        if not isinstance(self.input_schema, dict) or self.input_schema.get("type") != "object":
            raise McpSchemaMissingError(
                f"MCP tool inputSchema must be an object schema: {self.name}"
            )
        if not isinstance(self.input_schema.get("properties"), dict):
            raise McpSchemaMissingError(f"MCP tool inputSchema.properties missing: {self.name}")
        if self.input_schema.get("additionalProperties") is not False:
            raise McpSchemaMissingError(
                f"MCP tool inputSchema must set additionalProperties=False: {self.name}"
            )

    def as_dict(self) -> dict[str, Any]:
        """Return the MCP `tools/list` entry for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class McpToolCatalog:
    """Stable catalog of MCP tool definitions for one ToolRegistry.

    All schemas are validated at construction time so `tools/list` can never
    fail halfway through a session.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        definitions: list[McpToolDefinition] = []
        for metadata in registry.metadata():
            try:
                schema = registry.input_schema(metadata.name)
            except Exception as exc:
                raise McpSchemaMissingError(
                    f"Tool has no single-source input schema: {metadata.name}"
                ) from exc
            definitions.append(
                McpToolDefinition(
                    name=metadata.name,
                    description=metadata.description,
                    input_schema=schema,
                )
            )
        self._definitions = tuple(definitions)
        self._names = frozenset(definition.name for definition in definitions)

    def as_dict(self) -> list[dict[str, Any]]:
        """Return the MCP `tools/list` result entries in stable name order."""
        return [definition.as_dict() for definition in self._definitions]

    def has(self, name: str) -> bool:
        """Return whether a Tool is exposed over MCP."""
        return name in self._names

    def __len__(self) -> int:
        return len(self._definitions)


def tool_call_from_request(
    *,
    call_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None,
) -> ToolCall:
    """Build a ToolCall from an MCP `tools/call` request, reusing Tool validation."""
    if arguments is not None and not isinstance(arguments, dict):
        raise McpInvalidParamsError("tools/call arguments must be an object")
    try:
        return ToolCall.build(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments or {},
        )
    except ToolValidationError as exc:
        raise McpInvalidParamsError(str(exc)) from exc


def tool_result_to_mcp(result: ToolResult) -> dict[str, Any]:
    """Serialize a ToolResult into an MCP `tools/call` result body."""
    if result.status == ToolStatus.FAILED:
        return {
            "content": [
                {
                    "type": "text",
                    "text": result.error_message or result.error_type or "Tool execution failed",
                }
            ],
            "structuredContent": {
                "error_type": result.error_type or "TOOL_EXECUTION_FAILED",
                "requires_review": result.requires_review,
            },
            "isError": True,
        }
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    dict(result.output),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        ],
        "isError": False,
    }
