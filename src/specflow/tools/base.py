"""Tool Framework base protocol."""

from __future__ import annotations

from typing import Protocol

from specflow.tools.models import ToolCall, ToolMetadata, ToolResult


class Tool(Protocol):
    """Protocol implemented by tools."""

    @property
    def metadata(self) -> ToolMetadata:
        """Return stable tool metadata."""
        ...

    def execute(self, call: ToolCall) -> ToolResult:
        """Execute exactly one tool call."""
        ...
