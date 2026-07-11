"""Fallback strategies."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from specflow.context import _redact_secrets, _strip_control
from specflow.fallback.models import FallbackLevel, FallbackResult


@dataclass(frozen=True)
class RetryStrategy:
    """Bounded retry strategy."""

    max_retries: int = 2

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")

    def run(self, operation: Callable[[], str]) -> tuple[str, int, Exception | None]:
        attempts = 0
        last_error: Exception | None = None
        while attempts <= self.max_retries:
            try:
                return operation(), attempts, None
            except Exception as exc:
                last_error = exc
                attempts += 1
        return "", self.max_retries, last_error


class JsonRepairStrategy:
    """Extract and validate a JSON object from noisy model text."""

    _JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

    def repair(self, raw_response: str) -> str | None:
        match = self._JSON_OBJECT_RE.search(raw_response)
        if not match:
            return None
        candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class RuleBaselineStrategy:
    """Produce an honest degraded result without pretending AI succeeded."""

    def build(self, error: Exception | None, retry_count: int) -> FallbackResult:
        error_type = type(error).__name__ if error else None
        return FallbackResult(
            status="degraded",
            fallback_level=FallbackLevel.RULE_BASELINE,
            content="Fallback baseline: runtime failed; manual review is required.",
            confidence=0.0,
            requires_review=True,
            error_type=error_type,
            retry_count=retry_count,
        )


def sanitize_fallback_content(content: str) -> str:
    """Apply existing T-005 redaction and control-character stripping."""
    return _strip_control(_redact_secrets(content))
