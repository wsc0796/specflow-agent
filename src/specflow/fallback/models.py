"""Fallback System models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FallbackLevel(StrEnum):
    """Runtime fallback level applied to an operation result."""

    NONE = "none"
    RETRY = "retry"
    JSON_REPAIR = "json_repair"
    RULE_BASELINE = "rule_baseline"


@dataclass(frozen=True)
class FallbackResult:
    """Outcome of runtime fallback handling."""

    status: str
    fallback_level: FallbackLevel
    content: str
    confidence: float
    requires_review: bool
    error_type: str | None = None
    retry_count: int = 0

    def __post_init__(self) -> None:
        if self.status not in {"success", "degraded"}:
            raise ValueError("FallbackResult.status must be success or degraded")
        if not 0 <= self.confidence <= 1:
            raise ValueError("FallbackResult.confidence must be between 0 and 1")
