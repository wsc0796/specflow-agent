"""Adapter between the Tool Framework and the MCP protocol.

The MCP `tools/list` response requires a JSON Schema per tool, but the Tool
Framework carries only an `input_model` *name* (e.g. "ListFilesInput"), not a
schema.  This adapter supplies the missing schemas and maps MCP requests onto
the existing `ToolCall`/`ToolResult` contract so no Tool logic is re-implemented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from specflow.mcp.exceptions import McpInvalidParamsError, McpSchemaMissingError
from specflow.tools.exceptions import ToolValidationError
from specflow.tools.models import ToolCall, ToolResult, ToolStatus
from specflow.tools.registry import ToolRegistry

# JSON Schema per Tool, keyed by stable Tool name. Constraints mirror the real
# validations in tools/repository_tools.py and tools/repository_policy.py:
#   - list_files: include/exclude are optional string arrays; max_results is an
#     integer in [1, 1000] (RepositoryPolicyLimits.max_list_results).
#   - search_code: query is REQUIRED and capped at 256 chars (repository_tools.py
#     enforces len(query) > 256 -> RepositoryLimitError); include/exclude are
#     optional string arrays; case_sensitive is an optional boolean.
#   - read_file: path is REQUIRED.
# additionalProperties MUST be False for every tool: the Tool layer rejects
# unknown arguments (`_reject_unknown_arguments`), so the schema must say so too.
_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_files": {
        "type": "object",
        "properties": {
            "include": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional glob patterns; only matching allowed files are listed.",
            },
            "exclude": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional glob patterns to exclude from the listing.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1_000,
                "description": (
                    "Maximum number of files to list; defaults to the policy limit (1000)."
                ),
            },
        },
        "additionalProperties": False,
    },
    "search_code": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "description": "Literal search query; required and capped at 256 characters.",
            },
            "include": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional glob patterns; only matching allowed files are searched.",
            },
            "exclude": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional glob patterns to exclude from the search.",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether matching is case-sensitive; defaults to False.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "read_file": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "minLength": 1,
                "description": "Repository-relative path of the file to read.",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}


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
                schema = _INPUT_SCHEMAS[metadata.name]
            except KeyError as exc:
                raise McpSchemaMissingError(
                    f"No MCP inputSchema registered for tool: {metadata.name}"
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
