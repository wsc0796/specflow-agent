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


class _OneRevisionClient(ScriptedExecutionClient):
    def __init__(self) -> None:
        super().__init__()
        self.review_count = 0
        self.finding_id = "F-c25e59bf"

    def complete(self, request):
        message = request.messages[-1].content
        if "[Task Brief Enrichment Input]" in message:
            return super().complete(request)
        if "[Finding Resolution Contract]" in message:
            self.requests.append(request)
            payload = {
                "revised_output": {"summary": "revised design"},
                "resolutions": [
                    {
                        "finding_id": self.finding_id,
                        "status": "resolved",
                        "explanation": "Added the missing design detail.",
                    }
                ],
            }
        elif "agent/review/v1/output" in message:
            self.requests.append(request)
            self.review_count += 1
            payload = (
                {
                    "decision": "REJECT",
                    "summary": "Design detail is missing.",
                    "requires_revision": True,
                    "findings": [
                        {
                            "finding_id": self.finding_id,
                            "severity": "warning",
                            "category": "completeness",
                            "description": "Design detail is missing.",
                            "target_agent_id": "design-agent-v1",
                            "affected_artifact": None,
                            "evidence_refs": [],
                            "recommendation": "Add the missing design detail.",
                        }
                    ],
                }
                if self.review_count == 1
                else {
                    "decision": "PASS",
                    "summary": "Revision resolves the finding.",
                    "requires_revision": False,
                    "findings": [],
                }
            )
        else:
            return super().complete(request)

        class Response:
            content = json.dumps(payload)

        return Response()


def test_default_provider_attempt_budget_is_24() -> None:
    policy = ExecutionPolicy()
    assert policy.max_provider_call_attempts == 24
    assert policy.max_llm_calls == 24
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


def test_explicit_legacy_default_conflicting_with_new_field_is_rejected() -> None:
    with pytest.raises(ValueError, match="conflicts"):
        ExecutionPolicy(max_llm_calls=10, max_provider_call_attempts=48)


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
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["token_usage_known"] is False
    assert metrics["input_tokens"] is None
    assert metrics["output_tokens"] is None
    assert metrics["total_tokens"] is None


def test_single_target_revision_live_request_path_uses_15_attempts(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# searchable repository evidence", encoding="utf-8")
    output = tmp_path / "out"
    client = _OneRevisionClient()

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
    manifest = json.loads(
        (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
    )
    snapshot = manifest["budget_snapshot"]
    assert snapshot["provider_calls"]["attempts"] == 15
    assert snapshot["provider_calls"]["successful"] == 15
    assert snapshot["revision"]["rounds"] == 1
    assert snapshot["revision"]["agent_invocations"] == 1
    assert manifest["workflow_state"] == "completed"
