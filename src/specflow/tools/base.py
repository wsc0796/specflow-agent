"""Tool Framework base protocol."""

from __future__ import annotations

from typing import Any, Protocol

from specflow.tools.models import ToolCall, ToolMetadata, ToolResult


class Tool(Protocol):
    """Protocol implemented by tools."""

    @property
    def metadata(self) -> ToolMetadata:
        """Return stable tool metadata."""
        ...

    @property
    def input_schema(self) -> dict[str, Any]:
        """Return the tool-owned input JSON Schema (single source of truth).

        MCP ``tools/list`` and any other protocol adapter must read the schema
        from here; they must never maintain a hand-written copy.
        """
        ...

    def execute(self, call: ToolCall) -> ToolResult:
        """Execute exactly one tool call."""
        ...
