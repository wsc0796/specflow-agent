"""Tests for artifact store and renderers."""

import json
from pathlib import Path

import pytest

from specflow.artifacts import ArtifactExistsError, ArtifactStore, ArtifactWriteError, RunManifest
from specflow.artifacts.renderers import render_run_summary, render_technical_spec, render_test_plan
from specflow.evidence import EvidenceBundle


def _manifest(**overrides) -> RunManifest:
    values = {
        "run_id": "test-run-001",
        "started_at": "2026-07-11T12:00:00+00:00",
        "completed_at": "2026-07-11T12:00:05+00:00",
        "status": "completed",
        "provider_type": "mock",
        "model": "mock-model",
        "repository_root": "/tmp/test-repo",
        "requirement": "Add health check endpoint",
        "requirement_hash": "abc123",
        "evidence_hash": "def456",
        "analysis_hash": "ghi789",
        "generation_hash": "jkl012",
        "review_hash": "mno345",
        "review_decision": "PASS",
        "degraded": False,
        "requires_review": False,
        "tool_call_count": 5,
    }
    values.update(overrides)
    return RunManifest(**values)


def _evidence(run_id: str = "test-run-001") -> EvidenceBundle:
    return EvidenceBundle(
        run_id=run_id,
        requirement="Add health check",
        repository_root="/tmp/test-repo",
        project_summary="Test project",
        matched_files=("app.py",),
        selected_files=("app.py",),
    )


def _analysis_json() -> str:
    return json.dumps(
        {
            "requirement_summary": "Add a /health endpoint.",
            "goals": ["Expose health check"],
            "affected_components": ["api", "routes"],
            "risks": ["None"],
            "acceptance_criteria": ["Return 200 OK", "Return status ok"],
            "requires_review": False,
            "degraded": False,
        }
    )


def _generation_json() -> str:
    return json.dumps(
        {
            "requirement_summary": "Add a /health endpoint.",
            "proposed_solution": "Add route with status check.",
            "test_plan": ["Test health returns 200"],
        }
    )


def _review_json() -> str:
    return json.dumps(
        {
            "decision": "PASS",
            "summary": "All checks passed.",
        }
    )


def test_manifest_as_dict_is_serializable() -> None:
    manifest = _manifest()
    result = manifest.as_dict()

    assert result["run_id"] == "test-run-001"
    assert result["status"] == "completed"
    assert result["review_decision"] == "PASS"


def test_manifest_to_json_produces_valid_json() -> None:
    manifest = _manifest()
    raw = manifest.to_json()

    parsed = json.loads(raw)
    assert parsed["run_id"] == "test-run-001"


def test_render_technical_spec_produces_markdown() -> None:
    manifest = _manifest()
    analysis = _analysis_json()

    result = render_technical_spec(manifest, analysis)

    assert "# Technical Specification" in result
    assert "Add health check endpoint" in result
    assert "## Risks" in result


def test_render_test_plan_produces_markdown() -> None:
    result = render_test_plan(_analysis_json(), _generation_json())

    assert "# Test Plan" in result
    assert "## Unit Tests" in result
    assert "## Regression Risk" in result


def test_render_run_summary_produces_markdown() -> None:
    manifest = _manifest()
    evidence = _evidence()

    result = render_run_summary(manifest, evidence)

    assert "# Run Summary" in result
    assert "test-run-001" in result
    assert "## Capability Boundaries" in result


def test_artifact_store_writes_run_directory(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    manifest = _manifest()

    run_dir = store.write_run(
        run_id="test-run-001",
        manifest=manifest,
        evidence=_evidence(),
        analysis_json=_analysis_json(),
        generation_json=_generation_json(),
        review_json=_review_json(),
        tool_calls_json="[]",
        trace_json="[]",
    )

    assert run_dir.exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "analysis.json").exists()
    assert (run_dir / "generation.json").exists()
    assert (run_dir / "review.json").exists()
    assert (run_dir / "technical-spec.md").exists()
    assert (run_dir / "test-plan.md").exists()
    assert (run_dir / "run-summary.md").exists()
    assert (run_dir / "sources.json").exists()


def test_manifest_json_is_valid(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    run_dir = store.write_run(
        run_id="test-run-001",
        manifest=_manifest(),
        evidence=_evidence(),
        analysis_json=_analysis_json(),
        generation_json=_generation_json(),
        review_json=_review_json(),
        tool_calls_json="[]",
        trace_json="[]",
    )

    raw = (run_dir / "manifest.json").read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed["schema_version"] == "1.0.0"
    assert parsed["run_id"] == "test-run-001"


def test_duplicate_run_directory_is_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.write_run(
        run_id="test-run-001",
        manifest=_manifest(),
        evidence=_evidence(),
        analysis_json=_analysis_json(),
        generation_json=_generation_json(),
        review_json=_review_json(),
        tool_calls_json="[]",
        trace_json="[]",
    )

    with pytest.raises(ArtifactExistsError):
        store.write_run(
            run_id="test-run-001",
            manifest=_manifest(),
            evidence=_evidence(),
            analysis_json=_analysis_json(),
            generation_json=_generation_json(),
            review_json=_review_json(),
            tool_calls_json="[]",
            trace_json="[]",
        )


def test_path_traversal_run_id_is_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    with pytest.raises(ArtifactWriteError):
        store.write_run(
            run_id="../escape",
            manifest=_manifest(),
            evidence=_evidence(),
            analysis_json=_analysis_json(),
            generation_json=_generation_json(),
            review_json=_review_json(),
            tool_calls_json="[]",
            trace_json="[]",
        )


def test_api_key_does_not_appear_in_manifest(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    manifest = _manifest(model="gpt-4", provider_type="openai-compatible")

    run_dir = store.write_run(
        run_id="test-run-001",
        manifest=manifest,
        evidence=_evidence(),
        analysis_json=_analysis_json(),
        generation_json=_generation_json(),
        review_json=_review_json(),
        tool_calls_json="[]",
        trace_json="[]",
    )

    raw = (run_dir / "manifest.json").read_text(encoding="utf-8")
    assert "sk-" not in raw
    assert "api_key" not in raw.lower()


def test_write_failure_does_not_leave_completed_manifest(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    with pytest.raises(ArtifactWriteError):
        store.write_run(
            run_id="",
            manifest=_manifest(),
            evidence=_evidence(),
            analysis_json="{}",
            generation_json="{}",
            review_json="{}",
            tool_calls_json="[]",
            trace_json="[]",
        )


def test_markdown_files_exist_and_are_non_empty(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    run_dir = store.write_run(
        run_id="test-run-001",
        manifest=_manifest(),
        evidence=_evidence(),
        analysis_json=_analysis_json(),
        generation_json=_generation_json(),
        review_json=_review_json(),
        tool_calls_json="[]",
        trace_json="[]",
    )

    for name in ["technical-spec.md", "test-plan.md", "run-summary.md"]:
        path = run_dir / name
        assert path.exists(), f"Missing: {name}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 50, f"Too short: {name}"


def test_manifest_contains_required_fields(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    run_dir = store.write_run(
        run_id="test-run-001",
        manifest=_manifest(),
        evidence=_evidence(),
        analysis_json=_analysis_json(),
        generation_json=_generation_json(),
        review_json=_review_json(),
        tool_calls_json="[]",
        trace_json="[]",
    )

    raw = (run_dir / "manifest.json").read_text(encoding="utf-8")
    parsed = json.loads(raw)

    required = [
        "schema_version",
        "run_id",
        "started_at",
        "completed_at",
        "status",
        "provider_type",
        "model",
        "repository_root",
        "evidence_hash",
        "analysis_hash",
        "generation_hash",
        "review_hash",
    ]
    for key in required:
        assert key in parsed, f"Missing: {key}"
