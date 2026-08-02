"""RuntimeGuard — run-scoped budget, invocation, and token accounting.

Phase 3 centralizes the facts a run must agree on:

- configured role count (topology) vs agent invocations (role executions);
- agent invocations vs provider call attempts (one invocation may contain
  multiple attempts, including retries);
- real provider attempts vs synthetic/mock model calls;
- known token usage vs unavailable usage (never silently 0).

The legacy counters (``llm_calls``, ``consume_llm_call``, ``consume_tokens``)
are kept as deprecated, deterministically mapped compatibility accessors for
older tests and callers; new runtime code must use ``reserve_provider_attempt``,
``release_provider_attempt``, agent-invocation methods, and ``snapshot()``.
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from specflow.policy.models import (
    ExecutionPolicy,
    SpecFlowError,
)


@dataclass(frozen=True)
class ProviderAttempt:
    """One reserved provider-call attempt (release is mandatory)."""

    attempt_index: int
    call_type: str
    agent_id: str | None
    revision_id: str | None
    started_monotonic: float


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
        self._run_id: str = ""
        self._execution_mode: str = "mock"
        self._configured_role_count = 0

        # Agent invocation accounting
        self._agent_scheduled = 0
        self._agent_started = 0
        self._agent_completed = 0
        self._agent_failed = 0
        self._agent_active = 0

        # Provider call accounting
        self._provider_attempts = 0
        self._provider_success = 0
        self._provider_failed = 0
        self._provider_active = 0
        self._provider_peak_active = 0

        # Synthetic (mock) model calls — never confused with real provider calls
        self._synthetic_model_calls = 0

        # Token accounting (known usage only; unknown is tracked separately)
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._token_usage_known = False
        self._token_usage_unknown_calls = 0

        # Revision accounting
        self._revision_count = 0
        self._revision_agent_invocations = 0
        self._re_review_invocations = 0

        # Timing
        self._provider_latency_ms = 0
        self._agent_latency_ms = 0

        # Artifact bytes
        self._artifact_bytes_written = 0

        # Legacy alias for consume_llm_call (deprecated)
        self._legacy_llm_calls = 0

        self._budget_snapshots: list[dict[str, object]] = []
        self._model_call_events: list[dict[str, object]] = []
        self._lock = Lock()

    # ── run context ──────────────────────────────────────────────

    def set_run_context(self, run_id: str, *, execution_mode: str) -> None:
        """Bind this guard to one run and its execution mode."""
        with self._lock:
            self._run_id = run_id
            self._execution_mode = execution_mode

    def set_configured_role_count(self, count: int) -> None:
        """Record the topology's configured role count (not a budget)."""
        if count < 0:
            raise SpecFlowError(
                code="CONFIGURATION_ERROR",
                safe_message="configured_role_count cannot be negative",
                retryable=False,
            )
        with self._lock:
            self._configured_role_count = count

    @property
    def execution_mode(self) -> str:
        return self._execution_mode

    # ── deprecated budget consumption ────────────────────────────

    def consume_llm_call(self) -> None:
        """Deprecated: use ``reserve_provider_attempt`` in new code."""
        with self._lock:
            next_value = self._legacy_llm_calls + 1
            if next_value > self._policy.max_llm_calls:
                raise SpecFlowError(
                    code="CALL_BUDGET_EXCEEDED",
                    safe_message=(f"LLM call budget exceeded ({self._policy.max_llm_calls})"),
                    retryable=False,
                )
            self._legacy_llm_calls = next_value

    def consume_tokens(
        self, input_tokens: int, output_tokens: int, *, is_retry: bool = False
    ) -> None:
        """Deprecated: token accounting now happens in ``release_provider_attempt``."""
        self._consume_tokens_legacy(input_tokens, output_tokens, is_retry=is_retry)

    def _consume_tokens_legacy(
        self, input_tokens: int, output_tokens: int, *, is_retry: bool
    ) -> None:
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

    # ── provider attempt reservation (new, atomic) ───────────────

    def reserve_provider_attempt(
        self,
        *,
        call_type: str,
        agent_id: str | None = None,
        revision_id: str | None = None,
    ) -> ProviderAttempt:
        """Atomically validate and reserve one real provider attempt.

        Checks wall-clock, parallel-active, and total-attempt budgets in the
        same critical section as the counter increments, so a rejected request
        is never actually sent and counters never exceed ``max + 1``.
        """
        with self._lock:
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
            if self._provider_active >= self._policy.max_parallel_provider_calls:
                raise SpecFlowError(
                    code="PARALLEL_PROVIDER_LIMIT_EXCEEDED",
                    safe_message=(
                        f"Parallel provider limit exceeded "
                        f"({self._policy.max_parallel_provider_calls})"
                    ),
                    retryable=False,
                )
            if self._provider_attempts >= self._policy.max_provider_call_attempts:
                raise SpecFlowError(
                    code="PROVIDER_CALL_BUDGET_EXCEEDED",
                    safe_message=(
                        f"Provider call budget exceeded ({self._policy.max_provider_call_attempts})"
                    ),
                    retryable=False,
                )
            self._provider_attempts += 1
            self._provider_active += 1
            self._provider_peak_active = max(self._provider_peak_active, self._provider_active)
            attempt = ProviderAttempt(
                attempt_index=self._provider_attempts,
                call_type=call_type,
                agent_id=agent_id,
                revision_id=revision_id,
                started_monotonic=self._time(),
            )
            self._record_budget_snapshot_locked("MODEL_CALL_STARTED", attempt)
            return attempt

    def release_provider_attempt(
        self,
        attempt: ProviderAttempt,
        *,
        success: bool,
        error_code: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: int = 0,
    ) -> None:
        """Atomically settle one attempt: counters, tokens, latency, snapshot."""
        with self._lock:
            self._provider_active = max(0, self._provider_active - 1)
            if success:
                self._provider_success += 1
            else:
                self._provider_failed += 1
            self._provider_latency_ms += max(0, latency_ms)
            if input_tokens is None or output_tokens is None:
                self._token_usage_unknown_calls += 1
                self._record_budget_snapshot_locked("TOKEN_USAGE_UNAVAILABLE", attempt)
            else:
                self._consume_tokens_locked(input_tokens, output_tokens)
                self._token_usage_known = True
                self._record_budget_snapshot_locked("TOKEN_USAGE_RECORDED", attempt)
            if success:
                self._record_budget_snapshot_locked("MODEL_CALL_SUCCEEDED", attempt)
            else:
                self._record_budget_snapshot_locked(
                    "MODEL_CALL_FAILED", attempt, error_code=error_code
                )

    def record_synthetic_model_call(self, *, call_type: str) -> None:
        """Record a mock/synthetic model call that is NOT a provider attempt."""
        with self._lock:
            self._synthetic_model_calls += 1
            self._model_call_events.append(
                {
                    "event_type": "MODEL_CALL_SUCCEEDED",
                    "run_id": self._run_id,
                    "call_type": call_type,
                    "execution_mode": "mock",
                    "attempt_index": self._synthetic_model_calls,
                    "synthetic": True,
                }
            )

    def _consume_tokens_locked(self, input_tokens: int, output_tokens: int) -> None:
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
        if total > token_policy.max_run_total_tokens:
            raise SpecFlowError(
                code="TOKEN_BUDGET_EXCEEDED",
                safe_message=(f"Run token budget exceeded ({token_policy.max_run_total_tokens})"),
                retryable=False,
            )
        self._total_input_tokens = next_input
        self._total_output_tokens = next_output

    # ── agent invocation accounting ──────────────────────────────

    def schedule_agent_invocation(self) -> None:
        with self._lock:
            self._agent_scheduled += 1

    def start_agent_invocation(self) -> None:
        with self._lock:
            self._agent_started += 1
            self._agent_active += 1

    def complete_agent_invocation(self, *, failed: bool = False) -> None:
        with self._lock:
            self._agent_active = max(0, self._agent_active - 1)
            if failed:
                self._agent_failed += 1
            else:
                self._agent_completed += 1

    def record_agent_latency(self, latency_ms: int) -> None:
        with self._lock:
            self._agent_latency_ms += max(0, latency_ms)

    def record_revision_round(self) -> None:
        with self._lock:
            self._revision_count += 1

    def record_revision_agent_invocation(self) -> None:
        with self._lock:
            self._revision_agent_invocations += 1

    def record_re_review_invocation(self) -> None:
        with self._lock:
            self._re_review_invocations += 1

    def record_artifact_bytes(self, size_bytes: int) -> None:
        with self._lock:
            self._artifact_bytes_written += max(0, size_bytes)

    # ── budget snapshot ──────────────────────────────────────────

    def snapshot(self) -> dict[str, object]:
        """Return the current, consistent budget snapshot."""
        with self._lock:
            return self._snapshot_locked()

    @property
    def last_budget_snapshot(self) -> dict[str, object] | None:
        with self._lock:
            return self._budget_snapshots[-1] if self._budget_snapshots else None

    def model_call_events(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            return tuple(self._model_call_events)

    def record_model_call_event(self, event: dict[str, object]) -> None:
        """Append an external model-call event (e.g. retry) with run context."""
        with self._lock:
            self._model_call_events.append({**event, "run_id": self._run_id})

    def _snapshot_locked(self) -> dict[str, object]:
        return {
            "execution_mode": self._execution_mode,
            "configured_role_count": self._configured_role_count,
            "limits": {
                "max_provider_call_attempts": self._policy.max_provider_call_attempts,
                "max_parallel_provider_calls": self._policy.max_parallel_provider_calls,
                "max_wall_time_seconds": self._policy.max_wall_time_seconds,
                "max_revisions": self._policy.max_revisions,
                "max_run_input_tokens": self._policy.tokens.max_run_input_tokens,
                "max_run_output_tokens": self._policy.tokens.max_run_output_tokens,
                "max_run_total_tokens": self._policy.tokens.max_run_total_tokens,
                "max_artifact_bytes": self._policy.artifacts.max_artifact_bytes,
            },
            "agent_invocations": {
                "scheduled": self._agent_scheduled,
                "started": self._agent_started,
                "completed": self._agent_completed,
                "failed": self._agent_failed,
                "active": self._agent_active,
            },
            "provider_calls": {
                "attempts": self._provider_attempts,
                "successful": self._provider_success,
                "failed": self._provider_failed,
                "active": self._provider_active,
                "peak_active": self._provider_peak_active,
            },
            "synthetic_model_calls": self._synthetic_model_calls,
            "revision": {
                "rounds": self._revision_count,
                "agent_invocations": self._revision_agent_invocations,
                "re_review_invocations": self._re_review_invocations,
            },
            "tokens": {
                "input_tokens": self._total_input_tokens,
                "output_tokens": self._total_output_tokens,
                "total_tokens": self._total_input_tokens + self._total_output_tokens,
                "usage_known": self._token_usage_known,
                "unknown_calls": self._token_usage_unknown_calls,
            },
            "timing": {
                "wall_clock_elapsed_ms": int((self._time() - self._started_at) * 1000),
                "provider_latency_ms": self._provider_latency_ms,
                "agent_latency_ms": self._agent_latency_ms,
            },
            "artifact_bytes_written": self._artifact_bytes_written,
            "snapshot_id": uuid4().hex,
        }

    def _record_budget_snapshot_locked(
        self,
        event_type: str,
        attempt: ProviderAttempt,
        *,
        error_code: str | None = None,
    ) -> None:
        snapshot = self._snapshot_locked()
        self._budget_snapshots.append(snapshot)
        self._model_call_events.append(
            {
                "event_type": event_type,
                "run_id": self._run_id,
                "call_type": attempt.call_type,
                "agent_id": attempt.agent_id,
                "revision_id": attempt.revision_id,
                "attempt_index": attempt.attempt_index,
                "error_code": error_code,
                "snapshot_id": snapshot["snapshot_id"],
            }
        )

    def check_parallel_agents(self, count: int) -> None:
        """Reject a stage whose declared parallelism exceeds the policy."""
        if count < 0 or count > self._policy.max_parallel_agents:
            raise SpecFlowError(
                code="PARALLEL_AGENT_LIMIT_EXCEEDED",
                safe_message=f"Parallel agent limit exceeded ({self._policy.max_parallel_agents})",
                retryable=False,
            )

    def consume_revision(self) -> None:
        """Deprecated: use ``record_revision_round`` after the controller gate."""
        with self._lock:
            self._revision_count += 1
            if self._revision_count > self._policy.max_revisions:
                raise SpecFlowError(
                    code="REVISION_BUDGET_EXCEEDED",
                    safe_message=(f"Revision budget exceeded ({self._policy.max_revisions})"),
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
        """Deprecated: returns the legacy alias counter, not provider attempts."""
        return self._legacy_llm_calls

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens

    @property
    def revision_count(self) -> int:
        return self._revision_count
