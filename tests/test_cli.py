"""Tests for CLI entry point."""

import json
from pathlib import Path

import pytest

from specflow import __version__
from specflow.cli import main


def test_cli_help_exits_gracefully() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--help"])
    assert exc_info.value.code == 0


def test_cli_version_reports_installed_package_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"specflow {__version__}"


def test_cli_no_command_shows_help() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_cli_missing_repo_exits_with_error() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--repo", "/nonexistent/path", "--requirement", "test"])
    assert exc_info.value.code in {2, 3}


def test_cli_missing_requirement_exits_with_error() -> None:
    with pytest.raises(SystemExit):
        main(["run", "--repo", ".", "--requirement", ""])


def test_cli_mock_run_succeeds(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("# test app\n", encoding="utf-8")
    output = tmp_path / "artifacts"

    exit_code = _run_cli_mock(repo, output, "Add health check endpoint")

    assert exit_code == 0


def test_cli_mock_run_creates_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("def health():\n    return {'status':'ok'}\n", encoding="utf-8")
    output = tmp_path / "artifacts"
    requirement = "Add health check endpoint"

    exit_code = _run_cli_mock(repo, output, requirement)

    assert exit_code == 0
    assert output.exists()
    run_dirs = list(output.glob("run-*"))
    assert len(run_dirs) >= 1
    run_dir = run_dirs[0]
    expected_files = {
        "manifest.json",
        "analysis.json",
        "generation.json",
        "review.json",
        "sources.json",
        "tool-calls.json",
        "trace.json",
        "technical-spec.md",
        "test-plan.md",
        "run-summary.md",
    }
    assert expected_files <= {path.name for path in run_dir.iterdir()}
    manifest_text = (run_dir / "manifest.json").read_text(encoding="utf-8")
    assert requirement in manifest_text
    assert json.loads(manifest_text)["status"] == "completed"
    traces = json.loads((run_dir / "trace.json").read_text(encoding="utf-8"))
    assert len(traces) == 3
    assert {trace["metadata"]["worker_role"] for trace in traces} == {
        "analyze",
        "generate",
        "review",
    }


def test_cli_provider_config_missing_reports_clearly(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1", encoding="utf-8")
    output = tmp_path / "artifacts"

    exit_code = _run_cli_with_provider(repo, output, "test", "openai-compatible")

    assert exit_code == 2
    error_files = list(output.glob("*-error.json"))
    assert len(error_files) >= 1


def test_api_key_never_appears_in_cli_output_or_artifacts(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1", encoding="utf-8")
    output = tmp_path / "artifacts"
    secret = "sk-test-secret-value-1234567890"
    monkeypatch.setenv("SPECFLOW_LLM_API_KEY", secret)
    exit_code = _run_cli_mock(repo, output, "test requirement")

    assert exit_code == 0
    if output.exists():
        for run_dir in output.glob("run-*"):
            for artifact in run_dir.iterdir():
                content = artifact.read_text(encoding="utf-8")
                assert secret not in content


def test_cli_same_input_produces_stable_output(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("def stable():\n    return 1\n", encoding="utf-8")

    first_code = _run_cli_mock(repo, tmp_path / "out1", "stable function")
    second_code = _run_cli_mock(repo, tmp_path / "out2", "stable function")

    assert first_code == second_code
    assert first_code == 0
    assert _single_run_id(tmp_path / "out1") == _single_run_id(tmp_path / "out2")


def test_cli_max_files_limits_selected_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    for index in range(3):
        (repo / f"match_{index}.py").write_text("health endpoint\n", encoding="utf-8")

    output = tmp_path / "artifacts"
    exit_code = _run_cli_mock(repo, output, "health endpoint", max_files=1)

    assert exit_code == 0
    run_dir = next(output.glob("run-*"))
    sources = json.loads((run_dir / "sources.json").read_text(encoding="utf-8"))
    assert len(sources["selected_files"]) <= 1


def test_cli_requires_human_review_returns_degraded_exit_code(monkeypatch, tmp_path: Path) -> None:
    import specflow.runner as runner

    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("def health():\n    return 1\n", encoding="utf-8")
    original = runner._create_mock_clients
    monkeypatch.setattr(
        runner,
        "_create_mock_clients",
        lambda requirement: original(requirement, requires_human_review=True),
    )

    assert _run_cli_mock(repo, tmp_path / "artifacts", "Add health endpoint") == 4


def test_cli_does_not_modify_target_repo(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    target = repo / "app.py"
    target.write_text("original", encoding="utf-8")
    before = target.read_bytes()

    _run_cli_mock(repo, tmp_path / "artifacts", "test")

    assert target.read_bytes() == before


def _run_cli_mock(repo: Path, output: Path, requirement: str, *, max_files: int = 5) -> int:
    try:
        main(
            [
                "run",
                "--repo",
                str(repo),
                "--requirement",
                requirement,
                "--output",
                str(output),
                "--provider",
                "mock",
                "--max-files",
                str(max_files),
            ]
        )
        return 0
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else 1


def _run_cli_with_provider(repo: Path, output: Path, requirement: str, provider: str) -> int:
    try:
        main(
            [
                "run",
                "--repo",
                str(repo),
                "--requirement",
                requirement,
                "--output",
                str(output),
                "--provider",
                provider,
            ]
        )
        return 0
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else 1


def _single_run_id(output: Path) -> str:
    run_dirs = list(output.glob("run-*"))
    assert len(run_dirs) == 1
    return run_dirs[0].name
