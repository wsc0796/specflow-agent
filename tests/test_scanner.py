import os
from pathlib import Path

import pytest

from specflow.scanner import (
    FileLimitExceededError,
    InvalidRepositoryPathError,
    RepositoryScanner,
    ScanLimits,
)


def scanner(root: Path, **limits: int) -> RepositoryScanner:
    return RepositoryScanner([root], ScanLimits(**limits))


def test_scans_normal_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repos" / "demo"
    repository.mkdir(parents=True)
    (repository / "app.py").write_text("print('ok')")
    (repository / "src").mkdir()
    result = scanner(tmp_path / "repos").scan(repository)
    assert result.total_files == 1
    assert result.files[0].path == "app.py"
    assert result.directories == ["src"]


def test_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(InvalidRepositoryPathError):
        scanner(tmp_path).scan(tmp_path / "missing")


def test_rejects_parent_path_attack(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    with pytest.raises(InvalidRepositoryPathError):
        scanner(allowed).scan(allowed / "..")


def test_rejects_path_outside_allowed_root(tmp_path: Path) -> None:
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    with pytest.raises(InvalidRepositoryPathError):
        scanner(allowed).scan(outside)


def test_ignores_known_directories(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    for name in (".git", ".venv", "node_modules"):
        directory = repository / name
        directory.mkdir()
        (directory / "hidden.txt").write_text("ignored")
    (repository / "kept.txt").write_text("kept")
    result = scanner(tmp_path).scan(repository)
    assert [file.path for file in result.files] == ["kept.txt"]
    assert result.ignored_directories == [".git", ".venv", "node_modules"]


def test_records_oversized_file_as_metadata(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "large.bin").write_bytes(b"x" * 11)
    result = scanner(tmp_path, max_file_size_bytes=10).scan(repository)
    assert result.files == [result.files[0]]
    assert result.files[0].is_oversized is True
    assert result.files[0].size_bytes == 11


def test_enforces_file_count_limit(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "one.txt").write_text("1")
    (repository / "two.txt").write_text("2")
    with pytest.raises(FileLimitExceededError):
        scanner(tmp_path, max_files=1).scan(repository)


@pytest.mark.skipif(os.name == "nt", reason="directory symlinks require admin on Windows")
def test_skips_directory_symlink_escaping_repo(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "safe_dir").mkdir()
    (repository / "safe.py").write_text("x")
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink = repository / "escape_dir"
    symlink.symlink_to(outside, target_is_directory=True)

    result = scanner(tmp_path).scan(repository)

    assert symlink.name not in result.directories
    assert "safe_dir" in result.directories
