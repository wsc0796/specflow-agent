import os
from pathlib import Path, PureWindowsPath

import pytest

from specflow.scanner import (
    FileLimitExceededError,
    InvalidRepositoryPathError,
    RepositoryScanner,
    ScanLimits,
    _is_link_or_reparse_point,
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


@pytest.mark.parametrize("variant", [".GIT", ".Git", ".VENV", "NODE_MODULES"])
def test_ignores_ignored_directory_name_case_variants(tmp_path: Path, variant: str) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / variant).mkdir()
    (repository / variant / "HEAD").write_text("ref: refs/heads/main\n")
    (repository / "kept.txt").write_text("kept")
    result = scanner(tmp_path).scan(repository)
    assert [file.path for file in result.files] == ["kept.txt"]
    assert result.ignored_directories == [variant]


def test_rejects_root_inside_case_variant_of_ignored_directory(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    ignored = allowed / ".GIT"
    ignored.mkdir()
    with pytest.raises(InvalidRepositoryPathError):
        scanner(allowed).scan(ignored)


def test_skips_reparse_point_directory_escaping_repo(monkeypatch, tmp_path: Path) -> None:
    """A junction/reparse-point directory resolving outside root is skipped.

    Directory junctions are reparse points, not symlinks, so
    ``Path.is_symlink()`` is False for them on Windows. Simulate the junction
    (a directory whose resolved target lies outside the repository) with mocks
    so the test runs on Windows without junction privileges.
    """
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "safe_dir").mkdir()
    (repository / "safe.py").write_text("x")
    escape = repository / "escape_dir"
    escape.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    original_resolve = Path.resolve

    def fake_resolve(path: Path, strict: bool = False) -> Path:
        if path == escape:
            return outside
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", fake_resolve)
    monkeypatch.setattr(
        "specflow.scanner._is_link_or_reparse_point",
        lambda candidate: candidate == escape,
    )

    result = scanner(tmp_path).scan(repository)

    assert escape.name not in result.directories
    assert "safe_dir" in result.directories
    assert [file.path for file in result.files] == ["safe.py"]


def test_plain_directories_are_not_reparse_points(tmp_path: Path) -> None:
    """Reparse-point detection must not flag an ordinary directory."""
    target = tmp_path / "target"
    target.mkdir()

    assert _is_link_or_reparse_point(target) is False


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


def test_windows_path_containment_boundary_is_rejected_without_symlink(tmp_path: Path) -> None:
    del tmp_path
    assert not RepositoryScanner._is_within(
        PureWindowsPath(r"C:\outside"), PureWindowsPath(r"C:\allowed")
    )
