"""Fallback Manager."""

from __future__ import annotations

import json
from collections.abc import Callable

from specflow.fallback.models import FallbackLevel, FallbackResult
from specflow.fallback.strategies import (
    JsonRepairStrategy,
    RetryStrategy,
    RuleBaselineStrategy,
    sanitize_fallback_content,
)


class FallbackManager:
    """Coordinate retry, JSON repair, and rule baseline fallback."""

    def __init__(
        self,
        retry_strategy: RetryStrategy | None = None,
        json_repair_strategy: JsonRepairStrategy | None = None,
        rule_baseline_strategy: RuleBaselineStrategy | None = None,
    ) -> None:
        self._retry = retry_strategy or RetryStrategy()
        self._json_repair = json_repair_strategy or JsonRepairStrategy()
        self._baseline = rule_baseline_strategy or RuleBaselineStrategy()

    def execute(
        self,
        operation: Callable[[], str],
        *,
        expect_json: bool = False,
    ) -> FallbackResult:
        content, retry_count, error = self._retry.run(operation)
        if error is not None:
            return self._baseline.build(error=error, retry_count=retry_count)

        safe_content = sanitize_fallback_content(content)
        fallback_level = FallbackLevel.RETRY if retry_count else FallbackLevel.NONE
        if expect_json:
            if self._is_valid_json(safe_content):
                return self._success(safe_content, fallback_level, retry_count)
            repaired = self._json_repair.repair(safe_content)
            if repaired is not None:
                return self._success(repaired, FallbackLevel.JSON_REPAIR, retry_count)
            return self._baseline.build(error=None, retry_count=retry_count)

        return self._success(safe_content, fallback_level, retry_count)

    @staticmethod
    def _success(content: str, level: FallbackLevel, retry_count: int) -> FallbackResult:
        return FallbackResult(
            status="success",
            fallback_level=level,
            content=content,
            confidence=1.0 if level in {FallbackLevel.NONE, FallbackLevel.RETRY} else 0.8,
            requires_review=False,
            retry_count=retry_count,
        )

    @staticmethod
    def _is_valid_json(content: str) -> bool:
        try:
            json.loads(content)
        except json.JSONDecodeError:
            return False
        return True
