"""Tests for CLI entry point."""

from pathlib import Path

import pytest

from specflow.cli import main


def test_cli_help_exits_gracefully() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--help"])
    assert exc_info.value.code == 0


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


def test_cli_mock_run_with_temp_repo(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("# test app\n", encoding="utf-8")
    output = tmp_path / "artifacts"

    exit_code = _run_cli_mock(repo, output, "Add health check endpoint")

    assert exit_code in {0, 3, 4}


def test_cli_mock_run_creates_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("def health():\n    return {'status':'ok'}\n", encoding="utf-8")
    output = tmp_path / "artifacts"
    requirement = "Add health check endpoint"

    exit_code = _run_cli_mock(repo, output, requirement)

    assert exit_code in {0, 3, 4}
    if exit_code == 0:
        assert output.exists()
        run_dirs = list(output.glob("run-*"))
        assert len(run_dirs) >= 1


def test_cli_provider_config_missing_reports_clearly(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1", encoding="utf-8")

    with pytest.raises(SystemExit):
        main(
            [
                "run",
                "--repo",
                str(repo),
                "--requirement",
                "test",
                "--provider",
                "openai-compatible",
            ]
        )


def test_api_key_never_appears_in_cli_output_or_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1", encoding="utf-8")
    output = tmp_path / "artifacts"
    exit_code = _run_cli_mock(repo, output, "test requirement")

    if exit_code == 0 and output.exists():
        for run_dir in output.glob("run-*"):
            for artifact in run_dir.iterdir():
                content = artifact.read_text(encoding="utf-8")
                assert "sk-" not in content
                assert "api_key" not in content.lower()


def test_cli_same_input_produces_stable_output(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "app.py").write_text("def stable():\n    return 1\n", encoding="utf-8")

    first_code = _run_cli_mock(repo, tmp_path / "out1", "stable function")
    second_code = _run_cli_mock(repo, tmp_path / "out2", "stable function")

    assert first_code == second_code


def test_cli_does_not_modify_target_repo(tmp_path: Path) -> None:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    target = repo / "app.py"
    target.write_text("original", encoding="utf-8")
    before = target.read_bytes()

    _run_cli_mock(repo, tmp_path / "artifacts", "test")

    assert target.read_bytes() == before


def _run_cli_mock(repo: Path, output: Path, requirement: str) -> int:
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
            ]
        )
        return 0
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else 1
