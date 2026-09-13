"""Synthetic offline regressions; these are NOT historical live-run artifacts."""

import copy
import json
from pathlib import Path

import pytest

from specflow.cli import main
from specflow.llm.models import LLMResponse, LLMUsage
from specflow.runner_multi import _build_registry, run_multi_agent

PAYLOADS = json.loads(
    (Path(__file__).parent / "fixtures/required-output-validity.json").read_text(encoding="utf-8")
)
ROLES = tuple(PAYLOADS)
IDENTITIES = {identity.role.value: identity for identity in _build_registry().list_agents()}


class RecordingProvider:
    def __init__(self, role=None, content=None, *, plan_degraded=False, reject=False):
        self.role = role
        self.content = content
        self.plan_degraded = plan_degraded
        self.reject = reject
        self.calls = []
        self.requests = []

    def complete(self, request):
        message = request.messages[-1].content
        if message.startswith("Generate a task brief"):
            if self.plan_degraded:
                raise RuntimeError("synthetic planning failure")
            content = json.dumps({"task_description": "Inspect the fixture request."})
        else:
            role = next(role for role in ROLES if f"**{role}**" in message)
            self.calls.append(role)
            self.requests.append(request)
            payload = copy.deepcopy(PAYLOADS[role])
            if self.reject and role == "review":
                payload.update(decision="REJECT", target_agent_id="design-agent-v1")
            content = json.dumps(payload)
            if role == self.role:
                if isinstance(self.content, Exception):
                    raise self.content
                content = self.content
        return LLMResponse(
            content=content,
            model="offline-recording-provider",
            usage=LLMUsage(input_tokens=10, output_tokens=10),
            latency_ms=0,
            finish_reason="stop",
        )


def fixture_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def health():\n    return {'status': 'ok'}\n")
    return repo


def run_cli(tmp_path, monkeypatch, provider):
    # T-070 validates the effective provider configuration before ownership.
    # Supply explicit offline configuration; the transport guard remains active.
    monkeypatch.setenv("SPECFLOW_LLM_BASE_URL", "https://offline.invalid/v1")
    monkeypatch.setenv("SPECFLOW_LLM_API_KEY", "test-offline-recording-provider")
    monkeypatch.setenv("SPECFLOW_LLM_MODEL", "offline-recording-provider")
    monkeypatch.setenv("SPECFLOW_LLM_TIMEOUT_SECONDS", "30")
    monkeypatch.setattr("specflow.runner_multi._create_real_llm_client", lambda *a, **k: provider)
    with pytest.raises(SystemExit) as outcome:
        main(
            [
                "run",
                "--mode",
                "multi-agent",
                "--provider",
                "openai-compatible",
                "--model",
                "offline-recording-provider",
                "--repo",
                str(fixture_repo(tmp_path)),
                "--requirement",
                "Add a status route",
                "--output",
                str(tmp_path / "out"),
            ]
        )
    run_dir = next((tmp_path / "out").iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    return outcome.value.code, run_dir, manifest


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("fault", ["empty", "missing-summary", "blank-summary"])
def test_real_runner_rejects_invalid_required_payload(tmp_path, monkeypatch, role, fault):
    payload = copy.deepcopy(PAYLOADS[role])
    if fault == "empty":
        payload = {}
    elif fault == "missing-summary":
        del payload["summary"]
    else:
        payload["summary"] = " \t\n "
    provider = RecordingProvider(role, json.dumps(payload))
    code, run_dir, manifest = run_cli(tmp_path, monkeypatch, provider)
    assert role in provider.calls  # the actual AgentRunner consumed this fake response
    assert code == 3
    assert manifest["workflow_state"] == "failed"
    assert manifest["error"] == "MULTI_AGENT_RUN_FAILED"
    assert not (run_dir / "metrics.json").exists()  # no successful/PASS metrics
    if role != "review":
        assert "review" not in provider.calls  # fake PASS must never be requested
    if role == "repository_analyst":
        assert provider.calls == [role]
    if role in {"design", "test_strategy", "risk_review"}:
        assert "synthesis" not in provider.calls


@pytest.mark.parametrize("role", ["design", "test_strategy", "synthesis"])
def test_title_only_output_is_not_a_deliverable(tmp_path, monkeypatch, role):
    provider = RecordingProvider(role, json.dumps({"summary": "Title only"}))
    code, _, manifest = run_cli(tmp_path, monkeypatch, provider)
    assert code == 3
    assert manifest["workflow_state"] == "failed"
    assert "review" not in provider.calls


@pytest.mark.parametrize(
    "role,field,value",
    [
        ("design", "implementation_steps", ["  "]),
        ("test_strategy", "test_scenarios", ["\t"]),
        ("synthesis", "consolidated_design", "\n"),
    ],
)
def test_blank_role_content_is_not_substance(tmp_path, monkeypatch, role, field, value):
    payload = copy.deepcopy(PAYLOADS[role])
    payload[field] = value
    code, _, _ = run_cli(tmp_path, monkeypatch, RecordingProvider(role, json.dumps(payload)))
    assert code == 3


@pytest.mark.parametrize(
    "flag,value",
    [
        ("success", False),
        ("schema_validated", False),
        ("invalid-output", True),
    ],
)
def test_stage_rejects_false_envelope_with_complete_output(tmp_path, flag, value):
    identity = IDENTITIES["repository_analyst"]
    called = []
    result = {
        "agent_id": identity.agent_id,
        "role": identity.role.value,
        "success": True,
        "schema_validated": True,
        "output": PAYLOADS["repository_analyst"],
    }
    if flag == "invalid-output":
        result["output"] = {}
    else:
        result[flag] = value
    code = run_multi_agent(
        repo=fixture_repo(tmp_path),
        requirement="Add a status route",
        output=tmp_path / "out",
        mock=True,
        _executor_overrides={
            identity.agent_id: lambda _: result,
            "review-agent-v1": lambda _: called.append("review"),
            "design-agent-v1": lambda _: called.append("design"),
        },
    )
    assert code == 3
    assert not called


@pytest.mark.parametrize("plan_degraded", [False, True])
def test_real_runner_valid_outputs_and_empty_findings_pass(tmp_path, monkeypatch, plan_degraded):
    provider = RecordingProvider(plan_degraded=plan_degraded)
    code, run_dir, manifest = run_cli(tmp_path, monkeypatch, provider)
    assert code == 0
    assert manifest["workflow_state"] == "completed"
    assert manifest["enriched"] is not plan_degraded
    assert bool(manifest["degraded_agents"]) is plan_degraded
    outputs = json.loads((run_dir / "agent-outputs.json").read_text())
    assert len(outputs) == 6
    assert all(r["success"] and r["schema_validated"] for r in outputs.values())
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert metrics["review_decision"] == "PASS"
    assert metrics["degraded_count"] == 0
    assert metrics["schema_validated_count"] == 6


def test_real_runner_business_reject_retains_completed_semantics(tmp_path, monkeypatch):
    provider = RecordingProvider(reject=True)
    code, run_dir, manifest = run_cli(tmp_path, monkeypatch, provider)
    assert code == 0  # execution completion is not business approval
    assert manifest["workflow_state"] == "completed"
    assert manifest["revision_exhausted"] is True
    assert provider.calls.count("review") == 2
    assert json.loads((run_dir / "metrics.json").read_text())["review_decision"] == "REJECT"


@pytest.mark.parametrize(
    "content",
    [
        "not-json: synthetic-private-response",
        "[]",
        '{"unknown":"synthetic-private-response"}',
        RuntimeError("synthetic-private-response"),
    ],
)
def test_provider_failure_never_leaks_raw_output(tmp_path, monkeypatch, caplog, content):
    code, run_dir, _ = run_cli(
        tmp_path, monkeypatch, RecordingProvider("repository_analyst", content)
    )
    assert code == 3
    assert "synthetic-private-response" not in caplog.text
    for artifact in run_dir.iterdir():
        assert "synthetic-private-response" not in artifact.read_text()


def test_provider_receives_authoritative_output_contract(tmp_path, monkeypatch):
    provider = RecordingProvider()
    run_cli(tmp_path, monkeypatch, provider)
    for role, request in zip(provider.calls, provider.requests, strict=True):
        from specflow.schema import build_schema_registry

        schema = build_schema_registry().get(IDENTITIES[role].output_schema_id).model_json_schema()
        assert (
            json.dumps(schema, ensure_ascii=False, sort_keys=True) in request.messages[-1].content
        )


def test_run_api_invalid_output_has_no_review_package(tmp_path, monkeypatch):
    from test_runs import client_for, register_project

    monkeypatch.setattr(
        "specflow.agents.repository_analyst.RepositoryAnalystAgent.execute",
        lambda self, context: {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "success": True,
            "output": {},
        },
    )
    repo = fixture_repo(tmp_path)
    with client_for(tmp_path) as client:
        project_id = register_project(client, repo)
        response = client.post(
            "/api/v1/runs",
            json={
                "project_id": project_id,
                "requirement": "Add a status route",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "failed_runtime"
        assert body["error_code"] == "MULTI_AGENT_RUN_FAILED"
        assert client.get(f"/api/v1/runs/{body['id']}/review-package").status_code == 409


def test_explicit_noop_with_rationale_and_check_remains_valid(tmp_path, monkeypatch):
    payload = {
        "summary": "No change: the status route already meets this request.",
        "implementation_steps": [
            "Confirm the existing GET /status returns 200 and status=ok; retain the implementation."
        ],
    }
    code, _, manifest = run_cli(
        tmp_path, monkeypatch, RecordingProvider("design", json.dumps(payload))
    )
    assert code == 0
    assert manifest["workflow_state"] == "completed"


def test_valid_output_with_allowed_degradation_is_not_rejected(tmp_path):
    identity = IDENTITIES["repository_analyst"]
    result = {
        "agent_id": identity.agent_id,
        "role": identity.role.value,
        "success": True,
        "degraded": True,
        "output": PAYLOADS["repository_analyst"],
    }
    code = run_multi_agent(
        repo=fixture_repo(tmp_path),
        requirement="Add a status route",
        output=tmp_path / "out",
        mock=True,
        _executor_overrides={identity.agent_id: lambda _: result},
    )
    assert code == 0
    metrics = json.loads(next((tmp_path / "out").glob("*/metrics.json")).read_text())
    assert metrics["degraded_count"] == 1
    assert metrics["review_decision"] == "PASS"
