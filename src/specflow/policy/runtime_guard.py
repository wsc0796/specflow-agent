"""RuntimeGuard — enforces execution policy budgets during a run."""

from __future__ import annotations

import time as _time
from collections.abc import Callable
from threading import Lock

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
        self._lock = Lock()

    # ── budget consumption ───────────────────────────────────────

    def consume_llm_call(self) -> None:
        self._llm_calls += 1
        if self._llm_calls > self._policy.max_llm_calls:
            raise SpecFlowError(
                code="CALL_BUDGET_EXCEEDED",
                safe_message=f"LLM call budget exceeded ({self._policy.max_llm_calls})",
                retryable=False,
            )

    def consume_tokens(
        self, input_tokens: int, output_tokens: int, *, is_retry: bool = False
    ) -> None:
        """Consume one agent result while enforcing every token boundary.

        Normal calls cannot consume the reserved retry allowance.  Retry calls
        may use it, but remain bounded by the run-wide total.
        """
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            raise SpecFlowError(
                code="TOKEN_BUDGET_EXCEEDED",
                safe_message="Token usage must be integer values",
                retryable=False,
            )
        if input_tokens < 0 or output_tokens < 0:
            raise SpecFlowError(
                code="TOKEN_BUDGET_EXCEEDED",
                safe_message="Token usage cannot be negative",
                retryable=False,
            )
        token_policy = self._policy.tokens
        if input_tokens > token_policy.max_agent_input_tokens:
            raise SpecFlowError(
                code="TOKEN_BUDGET_EXCEEDED",
                safe_message=(
                    f"Agent input token budget exceeded ({token_policy.max_agent_input_tokens})"
                ),
                retryable=False,
            )
        if output_tokens > token_policy.max_agent_output_tokens:
            raise SpecFlowError(
                code="TOKEN_BUDGET_EXCEEDED",
                safe_message=(
                    f"Agent output token budget exceeded ({token_policy.max_agent_output_tokens})"
                ),
                retryable=False,
            )
        with self._lock:
            next_input = self._total_input_tokens + input_tokens
            next_output = self._total_output_tokens + output_tokens
            total = next_input + next_output
            if next_input > token_policy.max_run_input_tokens:
                raise SpecFlowError(
                    code="TOKEN_BUDGET_EXCEEDED",
                    safe_message=(
                        f"Run input token budget exceeded ({token_policy.max_run_input_tokens})"
                    ),
                    retryable=False,
                )
            if next_output > token_policy.max_run_output_tokens:
                raise SpecFlowError(
                    code="TOKEN_BUDGET_EXCEEDED",
                    safe_message=(
                        f"Run output token budget exceeded ({token_policy.max_run_output_tokens})"
                    ),
                    retryable=False,
                )
            normal_limit = token_policy.max_run_total_tokens
            if not is_retry:
                normal_limit -= token_policy.reserved_retry_tokens
            if total > normal_limit:
                raise SpecFlowError(
                    code="TOKEN_BUDGET_EXCEEDED",
                    safe_message=(f"Run token budget exceeded ({normal_limit})"),
                    retryable=False,
                )
            self._total_input_tokens = next_input
            self._total_output_tokens = next_output

    def check_parallel_agents(self, count: int) -> None:
        """Reject a stage whose declared parallelism exceeds the policy."""
        if count < 0 or count > self._policy.max_parallel_agents:
            raise SpecFlowError(
                code="PARALLEL_AGENT_LIMIT_EXCEEDED",
                safe_message=f"Parallel agent limit exceeded ({self._policy.max_parallel_agents})",
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

    # ── wall-time check ──────────────────────────────────────────

    def check_wall_time(self) -> None:
        elapsed = self._time() - self._started_at
        if elapsed > self._policy.max_wall_time_seconds:
            raise SpecFlowError(
                code="TIME_BUDGET_EXCEEDED",
                safe_message=(f"Wall-time budget exceeded ({self._policy.max_wall_time_seconds}s)"),
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
