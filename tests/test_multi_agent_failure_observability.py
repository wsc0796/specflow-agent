"""Rejected stages leave bounded audit evidence without becoming accepted outputs."""

import json
from copy import deepcopy
from hashlib import sha256

import pytest

from specflow import runner_multi
from specflow.agents.adapter import AgentRunner
from specflow.llm.models import LLMResponse, LLMUsage
from specflow.policy import ExecutionPolicy, RuntimeGuard
from specflow.policy.models import ArtifactPolicy
from specflow.schema import build_schema_registry

ANALYST = "repository-analyst-agent-v1"
DESIGN = "design-agent-v1"
SPECIALISTS = (DESIGN, "test-strategy-agent-v1", "risk-review-agent-v1")
REQUIREMENT = "Explain failure observability"
PRIVATE_MARKER = "UNVALIDATED_PRIVATE_BODY_" + "z" * 100_000
SECRET_MARKER = "synthetic-private-credential"
PATH_MARKER = "C:\\private-synthetic\\untrusted.txt"


def _failure(agent_id=ANALYST, code="SCHEMA_VALIDATION_FAILED"):
    return {
        "agent_id": agent_id,
        "role": "untrusted-role",
        "success": False,
        "schema_validated": False,
        "output": {"degraded": True, "error_code": code},
    }


def _run(tmp_path, overrides, *, policy=ExecutionPolicy()):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(f"# {REQUIREMENT}\n", encoding="utf-8")
    output = tmp_path / "artifacts"
    code = runner_multi.run_multi_agent(
        repo=repo,
        requirement=REQUIREMENT,
        output=output,
        mock=True,
        policy=policy,
        _executor_overrides=overrides,
    )
    assert code == 3
    return next(output.glob("run-multi-*"))


def _read(run_dir, filename):
    return json.loads((run_dir / filename).read_text(encoding="utf-8"))


def _assert_audit(
    run_dir,
    *,
    agent=ANALYST,
    stage=0,
    code="SCHEMA_VALIDATION_FAILED",
    source="executor_reported",
    role="repository_analyst",
):
    manifest = _read(run_dir, "manifest.json")
    assert manifest["workflow_state"] == "failed"
    assert manifest["error"] == "MULTI_AGENT_RUN_FAILED"
    assert manifest["stages_completed"] == stage
    assert manifest["failure_context"] == {
        "kind": "stage_result_validation",
        "agent_id": agent,
        "stage_index": str(stage),
        "error_code": code,
        "classification_source": source,
    }
    outputs = _read(run_dir, "agent-outputs.json")
    audit = outputs[f"stage-{stage}/{agent}"]
    assert audit == {
        "agent_id": agent,
        "role": role,
        "stage_index": stage,
        "success": False,
        "schema_validated": False,
        "degraded": True,
        "audit_only": True,
        "error_code": code,
        "classification_source": source,
    }
    assert len(json.dumps(audit)) < 512
    traces = _read(run_dir, "traces.json")
    root = next(s for s in traces if s.get("kind") == "run")
    coordinator = next(s for s in traces if s.get("kind") == "coordinator")
    failed = [s for s in traces if s.get("agent_id") == agent and s["stage"] == stage]
    assert len(failed) == 1
    span = failed[0]
    assert span["status"] == "failed"
    assert span["run_id"] == manifest["run_id"] == coordinator["run_id"] == root["run_id"]
    assert span["parent_span_id"] == coordinator["span_id"]
    assert coordinator["parent_span_id"] == root["span_id"]
    assert span["agent_role"] == role
    assert span["metadata"]["error_code"] == code
    assert span["metadata"]["classification_source"] == source
    assert not {"input_tokens", "output_tokens", "usage", "latency_ms"} & span.keys()
    assert (run_dir / "_COMPLETE").is_file()
    hashes = _read(run_dir, "artifact-integrity.json")["artifact_hashes"]
    for name in ("manifest.json", "agent-outputs.json", "traces.json"):
        assert sha256((run_dir / name).read_bytes()).hexdigest() == hashes[name]
    return span


def test_required_failure_artifacts_agree_without_running_specialists(tmp_path):
    calls = []

    def analyst(context):
        calls.append(ANALYST)
        assert context["prior_outputs"] == {}
        return _failure()

    def forbidden(context):
        calls.append("forbidden-specialist")
        raise AssertionError("Specialist must not run")

    run_dir = _run(tmp_path, {ANALYST: analyst, **dict.fromkeys(SPECIALISTS, forbidden)})
    assert calls == [ANALYST]
    span = _assert_audit(run_dir)
    assert set(_read(run_dir, "agent-outputs.json")) == {f"stage-0/{ANALYST}"}
    assert span["stage_started_at"] <= span["agent_submitted_at"]
    assert span["agent_submitted_at"] <= span["agent_completed_at"]
    assert span["agent_completed_at"] <= span["stage_completed_at"]


@pytest.mark.parametrize(
    ("content", "code"),
    [("not-json", "JSON_PARSE_FAILED"), ('{"unexpected":true}', "SCHEMA_VALIDATION_FAILED")],
)
def test_real_adapter_failure_classification_survives_stage_gate(tmp_path, content, code):
    class FakeLLMClient:
        def __init__(self):
            self.requests = []

        def complete(self, request):
            self.requests.append(request)
            return LLMResponse(
                content=content,
                model="fake",
                usage=LLMUsage(input_tokens=10, output_tokens=5),
                latency_ms=1,
                finish_reason="stop",
            )

    client = FakeLLMClient()
    adapter = AgentRunner(
        runner_multi._build_registry().get(ANALYST).identity,
        client,
        schema_registry=build_schema_registry(),
    )
    run_dir = _run(tmp_path, {ANALYST: adapter.execute})
    assert len(client.requests) == 1
    _assert_audit(run_dir, code=code)


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        (
            {
                "success": True,
                "output": {"summary": {"private": SECRET_MARKER, "body": PRIVATE_MARKER}},
            },
            "SCHEMA_VALIDATION_FAILED",
        ),
        ({"success": True, "output": ["unvalidated"]}, "AGENT_OUTPUT_NOT_OBJECT"),
        ({"agent_id": "spoofed-agent", "success": True}, "AGENT_EXECUTION_FAILED"),
        ({"agent_id": "spoofed-agent"}, "AGENT_EXECUTION_FAILED"),
    ],
)
def test_local_validation_overrides_untrusted_identity_and_status(tmp_path, caplog, changes, code):
    payload = {**_failure(), **changes}
    run_dir = _run(tmp_path, {ANALYST: lambda context: payload})
    _assert_audit(run_dir, code=code, source="stage_validator")
    assert "spoofed-agent" not in (run_dir / "traces.json").read_text(encoding="utf-8")
    for marker in (SECRET_MARKER, PRIVATE_MARKER[:25]):
        assert marker not in caplog.text
        assert all(marker not in p.read_text(encoding="utf-8") for p in run_dir.iterdir())


@pytest.mark.parametrize("reported_code", [None, "unknown-private-error", [], {}, 17])
def test_untrusted_failure_fields_are_bounded_and_never_persisted(tmp_path, caplog, reported_code):
    payload = _failure(code=reported_code)
    if reported_code is None:
        del payload["output"]["error_code"]
    payload["output"].update({"body": PRIVATE_MARKER, "api_key": SECRET_MARKER})
    payload.update({"message": PATH_MARKER, "model": SECRET_MARKER, "role": SECRET_MARKER})
    run_dir = _run(tmp_path, {ANALYST: lambda context: payload})
    _assert_audit(run_dir, code="AGENT_EXECUTION_FAILED")
    serialized = "\n".join(p.read_text(encoding="utf-8") for p in run_dir.iterdir())
    for marker in (PRIVATE_MARKER[:25], SECRET_MARKER, PATH_MARKER, "unknown-private-error"):
        assert marker not in serialized
        assert marker not in caplog.text
    assert sum(p.stat().st_size for p in run_dir.iterdir()) < 12_000


@pytest.mark.parametrize(
    "code", ["PROVIDER_TIMEOUT", "SCHEMA_REGISTRY_UNAVAILABLE", "SCHEMA_NOT_FOUND"]
)
def test_known_executor_codes_remain_classified_without_retries(tmp_path, code):
    calls = []

    def failure(context):
        calls.append(True)
        return _failure(code=code)

    _assert_audit(_run(tmp_path, {ANALYST: failure}), code=code)
    assert len(calls) == 1


def test_later_rejected_stage_preserves_only_previously_accepted_outputs(tmp_path):
    registry = runner_multi._build_registry()
    downstream = []
    contexts = []

    def specialist(agent):
        def execute(context):
            contexts.append(deepcopy(context))
            if agent == DESIGN:
                return _failure(DESIGN, "JSON_PARSE_FAILED")
            return registry.get(agent).execute(context)

        return execute

    def forbidden(context):
        downstream.append(True)
        raise AssertionError("No Synthesis or Review after rejected stage")

    run_dir = _run(
        tmp_path,
        {
            **{agent: specialist(agent) for agent in SPECIALISTS},
            "synthesis-agent-v1": forbidden,
            "review-agent-v1": forbidden,
        },
    )
    assert downstream == []
    assert len(contexts) == 3
    assert all(set(c["prior_outputs"]) == {ANALYST} for c in contexts)
    assert all("audit_only" not in json.dumps(c) for c in contexts)
    _assert_audit(run_dir, agent=DESIGN, stage=1, code="JSON_PARSE_FAILED", role="design")
    outputs = _read(run_dir, "agent-outputs.json")
    assert set(outputs) == {f"stage-0/{ANALYST}", f"stage-1/{DESIGN}"}
    assert outputs[f"stage-0/{ANALYST}"]["schema_validated"] is True
    # The existing deterministic executor omits success (accepted by the gate).
    # Preserve its envelope rather than inventing a field in accepted outputs.
    assert "success" not in outputs[f"stage-0/{ANALYST}"]
    assert outputs[f"stage-0/{ANALYST}"]["output"]["summary"] == (
        "Deterministic mock repository analysis."
    )


def test_rejected_stage_does_not_mutate_accepted_state(tmp_path):
    from specflow.coordinator.scheduler import MultiAgentScheduler

    prior = {}
    accepted = []
    with pytest.raises(ValueError):
        runner_multi._run_and_accumulate(
            accepted,
            MultiAgentScheduler(),
            (ANALYST,),
            0,
            {ANALYST: lambda context: _failure()},
            {"requirement": REQUIREMENT, "repository_evidence": "synthetic evidence"},
            prior,
            runner_multi._build_registry(),
            build_schema_registry(),
            RuntimeGuard(ExecutionPolicy()),
        )
    assert prior == {}
    assert accepted == []


def test_missing_scheduler_timing_is_unknown_in_failure_trace(tmp_path, monkeypatch):
    original = runner_multi.MultiAgentScheduler.execute

    def without_timing(self, *args, **kwargs):
        stages = original(self, *args, **kwargs)
        for stage in stages:
            stage.started_at = stage.completed_at = ""
            stage.agent_timings = {}
        return stages

    monkeypatch.setattr(runner_multi.MultiAgentScheduler, "execute", without_timing)
    span = _assert_audit(_run(tmp_path, {ANALYST: lambda context: _failure()}))
    for key in (
        "stage_started_at",
        "stage_completed_at",
        "agent_submitted_at",
        "agent_completed_at",
    ):
        assert span[key] is None


@pytest.mark.parametrize("failure", ["write", "size"])
def test_artifact_failure_never_marks_failed_run_complete(tmp_path, monkeypatch, failure):
    policy = ExecutionPolicy()
    if failure == "write":
        original = runner_multi._safe_write

        def fail_trace_write(run_dir, filename, data, guard, **kwargs):
            if filename == "traces.json":
                raise OSError("synthetic write failure")
            return original(run_dir, filename, data, guard, **kwargs)

        monkeypatch.setattr(runner_multi, "_safe_write", fail_trace_write)
    else:
        policy = ExecutionPolicy(artifacts=ArtifactPolicy(max_artifact_bytes=64))
    run_dir = _run(tmp_path, {ANALYST: lambda context: _failure()}, policy=policy)
    assert not (run_dir / "_COMPLETE").exists()
    assert not (run_dir / "artifact-integrity.json").exists()
    if failure == "write":
        manifest = _read(run_dir, "manifest.json")
        assert manifest["error"] == "MULTI_AGENT_RUN_FAILED"
        assert manifest["failure_context"]["error_code"] == "SCHEMA_VALIDATION_FAILED"
