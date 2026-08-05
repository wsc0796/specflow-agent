import json
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
import yaml

import specflow.evaluation.live_provider_v1 as live_eval
from specflow.evaluation.live_provider_v1 import (
    CONTROL_CLASS,
    QUALITY_CLASS,
    LiveEvalSuite,
    LiveEvalTask,
    LiveEvaluationError,
    PricingRule,
    RedactingResponseRecorder,
    build_live_report,
    load_live_suite,
    load_provider_config,
    render_live_report,
    run_live_suite,
)
from specflow.llm.models import LLMResponse, LLMUsage


def test_bearer_regex_ignores_technical_terms() -> None:
    """Plain prose like "Bearer prefix" is not a credential and must not fail
    the attempt secret scan."""
    assert live_eval._BEARER_RE.search("Use the Bearer prefix for authentication") is None
    assert live_eval._BEARER_RE.search("Authorization: Bearer sk-abcdefghijklmnop123") is not None


class FakeLiveClient:
    """Provider-shaped test client that records sanitized response metadata."""

    def __init__(self, recorder: RedactingResponseRecorder) -> None:
        self._recorder = recorder
        self.calls = 0

    def complete(self, request: object) -> LLMResponse:
        self.calls += 1
        system_prompt = request.messages[0].content
        payload = _payload_for_role(system_prompt)
        self._recorder.observe(
            {
                "id": f"fake-{self.calls}",
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "provider_metadata": {
                    "authorization": "Bearer test-live-secret",
                    "local_path": r"C:\\Users\\example\\private.txt",
                    "unlabeled_key": "sk-abcdefghijklmnop",
                    "embedded_json": json.dumps(
                        {
                            "api_key": "AKIAIOSFODNN7EXAMPLE",
                            "client_secret": "plain-example-value",
                        }
                    ),
                    "prose_json": ('Provider text: {"client_secret":"markdown-wrapped-secret"}'),
                },
            }
        )
        return LLMResponse(
            content=json.dumps(payload),
            model="test-live-model",
            usage=LLMUsage(input_tokens=10, output_tokens=5),
            latency_ms=1,
            finish_reason="stop",
        )


class FailingLiveClient:
    """Test double that models a Provider timeout before a response is available."""

    def complete(self, request: object) -> LLMResponse:
        del request
        raise RuntimeError("Provider timeout")


def _payload_for_role(system_prompt: str) -> dict[str, Any]:
    if "repository_analyst" in system_prompt:
        return {
            "summary": "Repository entrypoint is app/main.py.",
            "affected_components": ["app/main.py"],
            "key_files": ["app/main.py"],
            "technology_notes": "FastAPI",
            "evidence_count": 1,
        }
    if "test_strategy" in system_prompt:
        return {
            "summary": "Exercise the protected endpoint.",
            "test_scenarios": ["Test app/main.py registration."],
            "edge_cases": [],
            "regression_concerns": [],
            "coverage_gaps": [],
            "evidence_refs": ["app/main.py"],
        }
    if "risk_review" in system_prompt:
        return {
            "summary": "Keep the route boundary explicit.",
            "risks": ["Review app/main.py route ordering."],
            "severity": "low",
            "migration_concerns": [],
            "rollback_plan": "Revert the route registration.",
            "evidence_refs": ["app/main.py"],
        }
    if "design" in system_prompt:
        return {
            "summary": "Add a router at the application boundary.",
            "architecture_changes": [],
            "implementation_steps": [],
            "api_changes": [],
            "data_model_changes": [],
            "dependencies": [],
            "evidence_refs": ["app/main.py"],
        }
    if "synthesis" in system_prompt:
        return {
            "summary": "Synthesize evidence from app/main.py.",
            "consolidated_design": "Use app/main.py registration.",
            "consolidated_risks": [],
            "consolidated_tests": ["Test app/main.py."],
            "conflicts_resolved": [],
            "open_questions": [],
        }
    if "review" in system_prompt:
        return {
            "decision": "PASS",
            "summary": "Evidence is sufficient.",
            "findings": [],
            "severity": "info",
            "requires_revision": False,
            "target_agent_id": "",
        }
    raise AssertionError(f"unexpected system prompt: {system_prompt}")


def _make_target_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "target"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "SpecFlow Tests")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _write_task(path: Path, *, task_id: str, commit: str, control: bool = False) -> LiveEvalTask:
    raw: dict[str, object] = {
        "task_id": task_id,
        "repository": "tests/example",
        "repository_commit": commit,
        "user_request": "Locate app/main.py using source evidence.",
        "expected_files": ["app/main.py"],
        "required_evidence": ["app/main.py"],
        "required_output_fields": []
        if control
        else [
            "stage-0/repository-analyst-agent-v1.output.summary",
            "stage-3/review-agent-v1.output.decision",
        ],
        "forbidden_assumptions": ["The application uses a hidden router."],
        "timeout_seconds": 120,
        "human_notes": "Review evidence grounding.",
    }
    if control:
        raw["evaluation_class"] = CONTROL_CLASS
        raw["max_llm_calls"] = 1
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return LiveEvalTask(
        task_id=task_id,
        repository="tests/example",
        repository_commit=commit,
        user_request=str(raw["user_request"]),
        expected_files=("app/main.py",),
        required_evidence=("app/main.py",),
        required_output_fields=tuple(raw["required_output_fields"]),
        forbidden_assumptions=("The application uses a hidden router.",),
        timeout_seconds=120,
        human_notes="Review evidence grounding.",
        evaluation_class=CONTROL_CLASS if control else QUALITY_CLASS,
        max_llm_calls=1 if control else 10,
        source_path=path,
    )


def _config() -> object:
    return load_provider_config(
        environment={
            "SPECFLOW_LLM_BASE_URL": "https://provider.example/v1",
            "SPECFLOW_LLM_API_KEY": "test-live-secret",
            "SPECFLOW_LLM_MODEL": "test-live-model",
        }
    )


def _pricing() -> PricingRule:
    return PricingRule(
        provider="openai-compatible",
        model="test-live-model",
        input_usd_per_million_tokens=1.0,
        output_usd_per_million_tokens=2.0,
        source_url="https://provider.example/pricing",
        retrieved_at="2026-08-05",
    )


def _factory(config: object, recorder: RedactingResponseRecorder) -> FakeLiveClient:
    del config
    return FakeLiveClient(recorder)


def _failing_factory(config: object, recorder: RedactingResponseRecorder) -> FailingLiveClient:
    del config, recorder
    return FailingLiveClient()


def test_live_suite_rejects_tampered_frozen_task(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    controls = tmp_path / "controls"
    tasks.mkdir()
    controls.mkdir()
    for number in range(5):
        path = tasks / f"{number:02d}-task.yaml"
        path.write_text(_task_yaml(f"quality-task-{number}"), encoding="utf-8")
    control = controls / "budget.yaml"
    control.write_text(_task_yaml("budget-control", control=True), encoding="utf-8")
    lock = {
        "repository": "tests/example",
        "repository_commit": "abc123",
        "task_sha256": {path.name: _sha(path) for path in sorted(tasks.glob("*.yaml"))},
        "control_sha256": {control.name: _sha(control)},
    }
    lock_path = tmp_path / "suite-lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")

    suite = load_live_suite(tasks_dir=tasks, controls_dir=controls, lock_path=lock_path)
    assert len(suite.quality_tasks) == 5

    first = next(tasks.glob("*.yaml"))
    first.write_text(first.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    with pytest.raises(LiveEvaluationError, match="modified"):
        load_live_suite(tasks_dir=tasks, controls_dir=controls, lock_path=lock_path)


def test_missing_provider_configuration_is_blocked_before_client_creation() -> None:
    with pytest.raises(LiveEvaluationError, match="configuration"):
        load_provider_config(environment={})


def test_live_suite_writes_redacted_evidence_and_budget_control(tmp_path: Path) -> None:
    repository, commit = _make_target_repo(tmp_path)
    quality = _write_task(tmp_path / "quality.yaml", task_id="quality-task", commit=commit)
    control = _write_task(
        tmp_path / "control.yaml",
        task_id="budget-control",
        commit=commit,
        control=True,
    )
    suite = LiveEvalSuite(
        quality_tasks=(quality,),
        control_tasks=(control,),
        repository="tests/example",
        repository_commit=commit,
        suite_lock_sha256="a" * 64,
    )
    runs_root = tmp_path / "runs"

    results = run_live_suite(
        suite=suite,
        repository_root=repository,
        runs_root=runs_root,
        config=_config(),
        pricing=_pricing(),
        _client_factory=_factory,
    )

    assert [result["deterministic_status"] for result in results] == ["passed", "passed"]
    quality_result, control_result = results
    assert quality_result["run_completed"] is True
    assert quality_result["schema_passed"] is True
    assert quality_result["artifact_integrity_passed"] is True
    assert quality_result["required_evidence_cited"] == ["app/main.py"]
    assert quality_result["required_evidence_collected"] == ["app/main.py"]
    assert quality_result["required_evidence_hash_verified"] == ["app/main.py"]
    assert quality_result["required_evidence_covered"] == ["app/main.py"]
    assert control_result["failure_category"] == "budget_call_limit"

    attempt_dir = runs_root / str(quality_result["attempt_directory"])
    raw = json.loads((attempt_dir / "raw_provider_response.json").read_text(encoding="utf-8"))
    assert raw["redacted"] is True
    assert raw["responses"][0]["body"]["usage"]["prompt_tokens"] == 10
    contents = "\n".join(
        path.read_text(encoding="utf-8")
        for path in attempt_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    assert "test-live-secret" not in contents
    assert "sk-abcdefghijklmnop" not in contents
    assert "AKIAIOSFODNN7EXAMPLE" not in contents
    assert "plain-example-value" not in contents
    assert "markdown-wrapped-secret" not in contents
    assert r"C:\\Users\\example" not in contents
    assert "<redacted>" in contents
    assert (attempt_dir / "tool_calls.jsonl").is_file()
    assert (attempt_dir / "trace.jsonl").is_file()
    assert (attempt_dir / "human-review.yaml").is_file()

    with pytest.raises(LiveEvaluationError, match="test-double"):
        build_live_report(runs_root, batch_id=str(quality_result["batch_id"]))
    report = build_live_report(
        runs_root,
        batch_id=str(quality_result["batch_id"]),
        _allow_test_provenance=True,
    )
    assert report["quality_task_count"] == 1
    assert report["control_count"] == 1
    assert report["metrics"]["completion_rate"] == 1.0
    assert report["metrics"]["total_estimated_cost_usd"] is not None
    assert report["metrics"]["total_estimated_cost_usd"] == round(
        sum(float(result["estimated_cost_usd"]) for result in results), 8
    )
    assert "Mock benchmark results are excluded" in render_live_report(report)

    # A stale attempt outside the manifest must never change this batch's metrics.
    stale = runs_root / "stale-attempt"
    stale.mkdir()
    (stale / "deterministic-result.json").write_text("{}", encoding="utf-8")
    isolated = build_live_report(
        runs_root,
        batch_id=str(quality_result["batch_id"]),
        _allow_test_provenance=True,
    )
    assert isolated["attempt_count"] == 2

    # All static evidence files are batch-bound, not just the result summary.
    trace_path = attempt_dir / "trace.jsonl"
    original_trace = trace_path.read_text(encoding="utf-8")
    trace_path.write_text(f"{original_trace}{{}}\n", encoding="utf-8")
    with pytest.raises(LiveEvaluationError, match="evidence hash"):
        build_live_report(
            runs_root,
            batch_id=str(quality_result["batch_id"]),
            _allow_test_provenance=True,
        )
    trace_path.write_text(original_trace, encoding="utf-8")

    # A changed declared result is rejected rather than silently re-aggregated.
    result_path = attempt_dir / "deterministic-result.json"
    result_path.write_text("{}", encoding="utf-8")
    with pytest.raises(LiveEvaluationError, match="result hash"):
        build_live_report(
            runs_root,
            batch_id=str(quality_result["batch_id"]),
            _allow_test_provenance=True,
        )


def test_redacting_recorder_sanitizes_json_embedded_in_provider_strings() -> None:
    recorder = RedactingResponseRecorder(("configured-secret",))
    recorder.observe(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            'Provider text: {"api_key":"AKIAIOSFODNN7EXAMPLE",'
                            '"client_secret":"plain-example-value",'
                            '"nested":{"authorization":"Bearer configured-secret"}}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        }
    )

    rendered = json.dumps(recorder.as_dict(), ensure_ascii=False)
    assert "AKIAIOSFODNN7EXAMPLE" not in rendered
    assert "plain-example-value" not in rendered
    assert "configured-secret" not in rendered
    assert "<redacted>" in rendered


def test_provider_failure_is_categorized_and_never_estimated_as_zero_cost(tmp_path: Path) -> None:
    repository, commit = _make_target_repo(tmp_path)
    quality = _write_task(tmp_path / "quality.yaml", task_id="quality-task", commit=commit)
    control = _write_task(
        tmp_path / "control.yaml",
        task_id="budget-control",
        commit=commit,
        control=True,
    )
    suite = LiveEvalSuite(
        quality_tasks=(quality,),
        control_tasks=(control,),
        repository="tests/example",
        repository_commit=commit,
        suite_lock_sha256="b" * 64,
    )
    runs_root = tmp_path / "runs"

    results = run_live_suite(
        suite=suite,
        repository_root=repository,
        runs_root=runs_root,
        config=_config(),
        pricing=_pricing(),
        _client_factory=_failing_factory,
    )

    quality_result = results[0]
    assert quality_result["provider_usage_complete"] is False
    assert quality_result["estimated_cost_usd"] is None
    assert quality_result["failure_category"] == "timeout"
    report = build_live_report(
        runs_root,
        batch_id=str(quality_result["batch_id"]),
        _allow_test_provenance=True,
    )
    assert report["metrics"]["total_estimated_cost_usd"] is None
    assert report["metrics"]["cost_estimate_status"] == "provider_usage_unavailable"


def test_required_evidence_needs_an_output_citation_and_collected_source_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository, commit = _make_target_repo(tmp_path)
    quality = _write_task(tmp_path / "quality.yaml", task_id="quality-task", commit=commit)
    control = _write_task(
        tmp_path / "control.yaml",
        task_id="budget-control",
        commit=commit,
        control=True,
    )
    suite = LiveEvalSuite(
        quality_tasks=(quality,),
        control_tasks=(control,),
        repository="tests/example",
        repository_commit=commit,
        suite_lock_sha256="c" * 64,
    )
    original = live_eval._load_json_from_run

    def with_wrong_source_hash(run_dir: Path | None, filename: str) -> dict[str, Any]:
        if filename == "sources.json":
            source = original(run_dir, filename)
            return {**source, "source_hashes": {"app/main.py": "0" * 64}}
        return original(run_dir, filename)

    monkeypatch.setattr(live_eval, "_load_json_from_run", with_wrong_source_hash)
    results = run_live_suite(
        suite=suite,
        repository_root=repository,
        runs_root=tmp_path / "runs",
        config=_config(),
        pricing=_pricing(),
        _client_factory=_factory,
    )

    quality_result = results[0]
    assert quality_result["required_evidence_cited"] == ["app/main.py"]
    assert quality_result["required_evidence_collected"] == ["app/main.py"]
    assert quality_result["required_evidence_hash_verified"] == []
    assert quality_result["required_evidence_covered"] == []
    assert quality_result["deterministic_status"] == "failed"


def _task_yaml(task_id: str, *, control: bool = False) -> str:
    raw: dict[str, object] = {
        "task_id": task_id,
        "repository": "tests/example",
        "repository_commit": "abc123",
        "user_request": "Locate app/main.py.",
        "expected_files": ["app/main.py"],
        "required_evidence": ["app/main.py"],
        "required_output_fields": (
            [] if control else ["stage-0/repository-analyst-agent-v1.output.summary"]
        ),
        "forbidden_assumptions": ["A hidden router exists."],
        "timeout_seconds": 120,
        "human_notes": "Review evidence.",
    }
    if control:
        raw["evaluation_class"] = CONTROL_CLASS
        raw["max_llm_calls"] = 1
    return yaml.safe_dump(raw, sort_keys=False)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
