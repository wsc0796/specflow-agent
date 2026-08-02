"""Budget calibration tests: default 24, alias mapping, boundary enforcement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_cli_multi_agent import ScriptedExecutionClient

from specflow.llm.models import LLMMessage, LLMRequest, LLMResponse, LLMUsage
from specflow.policy.defaults import DEFAULT_POLICY
from specflow.policy.models import ExecutionPolicy, SpecFlowError
from specflow.policy.runtime_guard import RuntimeGuard
from specflow.runner_multi import run_multi_agent


def _request() -> LLMRequest:
    return LLMRequest(model="m", messages=[LLMMessage(role="user", content="hi")])


class _OkClient:
    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content='{"ok": true}',
            model="m",
            latency_ms=1,
            finish_reason="stop",
            usage=LLMUsage(input_tokens=1, output_tokens=1),
        )


def test_default_provider_attempt_budget_is_24() -> None:
    policy = ExecutionPolicy()
    assert policy.max_provider_call_attempts == 24
    assert DEFAULT_POLICY.max_provider_call_attempts == 24


def test_explicit_override_replaces_default() -> None:
    assert ExecutionPolicy(max_provider_call_attempts=48).max_provider_call_attempts == 48


def test_max_llm_calls_alias_maps_to_provider_attempts() -> None:
    policy = ExecutionPolicy(max_llm_calls=5)
    assert policy.max_provider_call_attempts == 5
    assert policy.max_llm_calls == 5


def test_conflicting_new_and_old_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="conflicts"):
        ExecutionPolicy(max_llm_calls=5, max_provider_call_attempts=48)


def test_24th_attempt_allowed_25th_fail_closed() -> None:
    guard = RuntimeGuard(
        ExecutionPolicy(
            max_provider_call_attempts=24,
            max_parallel_provider_calls=100,
        )
    )
    guard.set_run_context("run-test", execution_mode="live")
    for _ in range(24):
        reservation = guard.reserve_provider_attempt(call_type="worker")
        guard.release_provider_attempt(reservation, success=True, input_tokens=1, output_tokens=1)
    snapshot = guard.snapshot()
    assert snapshot["provider_calls"]["attempts"] == 24
    assert snapshot["provider_calls"]["active"] == 0
    with pytest.raises(SpecFlowError, match="Provider call budget exceeded"):
        guard.reserve_provider_attempt(call_type="worker")
    assert guard.snapshot()["provider_calls"]["attempts"] == 24


def test_snapshot_records_effective_limit() -> None:
    guard = RuntimeGuard(ExecutionPolicy())
    guard.set_run_context("run-test", execution_mode="live")
    assert guard.snapshot()["limits"]["max_provider_call_attempts"] == 24
    guard = RuntimeGuard(ExecutionPolicy(max_provider_call_attempts=48))
    guard.set_run_context("run-test", execution_mode="live")
    assert guard.snapshot()["limits"]["max_provider_call_attempts"] == 48


def test_normal_live_path_fits_default_budget(tmp_path: Path) -> None:
    """The 12-attempt normal live path must run under the default budget of 24."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# searchable repository evidence", encoding="utf-8")
    output = tmp_path / "out"
    client = ScriptedExecutionClient()

    assert (
        run_multi_agent(
            repo=repo,
            requirement="Inspect searchable repository evidence",
            output=output,
            provider="openai-compatible",
            _llm_client_override=client,
        )
        == 0
    )
    run_dir = next(output.glob("run-multi-*"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    snapshot = manifest["budget_snapshot"]
    assert snapshot["limits"]["max_provider_call_attempts"] == 24
    assert snapshot["provider_calls"]["attempts"] == 12
    assert snapshot["provider_calls"]["successful"] == 12
