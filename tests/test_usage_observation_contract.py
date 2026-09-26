"""Versioned all-request accounting coexists with historical subtotal reports."""

import json
from hashlib import sha256

import pytest
from test_multi_agent_request_budget import FakeProvider

from specflow import runner_multi
from specflow.evaluation.dev_baseline import inspect_attempt, summarize_attempts
from specflow.policy import ExecutionPolicy


@pytest.fixture(params=["mock", "fake"])
def measured_run(tmp_path, monkeypatch, request):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# health\n", encoding="utf-8")
    output = tmp_path / "out"
    records = []
    monkeypatch.setattr(runner_multi, "_create_real_llm_client", lambda *a, **k: FakeProvider())
    assert (
        runner_multi.run_multi_agent(
            repo=repo,
            requirement="health",
            output=output,
            mock=request.param == "mock",
            provider="mock" if request.param == "mock" else "openai-compatible",
            policy=ExecutionPolicy(max_llm_calls=12),
            request_observer=lambda o: records.append({"receiver": o.receiver}),
        )
        == 0
    )
    (output / "observation-status.json").write_text(
        json.dumps({"status": "complete", "observed_call_count": len(records)}), encoding="utf-8"
    )
    (output / "llm-requests.json").write_text(json.dumps(records), encoding="utf-8")
    return repo, output, next(output.glob("run-multi-*")), len(records)


def inspect(measured_run):
    repo, output, _, _ = measured_run
    result = inspect_attempt(output, repo, mode="multi-agent")
    result["case_id"] = "synthetic"
    return result


def rewrite_manifest(run, manifest):
    path = run / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    integrity_path = run / "artifact-integrity.json"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    integrity["artifact_hashes"]["manifest.json"] = sha256(path.read_bytes()).hexdigest()
    integrity_path.write_text(json.dumps(integrity), encoding="utf-8")


def test_new_usage_covers_coordinator_and_agents(measured_run):
    _, _, run, calls = measured_run
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["usage_contract"] == "all_provider_requests_v1"
    result = inspect(measured_run)
    usage = result["usage_observation"]
    assert usage["scope"] == "all_provider_requests_v1"
    assert usage["metered_provider_request_count"] == calls
    assert usage["metered_enrichment_request_count"] == 6
    assert usage["metered_agent_request_count"] == calls - 6
    assert usage["unmetered_enrichment_request_count"] == 0
    assert usage["all_provider_usage_complete"] is True
    cost = summarize_attempts(["synthetic"], [result], mode="multi-agent")["token_cost"]
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    assert cost["full_total"] == metrics["total_tokens"]
    assert cost["telemetry_coverage"] == 1
    assert "omit" not in cost["reason"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("usage_complete", None),
        ("usage_complete", False),
        ("usage_complete", 1),
        ("llm_calls", True),
        ("llm_calls", -1),
        ("usage_observed_calls", 99),
        ("usage_unknown_calls", 1),
        ("observed_input_tokens", 999999),
        ("observed_output_tokens", "10"),
        ("scope", "unknown"),
    ],
)
def test_invalid_or_incomplete_usage_never_claims_completeness(measured_run, field, value):
    _, _, run, _ = measured_run
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    manifest["usage_contract"] = "all_provider_requests_v1"
    if value is None:
        manifest["budget_usage"].pop(field, None)
    else:
        manifest["budget_usage"][field] = value
    rewrite_manifest(run, manifest)
    result = inspect(measured_run)
    assert result["usage_observation"]["all_provider_usage_complete"] is False
    cost = summarize_attempts(["synthetic"], [result], mode="multi-agent")["token_cost"]
    assert cost["full_total"] == "unknown"


@pytest.mark.parametrize("contract", [None, "future_v99"])
def test_old_or_unknown_contract_stays_conservative(measured_run, contract):
    _, _, run, _ = measured_run
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if contract is None:
        manifest.pop("usage_contract", None)
    else:
        manifest["usage_contract"] = contract
    rewrite_manifest(run, manifest)
    usage = inspect(measured_run)["usage_observation"]
    assert usage["all_provider_usage_complete"] is False
    assert usage["scope"] != "all_provider_requests_v1"


def test_missing_request_observer_does_not_invent_agent_breakdown(measured_run):
    _, output, _, calls = measured_run
    (output / "llm-requests.json").unlink()
    usage = inspect(measured_run)["usage_observation"]
    assert usage["all_provider_usage_complete"] is True
    assert usage["metered_provider_request_count"] == calls
    assert usage["metered_agent_request_count"] == "unknown"
