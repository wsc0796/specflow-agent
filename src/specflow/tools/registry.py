"""Deterministic Tool Registry."""

from __future__ import annotations

from specflow.tools.base import Tool
from specflow.tools.exceptions import DuplicateToolError, ToolNotFoundError
from specflow.tools.models import ToolMetadata


class ToolRegistry:
    """Explicit, deterministic registry for Tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by stable metadata name."""
        metadata = tool.metadata
        if metadata.name in self._tools:
            raise DuplicateToolError(f"Tool already registered: {metadata.name}")
        self._tools[metadata.name] = tool

    def get(self, name: str) -> Tool:
        """Return a tool by name."""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Tool not registered: {name}") from exc

    def has(self, name: str) -> bool:
        """Return whether a tool name is registered."""
        return name in self._tools

    def metadata(self) -> tuple[ToolMetadata, ...]:
        """Return tool metadata in deterministic name order."""
        return tuple(self._tools[name].metadata for name in sorted(self._tools))
