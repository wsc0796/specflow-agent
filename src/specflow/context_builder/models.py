"""Context Builder data models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextSource:
    """A deterministic source reference used by a built context."""

    kind: str
    identifier: str
    hash: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "kind": self.kind,
            "identifier": self.identifier,
            "hash": self.hash,
        }


@dataclass(frozen=True)
class BuiltContext:
    """Structured LLM-input payload assembled without calling an LLM."""

    system_message: str
    user_message: str
    sources: list[ContextSource]
    estimated_tokens: int
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    project_context_hash: str
    context_hash: str = field(default="")

    def __post_init__(self) -> None:
        if not self.context_hash:
            object.__setattr__(self, "context_hash", self.calculate_hash())

    def calculate_hash(self) -> str:
        """Return a stable digest for content-significant built-context fields."""
        payload = {
            "system_message": self.system_message,
            "user_message": self.user_message,
            "sources": [source.as_dict() for source in self.sources],
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "project_context_hash": self.project_context_hash,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
