import json
from pathlib import Path

from specflow.evaluation import EvaluationStatus, validate_live_artifact_import
from specflow.evaluation.validators import REQUIRED_ARTIFACTS


def _artifact_dir(
    tmp_path: Path, *, provider: str = "openai-compatible", model: str = "model"
) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    artifacts = tmp_path / "run"
    artifacts.mkdir()
    for name in REQUIRED_ARTIFACTS:
        (artifacts / name).write_text(
            "# artifact\n" if name.endswith(".md") else "{}", encoding="utf-8"
        )
    analysis = {"analysis_hash": "a" * 64}
    generation = {"analysis_hash": "a" * 64, "generation_hash": "b" * 64}
    review = {"analysis_hash": "a" * 64, "generation_hash": "b" * 64}
    (artifacts / "manifest.json").write_text(
        json.dumps({"provider_type": provider, "model": model, "status": "completed"}),
        encoding="utf-8",
    )
    (artifacts / "analysis.json").write_text(json.dumps(analysis), encoding="utf-8")
    (artifacts / "generation.json").write_text(json.dumps(generation), encoding="utf-8")
    (artifacts / "review.json").write_text(json.dumps(review), encoding="utf-8")
    (artifacts / "sources.json").write_text(
        json.dumps({"selected_files": ["app.py"], "matched_files": [], "excerpts": []}),
        encoding="utf-8",
    )
    (artifacts / "tool-calls.json").write_text(
        json.dumps([{"tool_name": "read_file"}]), encoding="utf-8"
    )
    (artifacts / "trace.json").write_text(
        json.dumps(
            [{"metadata": {"worker_role": role}} for role in ("analyze", "generate", "review")]
        ),
        encoding="utf-8",
    )
    return artifacts, repo


def test_valid_live_artifact_import_passes_without_provider_call(tmp_path: Path) -> None:
    artifacts, repo = _artifact_dir(tmp_path)

    record = validate_live_artifact_import(artifacts, repo)

    assert record.status == EvaluationStatus.PASSED
    assert record.provider_type == "openai-compatible"


def test_live_import_rejects_mock_provider(tmp_path: Path) -> None:
    artifacts, repo = _artifact_dir(tmp_path, provider="mock")
    assert any(
        f.code == "live_provider_mock"
        for f in validate_live_artifact_import(artifacts, repo).findings
    )


def test_live_import_rejects_missing_artifact_invalid_json_external_path_secret_and_traces(
    tmp_path: Path,
) -> None:
    artifacts, repo = _artifact_dir(tmp_path)
    (artifacts / "generation.json").unlink()
    assert any(
        f.code == "artifact_missing"
        for f in validate_live_artifact_import(artifacts, repo).findings
    )

    artifacts, repo = _artifact_dir(tmp_path / "second")
    (artifacts / "sources.json").write_text("{", encoding="utf-8")
    assert any(
        f.code == "invalid_json" for f in validate_live_artifact_import(artifacts, repo).findings
    )

    artifacts, repo = _artifact_dir(tmp_path / "third")
    (artifacts / "sources.json").write_text(
        json.dumps({"selected_files": ["../outside.py"], "matched_files": [], "excerpts": []}),
        encoding="utf-8",
    )
    assert any(
        f.code == "source_path_external"
        for f in validate_live_artifact_import(artifacts, repo).findings
    )

    artifacts, repo = _artifact_dir(tmp_path / "fourth")
    (artifacts / "run-summary.md").write_text(
        "api_key=sk-test-secret-value-1234567890", encoding="utf-8"
    )
    assert any(
        f.code == "secret_detected" for f in validate_live_artifact_import(artifacts, repo).findings
    )

    artifacts, repo = _artifact_dir(tmp_path / "fifth")
    (artifacts / "trace.json").write_text(json.dumps([]), encoding="utf-8")
    assert any(
        f.code == "worker_trace_missing"
        for f in validate_live_artifact_import(artifacts, repo).findings
    )
