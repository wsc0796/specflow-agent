"""Prompt Registry entry point."""

from __future__ import annotations

from pathlib import Path

from specflow.prompts.loader import PromptLoader
from specflow.prompts.models import PromptDefinition


class PromptRegistry:
    """Load versioned prompt definitions from a Git-managed prompt root."""

    def __init__(self, prompts_root: Path | str = "prompts") -> None:
        self._root = Path(prompts_root)
        self._loader = PromptLoader(self._root)

    @property
    def root(self) -> Path:
        return self._root

    def get(self, name: str, version: str) -> PromptDefinition:
        """Return a prompt definition by name and semantic version."""
        return self._loader.load(name, version)
