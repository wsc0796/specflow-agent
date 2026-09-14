"""Dev input isolation; only synthetic manifests and source repositories are used."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


def dataset_module():
    assert importlib.util.find_spec("specflow.evaluation.dataset_v1") is not None, (
        "Dataset v1 needs its own Dev-only loader"
    )
    from specflow.evaluation import dataset_v1

    return dataset_v1


def make_dataset(root, revision="a" * 40):
    root.mkdir()
    categories = ["exact_keyword"] * 5 + ["semantic_rewrite"] * 5
    categories += ["multi_file"] * 4 + ["no_answer"] * 3 + ["safety_or_stale_index"] * 3
    cases = [
        {
            "case_id": f"SF-RT-D{i:03}",
            "suite": "specflow_repository_tasks",
            "dataset_version": "v1",
            "annotation_version": "v1",
            "status": "frozen_v1",
            "split": "dev",
            "repository_revision": revision,
            "category": category,
            "requirement": "Explain the health endpoint.",
            "answerability": "answerable",
            "gold_evidence": [{"fact_id": "EVALUATOR_ONLY_MARKER"}],
            "expected_properties": [{"statement": "EVALUATOR_ONLY_MARKER"}],
            "forbidden_claims": ["EVALUATOR_ONLY_MARKER"],
            "annotation_provenance": {"notes": "EVALUATOR_ONLY_MARKER"},
        }
        for i, category in enumerate(categories, 1)
    ]
    identity = {
        "suite": "specflow_repository_tasks",
        "dataset_version": "v1",
        "annotation_version": "v1",
        "repository_revision": revision,
        "status": "frozen_v1",
    }
    manifest = {
        **identity,
        "frozen": True,
        "freeze_commit": "b" * 40,
        "splits": {
            "dev": {
                "file": "dev.json",
                "case_count": 20,
                "case_ids": [c["case_id"] for c in cases],
            }
        },
    }
    dev = {**identity, "split": "dev", "case_count": 20, "cases": cases}
    for name, value in (("manifest.json", manifest), ("dev.json", dev)):
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    (root / "holdout.json").write_text("DO NOT OPEN", encoding="utf-8")
    return root


def make_repository(root):
    root.mkdir()
    for name, text in {
        "src/app.py": "def health():\n    return 'REPOSITORY_EXCERPT_MARKER'\n",
        "tests/test_app.py": "# ordinary product test\n",
        "README.md": "# Synthetic source fixture\n",
        "pyproject.toml": "[project]\nname = 'fixture'\n",
        "uv.lock": "version = 1\n",
        "docs/answers.md": "EVALUATOR_ONLY_MARKER",
        "benchmarks/cases/answer.json": "EVALUATOR_ONLY_MARKER",
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    commands = [
        ["init", "--quiet"],
        ["add", "."],
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "fixture",
        ],
    ]
    for command in commands:
        subprocess.run(["git", "-C", str(root), *command], check=True, capture_output=True)
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    return root, revision


def test_dev_loader_reads_only_explicit_files_and_projects_requirement(tmp_path, monkeypatch):
    module = dataset_module()
    root = make_dataset(tmp_path / "dataset")
    opened = []
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        opened.append(path.name)
        assert path.name != "holdout.json", "Forbidden Holdout open"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    dataset = module.load_dev_dataset(root)
    assert len(dataset.cases) == 20
    assert opened == ["manifest.json", "dev.json"]
    assert dataset.cases[0].product_input() == {"requirement": "Explain the health endpoint."}
    assert "EVALUATOR_ONLY_MARKER" in json.dumps(dataset.cases[0].annotations)


@pytest.mark.parametrize(
    "change", ["id", "split", "count", "version", "revision", "category", "file"]
)
def test_dev_loader_rejects_invalid_identity_before_execution(tmp_path, change):
    module = dataset_module()
    root = make_dataset(tmp_path / "dataset")
    name = "manifest.json" if change == "file" else "dev.json"
    data = json.loads((root / name).read_text())
    if change == "file":
        data["splits"]["dev"]["file"] = "holdout.json"
    elif change == "count":
        data["cases"].pop()
    else:
        field = {
            "id": "case_id",
            "version": "dataset_version",
            "revision": "repository_revision",
        }.get(change, change)
        data["cases"][0][field] = "invalid"
    (root / name).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        module.load_dev_dataset(root)


def test_snapshot_uses_fixed_git_content_and_excludes_answers(tmp_path):
    module = dataset_module()
    repo, revision = make_repository(tmp_path / "repo")
    (repo / "src/app.py").write_text("uncommitted change", encoding="utf-8")
    target = tmp_path / "target"
    module.prepare_source_snapshot(repo, revision, target)
    assert "REPOSITORY_EXCERPT_MARKER" in (target / "src/app.py").read_text()
    assert not (target / "docs").exists()
    assert not (target / "benchmarks").exists()
    assert not (target / ".git").exists()
    module.validate_source_snapshot(repo, revision, target)
    (target / "answer.json").write_text("EVALUATOR_ONLY_MARKER", encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot"):
        module.validate_source_snapshot(repo, revision, target)


def test_snapshot_rejects_checkout_and_wrong_revision(tmp_path):
    module = dataset_module()
    repo, revision = make_repository(tmp_path / "repo")
    with pytest.raises(ValueError):
        module.prepare_source_snapshot(repo, revision, repo)
    with pytest.raises(ValueError):
        module.prepare_source_snapshot(repo, "0" * 40, tmp_path / "target")


def test_frozen_dev_accepts_git_checkout_line_endings(tmp_path):
    module = dataset_module()
    repo, revision = make_repository(tmp_path / "repo")
    root = make_dataset(repo / "dataset", revision)
    dev = json.loads((root / "dev.json").read_text(encoding="utf-8"))
    (root / "dev.json").write_bytes(json.dumps(dev, indent=2).replace("\n", "\r\n").encode())
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "core.autocrlf=true",
            "add",
            "dataset/dev.json",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "freeze CRLF fixture",
        ],
        check=True,
    )
    frozen = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["freeze_commit"] = frozen
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    module.validate_frozen_dev(repo, root, module.load_dev_dataset(root))
