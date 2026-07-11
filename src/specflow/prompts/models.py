"""Structured prompt models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from specflow.prompts.renderer import PromptRenderer


@dataclass(frozen=True)
class PromptDefinition:
    """A versioned prompt asset with metadata, template, and stable hash."""

    name: str
    version: str
    description: str
    purpose: str
    required_variables: list[str]
    output_format: dict[str, Any]
    owner: str
    created_at: str
    template: str
    metadata: dict[str, Any] = field(default_factory=dict)
    prompt_hash: str = ""

    def __post_init__(self) -> None:
        if not self.prompt_hash:
            object.__setattr__(self, "prompt_hash", self.calculate_hash())

    def calculate_hash(self) -> str:
        """Return a stable SHA-256 digest for metadata and template content."""
        payload = {
            "metadata": self.metadata,
            "template": self.template,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def render(self, variables: dict[str, object]) -> str:
        """Render this prompt with strict variable handling."""
        return PromptRenderer().render(self, variables)
