"""Token Budget Manager data models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from specflow.context_builder import BuiltContext

DEFAULT_SECTION_PRIORITIES: dict[str, int] = {
    "system_message": 100,
    "requirement": 90,
    "project_overview": 80,
    "technology_stack": 70,
    "source_tracking": 60,
    "evidence": 50,
    "warnings": 40,
    "unknowns": 30,
}


@dataclass(frozen=True)
class BudgetPolicy:
    """Deterministic input budget policy."""

    max_tokens: int
    reserved_response_tokens: int = 0
    estimation_chars_per_token: int = 4
    section_priorities: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_SECTION_PRIORITIES)
    )

    @property
    def input_budget(self) -> int:
        return self.max_tokens - self.reserved_response_tokens

    def as_dict(self) -> dict[str, object]:
        return {
            "max_tokens": self.max_tokens,
            "reserved_response_tokens": self.reserved_response_tokens,
            "estimation_chars_per_token": self.estimation_chars_per_token,
            "section_priorities": dict(sorted(self.section_priorities.items())),
        }


@dataclass(frozen=True)
class RemovedSection:
    """A section removed during deterministic budget trimming."""

    name: str
    estimated_tokens: int
    priority: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "name": self.name,
            "estimated_tokens": self.estimated_tokens,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class BudgetResult:
    """Budgeted context plus trimming evidence."""

    context: BuiltContext
    policy: BudgetPolicy
    original_estimated_tokens: int
    final_estimated_tokens: int
    was_trimmed: bool
    removed_sections: list[RemovedSection]
    context_hash: str = ""

    def __post_init__(self) -> None:
        if not self.context_hash:
            object.__setattr__(self, "context_hash", self.calculate_hash())

    def calculate_hash(self) -> str:
        payload = {
            "context_hash": self.context.context_hash,
            "policy": self.policy.as_dict(),
            "original_estimated_tokens": self.original_estimated_tokens,
            "final_estimated_tokens": self.final_estimated_tokens,
            "was_trimmed": self.was_trimmed,
            "removed_sections": [section.as_dict() for section in self.removed_sections],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
