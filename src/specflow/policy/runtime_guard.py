"""RuntimeGuard — enforces execution policy budgets during a run."""

from __future__ import annotations

import time as _time
from collections.abc import Callable

from specflow.policy.models import (
    ExecutionPolicy,
    SpecFlowError,
)


class RuntimeGuard:
    """Tracks and enforces time, call, token, revision, and artifact budgets.

    All checks are O(1).  The time source can be injected for testing.
    """

    def __init__(
        self,
        policy: ExecutionPolicy,
        *,
        time_source: Callable[[], float] = _time.monotonic,
    ) -> None:
        self._policy = policy
        self._time = time_source
        self._started_at = self._time()
        self._llm_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._revision_count = 0
        self._agent_count = 0

    # ── budget consumption ───────────────────────────────────────

    def consume_llm_call(self) -> None:
        self._llm_calls += 1
        if self._llm_calls > self._policy.max_llm_calls:
            raise SpecFlowError(
                code="CALL_BUDGET_EXCEEDED",
                safe_message=f"LLM call budget exceeded ({self._policy.max_llm_calls})",
                retryable=False,
            )

    def consume_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        total = self._total_input_tokens + self._total_output_tokens
        if total > self._policy.tokens.max_run_total_tokens:
            raise SpecFlowError(
                code="TOKEN_BUDGET_EXCEEDED",
                safe_message=(
                    f"Run token budget exceeded"
                    f" ({self._policy.tokens.max_run_total_tokens})"
                ),
                retryable=False,
            )

    def consume_revision(self) -> None:
        self._revision_count += 1
        if self._revision_count > self._policy.max_revisions:
            raise SpecFlowError(
                code="REVISION_BUDGET_EXCEEDED",
                safe_message=f"Revision budget exceeded ({self._policy.max_revisions})",
                retryable=False,
            )

    def consume_agent(self) -> None:
        self._agent_count += 1
        if self._agent_count > self._policy.max_parallel_agents:
            raise SpecFlowError(
                code="PARALLEL_AGENT_LIMIT_EXCEEDED",
                safe_message=f"Parallel agent limit exceeded ({self._policy.max_parallel_agents})",
                retryable=False,
            )

    # ── wall-time check ──────────────────────────────────────────

    def check_wall_time(self) -> None:
        elapsed = self._time() - self._started_at
        if elapsed > self._policy.max_wall_time_seconds:
            raise SpecFlowError(
                code="TIME_BUDGET_EXCEEDED",
                safe_message=(
                    f"Wall-time budget exceeded ({self._policy.max_wall_time_seconds}s)"
                ),
                retryable=False,
                details={"elapsed_seconds": elapsed},
            )

    # ── artifact size check ──────────────────────────────────────

    def check_artifact_size(self, size_bytes: int) -> None:
        if size_bytes > self._policy.artifacts.max_artifact_bytes:
            raise SpecFlowError(
                code="ARTIFACT_LIMIT_EXCEEDED",
                safe_message=(
                    f"Artifact size {size_bytes} exceeds limit "
                    f"({self._policy.artifacts.max_artifact_bytes})"
                ),
                retryable=False,
            )

    # ── query ────────────────────────────────────────────────────

    @property
    def llm_calls(self) -> int:
        return self._llm_calls

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens

    @property
    def revision_count(self) -> int:
        return self._revision_count

    @property
    def agent_count(self) -> int:
        return self._agent_count
