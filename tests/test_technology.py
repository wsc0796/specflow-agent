from pathlib import Path

import pytest

from specflow.scanner import (
    FileMetadata,
    RepositoryScanner,
    ScanLimits,
    ScanResult,
)
from specflow.technology import TechnologyStackDetector

# ── helpers ────────────────────────────────────────────────────


def _scan(tmp_path: Path) -> ScanResult:
    """Run T-003 scanner over *tmp_path* (allowed root = tmp_path)."""
    return RepositoryScanner([tmp_path], ScanLimits()).scan(tmp_path)


def _add_file(base: Path, relative: str, content: str = "") -> None:
    full = base / relative
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def _oversized_metadata(path: str) -> FileMetadata:
    return FileMetadata(path=path, size_bytes=2_000_000, is_oversized=True)


# ── existing scenarios (updated for ScanResult) ─────────────────


def test_detects_supported_pyproject_stack_with_evidence(tmp_path: Path) -> None:
    _add_file(
        tmp_path,
        "pyproject.toml",
        "[project]\ndependencies = ['fastapi', 'pydantic>=2', 'sqlalchemy', 'aiosqlite']\n"
        "[dependency-groups]\ndev = ['pytest', 'ruff']\n",
    )
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert result.language == "python"
    assert result.frameworks == ["fastapi"]
    assert result.validation_library == "pydantic"
    assert result.orm == "sqlalchemy"
    assert result.database == "sqlite"
    assert result.test_framework == "pytest"
    assert result.lint_tools == ["ruff"]
    assert result.dependency_files == ["pyproject.toml"]
    assert result.application_entry_candidates == ["main.py"]
    assert any(item.matched == "fastapi" for item in result.evidence)
    assert result.parse_warnings == []


def test_detects_requirements(tmp_path: Path) -> None:
    _add_file(tmp_path, "requirements.txt", "fastapi\npytest\nruff\n")
    _add_file(tmp_path, "app.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert result.dependency_files == ["requirements.txt"]
    assert result.application_entry_candidates == ["app.py"]


def test_unknown_repository_is_not_guessed(tmp_path: Path) -> None:
    result = TechnologyStackDetector().detect(_scan(tmp_path))
    assert result.language == "unknown"
    assert result.frameworks == []
    assert result.evidence == []


# ── T-004.1: version operator edge cases ────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("fastapi~=0.115", "fastapi"),
        ("fastapi~=0.115.0", "fastapi"),
        ("pytest!=8.0", "pytest"),
        ("pkg; python_version >= '3.12'", "pkg"),
        ("pkg[extra]; python_version >= '3.12'", "pkg"),
        ("fastapi>=0.100,<1.0", "fastapi"),
        ("package @ https://example.com/pkg.whl", "package"),
        ("  fastapi  ", "fastapi"),
    ],
)
def test_normalized_name_handles_edge_cases(raw: str, expected: str) -> None:
    assert TechnologyStackDetector._normalized_name(raw) == expected


def test_version_operators_are_parsed_from_pyproject(tmp_path: Path) -> None:
    _add_file(
        tmp_path,
        "pyproject.toml",
        "[project]\ndependencies = [\n"
        "'fastapi~=0.115',\n"
        "'pytest!=8.0',\n"
        "'pydantic>=2.0,<3.0',\n"
        "]\n",
    )
    _add_file(tmp_path, "main.py", "x=1\n")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert result.validation_library == "pydantic"
    assert result.test_framework == "pytest"
    assert result.frameworks == ["fastapi"]


# ── T-004.1: corrupted pyproject.toml ───────────────────────────


def test_corrupted_pyproject_toml_produces_warning(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "this is not valid toml {{{")
    _add_file(tmp_path, "main.py", "print('hello')\n")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert result.language == "python"
    assert result.parse_warnings == ["pyproject.toml could not be parsed"]
    assert result.dependency_files == ["pyproject.toml"]  # still recorded as present
    assert result.frameworks == []  # nothing parsed


# ── T-004.1: both dependency files present ──────────────────────


def test_both_pyproject_and_requirements(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "requirements.txt", "pytest\n")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert set(result.dependency_files) == {"pyproject.toml", "requirements.txt"}
    assert result.frameworks == ["fastapi"]
    assert result.test_framework == "pytest"


# ── T-004.1: .venv isolation ────────────────────────────────────


def test_venv_fastapi_is_ignored(tmp_path: Path) -> None:
    """FastAPI installed in .venv must not leak into the project stack."""
    _add_file(tmp_path, ".venv/lib/fastapi/__init__.py", "")
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = []\n")
    _add_file(tmp_path, "src/main.py", "print('hello')\n")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert result.frameworks == []
    assert result.language == "python"


# ── T-004.1: SQLite is no longer a false positive ───────────────


def test_sqlite_string_in_source_does_not_confirm_database(tmp_path: Path) -> None:
    """'sqlite' appearing in code/comments is NOT a confirmed database."""
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(
        tmp_path,
        "app.py",
        "# This project does NOT use sqlite\nfrom fastapi import FastAPI\napp = FastAPI()\n",
    )

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert result.database is None  # not confirmed from dependencies


def test_aiosqlite_dependency_confirms_sqlite(tmp_path: Path) -> None:
    _add_file(tmp_path, "requirements.txt", "aiosqlite\n")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert result.database == "sqlite"


# ── T-004.1: oversized files are skipped ────────────────────────


def test_oversized_python_file_is_not_read(tmp_path: Path) -> None:
    scanner = RepositoryScanner([tmp_path], ScanLimits(max_file_size_bytes=10))
    _add_file(tmp_path, "small.py", "print(1)")
    (tmp_path / "huge.py").write_bytes(b"x" * 100)

    result = TechnologyStackDetector().detect(scanner.scan(tmp_path))

    assert result.language == "python"
    # huge.py is marked oversized in the scan and must NOT be read
    assert result.application_entry_candidates == [
        p for p in result.application_entry_candidates if "huge" not in p
    ]


# ── T-004.1: multiple entry candidates ──────────────────────────


def test_multiple_fastapi_entries_are_all_reported(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "api/v1/users.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _add_file(tmp_path, "api/v1/orders.py", "from fastapi import FastAPI\nrouter = FastAPI()\n")
    _add_file(tmp_path, "utils/helpers.py", "print('no fastapi here')")

    result = TechnologyStackDetector().detect(_scan(tmp_path))

    assert len(result.application_entry_candidates) == 2
    assert "api/v1/orders.py" in result.application_entry_candidates
    assert "api/v1/users.py" in result.application_entry_candidates
    assert "utils/helpers.py" not in result.application_entry_candidates


# ── code-review fix: real-file Python evidence ──────────────────


def test_python_evidence_uses_real_file_not_synthetic(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "src/main.py", "print('ok')")

    tech = TechnologyStackDetector().detect(_scan(tmp_path))

    assert tech.language == "python"
    assert not any(e.file == "repository" for e in tech.evidence), (
        "Python evidence must use a real file path, not 'repository'"
    )
    assert any(e.file.endswith(".py") or e.file.endswith(".toml") for e in tech.evidence)


# ── code-review fix: SQLite file-content evidence ───────────────


def test_sqlite_pattern_in_file_content_adds_evidence(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "src/db.py", "import sqlite3\nconn = sqlite3.connect(':memory:')\n")

    tech = TechnologyStackDetector().detect(_scan(tmp_path))

    # SQLite is in file content but not in dependencies → evidence exists
    sqlite_evidence = [e for e in tech.evidence if "sqlite" in e.matched.lower()]
    assert sqlite_evidence, "SQLite file-content evidence should be recorded"
    assert sqlite_evidence[0].file == "src/db.py"


def test_sqlite_file_evidence_does_not_change_database_conclusion(
    tmp_path: Path,
) -> None:
    """File-content SQLite patterns add evidence but do NOT confirm the database."""
    _add_file(tmp_path, "requirements.txt", "fastapi\n")
    _add_file(
        tmp_path,
        "app.py",
        "sqlite:///data.db\nfrom fastapi import FastAPI\n",
    )

    tech = TechnologyStackDetector().detect(_scan(tmp_path))

    # Evidence from file content
    assert any("sqlite" in e.matched.lower() for e in tech.evidence)
    # But database is NOT confirmed (no aiosqlite/sqlite dependency)
    assert tech.database is None
