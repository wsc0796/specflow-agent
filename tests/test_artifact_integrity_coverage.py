"""The artifact hash table must cover the fixed set of data files."""

import json
from pathlib import Path

import pytest

from specflow import runner_multi
from specflow.evaluation.dev_baseline import inspect_attempt


@pytest.fixture
def artifact_run(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("# health\n", encoding="utf-8")
    output = tmp_path / "out"
    assert (
        runner_multi.run_multi_agent(repo=repo, requirement="health", output=output, mock=True) == 0
    )
    return repo, output, next(output.glob("run-multi-*"))


def observation(artifact_run):
    repo, output, _ = artifact_run
    return inspect_attempt(output, repo, mode="multi-agent")["evaluator_results"][
        "artifact_validation"
    ]


def test_complete_product_hash_table_passes(artifact_run):
    assert observation(artifact_run)["verdict"] == "pass"


@pytest.mark.parametrize("change", ["empty", "missing", "extra", "absolute", "digest", "content"])
def test_invalid_integrity_table_or_content_fails(artifact_run, change, monkeypatch, tmp_path):
    _, _, run = artifact_run
    integrity_path = run / "artifact-integrity.json"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    hashes = integrity["artifact_hashes"]
    outside = tmp_path / "outside.json"
    outside.write_text("private synthetic", encoding="utf-8")
    if change == "empty":
        hashes.clear()
        (run / "agent-outputs.json").write_text("INVALID JSON", encoding="utf-8")
    elif change == "missing":
        del hashes["agent-outputs.json"]
        (run / "agent-outputs.json").write_text("INVALID JSON", encoding="utf-8")
    elif change == "extra":
        hashes["../../outside.json"] = "0" * 64
    elif change == "absolute":
        hashes[str(outside)] = "0" * 64
    elif change == "digest":
        hashes["agent-outputs.json"] = True
    else:
        (run / "agent-outputs.json").write_text("INVALID JSON", encoding="utf-8")
    integrity_path.write_text(json.dumps(integrity), encoding="utf-8")
    original_read = Path.read_bytes

    def read_inside_only(path):
        assert path.resolve().is_relative_to(run.resolve()), "must not read table-supplied paths"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_inside_only)
    assert observation(artifact_run)["verdict"] == "fail"


def test_linked_required_artifact_fails_even_with_omitted_hash(artifact_run, monkeypatch):
    _, _, run = artifact_run
    path = run / "artifact-integrity.json"
    integrity = json.loads(path.read_text(encoding="utf-8"))
    del integrity["artifact_hashes"]["sources.json"]
    path.write_text(json.dumps(integrity), encoding="utf-8")
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p.name == "sources.json" or original(p))
    assert observation(artifact_run)["verdict"] == "fail"
