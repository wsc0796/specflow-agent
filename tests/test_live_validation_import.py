import hashlib
import json
from pathlib import Path

from specflow.evaluation import EvaluationStatus, validate_live_artifact_import
from specflow.evaluation.validators import REQUIRED_ARTIFACTS


def _hash_payload(payload: dict[str, object], excluded_field: str) -> str:
    canonical = dict(payload)
    canonical.pop(excluded_field, None)
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    analysis: dict[str, object] = {"requirement_summary": "test"}
    analysis["analysis_hash"] = _hash_payload(analysis, "analysis_hash")
    generation: dict[str, object] = {"analysis_hash": analysis["analysis_hash"], "plan": "test"}
    generation["generation_hash"] = _hash_payload(generation, "generation_hash")
    review = {
        "analysis_hash": analysis["analysis_hash"],
        "generation_hash": generation["generation_hash"],
    }
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
        json.dumps([{"call_id": "call-1", "tool_name": "read_file", "status": "success"}]),
        encoding="utf-8",
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


def test_live_import_rejects_forged_hash_or_non_read_only_tool(tmp_path: Path) -> None:
    artifacts, repo = _artifact_dir(tmp_path)
    generation = json.loads((artifacts / "generation.json").read_text(encoding="utf-8"))
    generation["generation_hash"] = "f" * 64
    (artifacts / "generation.json").write_text(json.dumps(generation), encoding="utf-8")

    assert any(
        f.code == "hash_content_invalid"
        for f in validate_live_artifact_import(artifacts, repo).findings
    )

    artifacts, repo = _artifact_dir(tmp_path / "tool")
    (artifacts / "tool-calls.json").write_text(
        json.dumps([{"call_id": "call-1", "tool_name": "write_file", "status": "success"}]),
        encoding="utf-8",
    )
    assert any(
        f.code == "tool_calls_missing"
        for f in validate_live_artifact_import(artifacts, repo).findings
    )


def test_live_import_does_not_follow_artifact_symlinks(tmp_path: Path) -> None:
    artifacts, repo = _artifact_dir(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(
        '{"provider_type": "openai-compatible", "model": "secret"}', encoding="utf-8"
    )
    (artifacts / "manifest.json").unlink()
    try:
        (artifacts / "manifest.json").symlink_to(outside)
    except OSError:
        return

    record = validate_live_artifact_import(artifacts, repo)
    assert record.provider_type == ""
    assert any(f.code == "artifact_missing" for f in record.findings)
