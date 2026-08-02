"""Phase 3 tests: unified invocation, budget, retry, token, and concurrency facts."""

from __future__ import annotations

import ast
import json
import threading
import time
from pathlib import Path

import pytest

from specflow.invoker import GuardedModelInvoker
from specflow.llm.models import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from specflow.policy.models import (
    ExecutionPolicy,
    SpecFlowError,
    TokenPolicy,
)
from specflow.policy.runtime_guard import ProviderAttempt, RuntimeGuard


def _request() -> LLMRequest:
    return LLMRequest(model="test-model", messages=[LLMMessage(role="user", content="hi")])


def _response(
    *,
    content: str = '{"ok": true}',
    input_tokens: int | None = 10,
    output_tokens: int | None = 5,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="test-model",
        latency_ms=3,
        finish_reason="stop",
        usage=(
            LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens)
            if input_tokens is not None and output_tokens is not None
            else None
        ),
    )


class ScriptedClient:
    """Deterministic client: per-call success/failure/usage scripts."""

    def __init__(
        self,
        *,
        failures: int = 0,
        failure_error: Exception | None = None,
        usage: tuple[int, int] | None = (10, 5),
    ) -> None:
        self.calls = 0
        self.failures = failures
        self.failure_error = failure_error or TimeoutError("provider timeout")
        self.usage = usage

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.failure_error
        usage = (
            LLMUsage(input_tokens=self.usage[0], output_tokens=self.usage[1])
            if self.usage is not None
            else None
        )
        return LLMResponse(
            content='{"ok": true}',
            model="test-model",
            latency_ms=3,
            finish_reason="stop",
            usage=usage,
        )


def _guard(
    *,
    max_attempts: int = 100,
    max_parallel: int = 4,
    max_wall_seconds: int = 300,
    max_input: int = 1_000_000,
    max_output: int = 1_000_000,
    max_total: int = 2_000_000,
    max_agent_input: int = 1_000_000,
    max_agent_output: int = 1_000_000,
    reserved_retry_tokens: int = 6000,
) -> RuntimeGuard:
    policy = ExecutionPolicy(
        max_provider_call_attempts=max_attempts,
        max_parallel_provider_calls=max_parallel,
        max_wall_time_seconds=max_wall_seconds,
        tokens=TokenPolicy(
            max_run_input_tokens=max_input,
            max_run_output_tokens=max_output,
            max_run_total_tokens=max_total,
            max_agent_input_tokens=max_agent_input,
            max_agent_output_tokens=max_agent_output,
            reserved_retry_tokens=reserved_retry_tokens,
        ),
    )
    guard = RuntimeGuard(policy)
    guard.set_run_context("run-test", execution_mode="live")
    guard.set_configured_role_count(6)
    return guard


class TestMetricSemantics:
    def test_configured_role_count_is_topology_not_budget(self) -> None:
        guard = _guard()
        assert guard.snapshot()["configured_role_count"] == 6

    def test_agent_invocation_and_provider_attempt_are_separate(self) -> None:
        guard = _guard()
        guard.schedule_agent_invocation()
        guard.start_agent_invocation()
        invoker = GuardedModelInvoker(ScriptedClient(failures=1), guard, max_provider_retries=2)
        invoker.invoke(_request(), call_type="worker", agent_id="design-agent-v1")
        guard.complete_agent_invocation()
        snapshot = guard.snapshot()
        assert snapshot["agent_invocations"]["started"] == 1
        assert snapshot["agent_invocations"]["completed"] == 1
        assert snapshot["provider_calls"]["attempts"] == 2
        assert snapshot["provider_calls"]["successful"] == 1
        assert snapshot["provider_calls"]["failed"] == 1

    def test_dead_agent_count_getter_removed(self) -> None:
        guard = _guard()
        assert not hasattr(guard, "agent_count")

    def test_mock_execution_is_synthetic_not_provider_call(self) -> None:
        guard = _guard()
        guard.set_run_context("run-test", execution_mode="mock")
        invoker = GuardedModelInvoker(ScriptedClient(), guard)
        invoker.invoke(_request(), call_type="enrichment")
        snapshot = guard.snapshot()
        assert snapshot["provider_calls"]["attempts"] == 0
        assert snapshot["synthetic_model_calls"] == 1


class TestRetryAccounting:
    def test_fail_then_success_counts_one_invocation_two_attempts(self) -> None:
        guard = _guard()
        client = ScriptedClient(failures=1)
        invoker = GuardedModelInvoker(client, guard, max_provider_retries=2)
        guard.schedule_agent_invocation()
        guard.start_agent_invocation()
        response = invoker.invoke(_request(), call_type="worker", agent_id="a1")
        guard.complete_agent_invocation()
        assert client.calls == 2
        assert response.content == '{"ok": true}'
        snapshot = guard.snapshot()
        assert snapshot["agent_invocations"]["completed"] == 1
        assert snapshot["provider_calls"]["attempts"] == 2
        assert snapshot["provider_calls"]["successful"] == 1
        assert snapshot["provider_calls"]["failed"] == 1
        assert snapshot["provider_calls"]["active"] == 0

    def test_each_attempt_has_own_trace_event(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(ScriptedClient(failures=1), guard, max_provider_retries=2)
        invoker.invoke(_request(), call_type="worker")
        events = guard.model_call_events()
        event_types = [event["event_type"] for event in events]
        assert event_types.count("MODEL_CALL_STARTED") == 2
        assert event_types.count("MODEL_CALL_FAILED") == 1
        assert event_types.count("MODEL_CALL_RETRYING") == 1
        assert event_types.count("MODEL_CALL_SUCCEEDED") == 1

    def test_retry_is_bounded_by_total_attempt_budget(self) -> None:
        guard = _guard(max_attempts=1)
        invoker = GuardedModelInvoker(ScriptedClient(failures=99), guard, max_provider_retries=5)
        with pytest.raises(SpecFlowError, match="Provider call budget exceeded"):
            invoker.invoke(_request(), call_type="worker")
        assert guard.snapshot()["provider_calls"]["attempts"] == 1
        assert guard.snapshot()["provider_calls"]["active"] == 0

    def test_retry_respects_wall_clock(self) -> None:
        tick = [0.0]
        policy = ExecutionPolicy(max_wall_time_seconds=1, max_provider_call_attempts=100)
        guard = RuntimeGuard(policy, time_source=lambda: tick[0])
        guard.set_run_context("run-test", execution_mode="live")
        invoker = GuardedModelInvoker(ScriptedClient(failures=99), guard, max_provider_retries=5)
        tick[0] = 5.0  # wall clock already expired
        with pytest.raises(SpecFlowError, match="Wall-time budget exceeded"):
            invoker.invoke(_request(), call_type="worker")
        assert guard.snapshot()["provider_calls"]["attempts"] == 0

    def test_retry_failure_is_not_overwritten_by_final_success(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(ScriptedClient(failures=1), guard, max_provider_retries=2)
        invoker.invoke(_request(), call_type="worker")
        snapshot = guard.snapshot()
        assert snapshot["provider_calls"]["failed"] == 1
        assert snapshot["provider_calls"]["successful"] == 1

    def test_active_count_recovers_after_retry_chain(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(ScriptedClient(failures=2), guard, max_provider_retries=2)
        invoker.invoke(_request(), call_type="worker")
        assert guard.snapshot()["provider_calls"]["active"] == 0


class TestTokenAccounting:
    def test_tokens_read_from_real_response_usage(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(ScriptedClient(usage=(123, 45)), guard)
        invoker.invoke(_request(), call_type="worker")
        tokens = guard.snapshot()["tokens"]
        assert tokens["input_tokens"] == 123
        assert tokens["output_tokens"] == 45
        assert tokens["total_tokens"] == 168
        assert tokens["usage_known"] is True

    def test_missing_usage_is_unknown_not_zero(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(ScriptedClient(usage=None), guard)
        invoker.invoke(_request(), call_type="worker")
        tokens = guard.snapshot()["tokens"]
        assert tokens["usage_known"] is False
        assert tokens["unknown_calls"] == 1
        assert tokens["input_tokens"] is None
        assert tokens["output_tokens"] is None
        assert tokens["total_tokens"] is None
        assert tokens["known_input_tokens"] == 0
        assert tokens["known_output_tokens"] == 0

    def test_mixed_usage_keeps_aggregate_unknown(self) -> None:
        guard = _guard()
        GuardedModelInvoker(ScriptedClient(usage=None), guard).invoke(
            _request(), call_type="worker"
        )
        GuardedModelInvoker(ScriptedClient(usage=(10, 5)), guard).invoke(
            _request(), call_type="worker"
        )
        tokens = guard.snapshot()["tokens"]
        assert tokens["usage_known"] is False
        assert tokens["unknown_calls"] == 1
        assert tokens["input_tokens"] is None
        assert tokens["output_tokens"] is None
        assert tokens["total_tokens"] is None
        assert tokens["known_input_tokens"] == 10
        assert tokens["known_output_tokens"] == 5

    def test_token_budget_fail_closed(self) -> None:
        guard = _guard(max_input=50, max_total=100, reserved_retry_tokens=0)
        invoker = GuardedModelInvoker(ScriptedClient(usage=(100, 0)), guard)
        with pytest.raises(SpecFlowError, match="budget exceeded"):
            invoker.invoke(_request(), call_type="worker")
        # Active count must be restored even when the token check raises.
        assert guard.snapshot()["provider_calls"]["active"] == 0

    def test_normal_calls_cannot_consume_retry_reserve(self) -> None:
        guard = _guard(
            max_input=1_000,
            max_output=1_000,
            max_total=250,
            max_agent_input=1_000,
            max_agent_output=1_000,
            reserved_retry_tokens=50,
        )
        invoker = GuardedModelInvoker(ScriptedClient(usage=(80, 0)), guard)
        invoker.invoke(_request(), call_type="worker")
        invoker.invoke(_request(), call_type="worker")
        with pytest.raises(SpecFlowError, match="budget exceeded"):
            invoker.invoke(_request(), call_type="worker")
        assert guard.snapshot()["tokens"]["known_input_tokens"] == 160

    def test_successful_retry_may_use_retry_reserve(self) -> None:
        guard = _guard(
            max_input=1_000,
            max_output=1_000,
            max_total=250,
            max_agent_input=1_000,
            max_agent_output=1_000,
            reserved_retry_tokens=50,
        )
        normal = GuardedModelInvoker(ScriptedClient(usage=(80, 0)), guard)
        normal.invoke(_request(), call_type="worker")
        normal.invoke(_request(), call_type="worker")
        retrying = GuardedModelInvoker(
            ScriptedClient(failures=1, usage=(80, 0)),
            guard,
            max_provider_retries=1,
            base_backoff_seconds=0,
        )
        retrying.invoke(_request(), call_type="worker")
        snapshot = guard.snapshot()
        assert snapshot["tokens"]["known_input_tokens"] == 240
        assert snapshot["tokens"]["usage_known"] is False


class TestConcurrency:
    def test_parallel_active_and_peak_are_exact(self) -> None:
        guard = _guard(max_parallel=4)
        release = threading.Event()

        class BlockingClient:
            def __init__(self) -> None:
                self.calls = 0

            def complete(self, request: LLMRequest) -> LLMResponse:
                self.calls += 1
                release.wait(timeout=5)
                return _response()

        client = BlockingClient()
        invoker = GuardedModelInvoker(client, guard)
        results: list[Exception | None] = [None] * 3

        def run(index: int) -> None:
            try:
                invoker.invoke(_request(), call_type="worker")
            except Exception as exc:  # pragma: no cover
                results[index] = exc

        threads = [threading.Thread(target=run, args=(i,)) for i in range(3)]
        for thread in threads:
            thread.start()
        time.sleep(0.2)
        mid_snapshot = guard.snapshot()
        assert mid_snapshot["provider_calls"]["active"] == 3
        assert mid_snapshot["provider_calls"]["peak_active"] == 3
        release.set()
        for thread in threads:
            thread.join(timeout=10)
        final = guard.snapshot()
        assert final["provider_calls"]["active"] == 0
        assert final["provider_calls"]["peak_active"] == 3
        assert all(result is None for result in results)

    def test_concurrency_limit_prevents_extra_requests(self) -> None:
        guard = _guard(max_parallel=1)
        hold = threading.Event()

        class SlowClient:
            def __init__(self) -> None:
                self.calls = 0
                self.lock = threading.Lock()

            def complete(self, request: LLMRequest) -> LLMResponse:
                with self.lock:
                    self.calls += 1
                hold.wait(timeout=5)
                return _response()

        client = SlowClient()
        invoker = GuardedModelInvoker(client, guard)
        first = threading.Thread(
            target=invoker.invoke,
            args=(_request(),),
            kwargs={"call_type": "worker"},
        )
        first.start()
        time.sleep(0.2)
        with pytest.raises(SpecFlowError, match="Parallel provider limit exceeded"):
            invoker.invoke(_request(), call_type="worker")
        hold.set()
        first.join(timeout=10)
        assert client.calls == 1
        assert guard.snapshot()["provider_calls"]["active"] == 0

    def test_provider_exception_restores_active(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(
            ScriptedClient(failures=99, failure_error=RuntimeError("boom")),
            guard,
            max_provider_retries=0,
        )
        with pytest.raises(RuntimeError, match="boom"):
            invoker.invoke(_request(), call_type="worker")
        assert guard.snapshot()["provider_calls"]["active"] == 0

    def test_active_count_never_negative(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(ScriptedClient(), guard)
        invoker.invoke(_request(), call_type="worker")
        guard.release_provider_attempt(
            ProviderAttempt(
                attempt_index=999,
                call_type="worker",
                agent_id=None,
                revision_id=None,
                started_monotonic=0.0,
            ),
            success=True,
            input_tokens=1,
            output_tokens=1,
        )
        assert guard.snapshot()["provider_calls"]["active"] == 0

    def test_runs_are_isolated(self) -> None:
        first = _guard()
        second = _guard()
        GuardedModelInvoker(ScriptedClient(), first).invoke(_request(), call_type="worker")
        assert first.snapshot()["provider_calls"]["attempts"] == 1
        assert second.snapshot()["provider_calls"]["attempts"] == 0

    def test_thread_race_never_exceeds_attempt_budget(self) -> None:
        guard = _guard(max_attempts=5, max_parallel=10)
        invoker = GuardedModelInvoker(ScriptedClient(), guard)
        errors: list[Exception] = []
        lock = threading.Lock()

        def run() -> None:
            try:
                invoker.invoke(_request(), call_type="worker")
            except SpecFlowError as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        snapshot = guard.snapshot()
        assert snapshot["provider_calls"]["attempts"] <= 5
        assert len(errors) >= 15


class TestFailureArtifacts:
    def test_budget_failure_produces_snapshot_with_active_restored(self) -> None:
        guard = _guard(max_attempts=1)
        invoker = GuardedModelInvoker(ScriptedClient(), guard)
        invoker.invoke(_request(), call_type="worker")
        with pytest.raises(SpecFlowError, match="Provider call budget exceeded"):
            invoker.invoke(_request(), call_type="worker")
        last = guard.last_budget_snapshot
        assert last is not None
        assert last["provider_calls"]["attempts"] == 1
        assert last["provider_calls"]["active"] == 0
        assert last["limits"]["max_provider_call_attempts"] == 1

    def test_model_call_events_never_contain_prompt_or_secret(self) -> None:
        guard = _guard()
        invoker = GuardedModelInvoker(ScriptedClient(), guard)
        request = LLMRequest(
            model="m",
            messages=[
                LLMMessage(role="user", content="PROMPT_SECRET_MARKER_9f2c"),
            ],
        )
        invoker.invoke(request, call_type="worker")
        serialized = json.dumps(guard.model_call_events())
        assert "PROMPT_SECRET_MARKER_9f2c" not in serialized
        assert "api_key" not in serialized


class TestStaticGate:
    def test_no_direct_provider_complete_outside_allowlist(self) -> None:
        """Production modules must not call ``.complete(...)`` on LLM clients."""
        root = Path(__file__).resolve().parents[1] / "src" / "specflow"
        allowlist = {
            "invoker.py",
            "trace/recorder.py",  # legacy trace recorder (baseline)
            "runner.py",  # legacy 3-worker baseline (frozen for Phase 6 A/B)
        }
        violations: list[str] = []
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if relative.startswith("llm/"):
                continue  # provider/client/mock definitions
            if relative.startswith("workers/"):
                continue  # legacy 3-worker baseline (frozen for Phase 6 A/B)
            if relative in allowlist:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "complete":
                        violations.append(f"{relative}:{node.lineno}")
        assert violations == [], f"Direct provider calls outside allowlist: {violations}"
