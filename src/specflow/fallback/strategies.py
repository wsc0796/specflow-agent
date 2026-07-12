"""Fallback strategies."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from specflow.context import _redact_secrets, _strip_control
from specflow.fallback.models import FallbackLevel, FallbackResult
from specflow.policy.errors import ErrorCode, is_retryable


@dataclass(frozen=True)
class RetryStrategy:
    """Bounded retry strategy."""

    max_retries: int = 2
    base_backoff_seconds: float = 0.1

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.base_backoff_seconds < 0:
            raise ValueError("base_backoff_seconds must not be negative")

    def run(self, operation: Callable[[], str]) -> tuple[str, int, Exception | None]:
        attempts = 0
        last_error: Exception | None = None
        while attempts <= self.max_retries:
            try:
                return operation(), attempts, None
            except Exception as exc:
                last_error = exc
                if attempts >= self.max_retries or not is_retryable(_error_to_code(exc)):
                    return "", attempts, last_error
                attempts += 1
                if self.base_backoff_seconds:
                    time.sleep(min(self.base_backoff_seconds * (2 ** (attempts - 1)), 5.0))
        return "", self.max_retries, last_error


def _error_to_code(error: Exception) -> ErrorCode:
    """Map only known transient provider failures to retryable codes."""
    if isinstance(error, TimeoutError):
        return ErrorCode.PROVIDER_TIMEOUT
    text = str(error).lower()
    if "429" in text or "rate" in text:
        return ErrorCode.PROVIDER_RATE_LIMITED
    if "timeout" in text or "timed out" in text:
        return ErrorCode.PROVIDER_TIMEOUT
    if "connection" in text or "network" in text:
        return ErrorCode.PROVIDER_CONNECTION_ERROR
    if any(code in text for code in ("500", "502", "503", "server")):
        return ErrorCode.PROVIDER_SERVER_ERROR
    if "401" in text or "403" in text or "auth" in text or "unauthorized" in text:
        return ErrorCode.PROVIDER_AUTH_FAILURE
    if any(term in text for term in ("security", "traversal", "sensitive", "redaction")):
        return ErrorCode.SECURITY_PATH_TRAVERSAL
    return ErrorCode.INTERNAL_UNEXPECTED


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
