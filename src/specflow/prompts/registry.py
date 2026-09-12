"""Prompt Registry entry point."""

from __future__ import annotations

from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from specflow.prompts.loader import PromptLoader
from specflow.prompts.models import PromptDefinition


class PromptRegistry:
    """Load versioned prompt definitions from a Git-managed prompt root."""

    def __init__(self, prompts_root: Path | str | None = None) -> None:
        self._root = (
            resources.files("specflow").joinpath("prompt_assets")
            if prompts_root is None
            else Path(prompts_root)
        )
        self._loader = None if prompts_root is None else PromptLoader(Path(prompts_root))

    @property
    def root(self) -> Path | Traversable:
        return self._root

    def get(self, name: str, version: str) -> PromptDefinition:
        """Return a prompt definition by name and semantic version."""
        if self._loader is not None:
            return self._loader.load(name, version)
        # PromptDefinition owns strings/metadata, never a temporary resource path.
        # Keep extraction alive until the loader has read both metadata and template.
        with resources.as_file(self._root) as root:
            return PromptLoader(root).load(name, version)
