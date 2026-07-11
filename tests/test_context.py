from pathlib import Path

import pytest

from specflow.context import (
    ContextGenerationError,
    ProjectContextGenerator,
)
from specflow.scanner import RepositoryScanner, ScanLimits
from specflow.technology import TechnologyStackDetector

# ── helpers ────────────────────────────────────────────────────

def _add_file(base: Path, relative: str, content: str = "") -> None:
    full = base / relative
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def _scan_tech(tmp_path: Path):
    """Run T-003 scan + T-004 detect on a temp directory."""
    scan = RepositoryScanner([tmp_path], ScanLimits()).scan(tmp_path)
    tech = TechnologyStackDetector().detect(scan)
    return scan, tech


def _generator() -> ProjectContextGenerator:
    return ProjectContextGenerator()


# ── normal FastAPI project ─────────────────────────────────────

def test_normal_fastapi_project_produces_complete_context(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi', 'pydantic', 'sqlalchemy', 'aiosqlite']\n"
              "[dependency-groups]\ndev = ['pytest', 'ruff']\n")
    _add_file(tmp_path, "app/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _add_file(tmp_path, "app/routers/users.py", "print('ok')")
    _add_file(tmp_path, "tests/test_app.py", "def test(): pass")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("demo-api", scan, tech)
    md = _generator().render_markdown(ctx)

    # All sections present
    assert "## Project Overview" in md
    assert "## Directory Summary" in md
    assert "## Technology Stack" in md
    assert "## Application Entry Candidates" in md
    assert "## Dependency Files" in md
    assert "## Testing & Linting" in md
    assert "## Unknowns" in md

    # Values
    assert ctx.language == "python"
    assert ctx.frameworks == ["fastapi"]
    assert ctx.validation_library == "pydantic"
    assert ctx.orm == "sqlalchemy"
    assert ctx.database == "sqlite"
    assert ctx.test_framework == "pytest"
    assert ctx.lint_tools == ["ruff"]
    assert ctx.total_files > 0
    assert "app/main.py" in ctx.entry_candidates
    assert "pyproject.toml" in ctx.dependency_files
    assert ctx.generated_at  # ISO timestamp
    assert ctx.content_hash()

    # Markdown contains evidence
    assert "demo-api" in md
    assert "python" in md
    assert "fastapi" in md


# ── unknown project ────────────────────────────────────────────

def test_unknown_project_clearly_states_unknown(tmp_path: Path) -> None:
    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("empty-repo", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.language == "unknown"
    assert ctx.frameworks == []
    assert "**No supported technology stack detected.**" in md
    assert "Language could not be determined" in md


# ── corrupted pyproject warning ─────────────────────────────────

def test_corrupted_pyproject_warning_appears_in_document(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "{{{ not toml")
    _add_file(tmp_path, "main.py", "print('hello')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("broken-pyproject", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.parse_warnings == ["pyproject.toml could not be parsed"]
    assert "pyproject.toml could not be parsed" in md
    assert "## Scan Limits & Warnings" in md
    assert ctx.content_hash()


# ── .venv isolation ────────────────────────────────────────────

def test_venv_is_ignored_in_context(tmp_path: Path) -> None:
    _add_file(tmp_path, ".venv/lib/fastapi/__init__.py", "")
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "src/main.py", "print('hello')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("venv-test", scan, tech)

    assert ".venv" in ctx.ignored_directories
    # .venv files should NOT appear in entry_candidates
    for entry in ctx.entry_candidates:
        assert ".venv" not in entry


# ── oversized files ────────────────────────────────────────────

def test_oversized_files_recorded_not_read(tmp_path: Path) -> None:
    scanner = RepositoryScanner([tmp_path], ScanLimits(max_file_size_bytes=10))
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "small.py", "print('ok')")
    (tmp_path / "huge.py").write_bytes(b"x" * 100)
    (tmp_path / "also_big.log").write_bytes(b"y" * 200)

    scan = scanner.scan(tmp_path)
    tech = TechnologyStackDetector().detect(scan)
    ctx = _generator().generate("oversized-demo", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.oversized_files
    assert any("huge.py" in f for f in ctx.oversized_files)
    assert any("also_big.log" in f for f in ctx.oversized_files)
    assert "## Scan Limits & Warnings" in md
    assert "Oversized Files" in md


# ── multiple entry candidates ──────────────────────────────────

def test_multiple_entry_candidates_all_listed(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "api/v1/users.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _add_file(tmp_path, "api/v1/orders.py", "from fastapi import FastAPI\nrouter = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("multi-entry", scan, tech)
    md = _generator().render_markdown(ctx)

    assert len(ctx.entry_candidates) == 2
    assert "api/v1/users.py" in md
    assert "api/v1/orders.py" in md
    assert "NOT confirmed" in md  # disclaimer


# ── deterministic output ────────────────────────────────────────

def test_same_input_produces_identical_output(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi', 'pydantic']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    ctx1 = gen.generate("stable", scan, tech)
    ctx2 = gen.generate("stable", scan, tech)

    assert ctx1.content_hash() == ctx2.content_hash()

    md1 = gen.render_markdown(ctx1)
    md2 = gen.render_markdown(ctx2)
    assert md1 == md2


def test_different_project_name_changes_hash(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)

    a = _generator().generate("project-a", scan, tech)
    b = _generator().generate("project-b", scan, tech)

    assert a.content_hash() != b.content_hash()


# ── artifact path safety ───────────────────────────────────────

def test_artifact_is_written_to_controlled_directory(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print('hello')")
    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("safe-artifact", scan, tech)

    artifacts_root = tmp_path / "artifacts"
    out = _generator().write_artifact(ctx, "proj-001", artifacts_root)

    assert out.exists()
    assert out.name == "PROJECT_CONTEXT.md"
    assert out.parent == (artifacts_root / "proj-001").resolve()
    content = out.read_text()
    assert "safe-artifact" in content


@pytest.mark.parametrize("bad_id", [
    "../escape",
    "sub/../../etc",
    "..\\windows",
    "",
    "  ",
])
def test_path_escape_is_rejected(tmp_path: Path, bad_id: str) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("test", scan, tech)

    with pytest.raises(ContextGenerationError):
        _generator().write_artifact(ctx, bad_id, tmp_path / "artifacts")


# ── content hash stability ─────────────────────────────────────

def test_content_hash_is_stable(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("hash-test", scan, tech)

    h1 = ctx.content_hash()
    h2 = ctx.content_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA-256
    assert all(c in "0123456789abcdef" for c in h1)


# ── partial project (some tools missing) ───────────────────────

def test_partial_project_lists_missing_tools_as_unknowns(tmp_path: Path) -> None:
    _add_file(tmp_path, "requirements.txt", "fastapi\n")
    _add_file(tmp_path, "app.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generator().generate("partial", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.language == "python"
    assert ctx.frameworks == ["fastapi"]
    # These were not declared
    assert ctx.test_framework is None
    assert ctx.lint_tools == []
    # Unknowns section
    assert "Test framework not detected" in md
    assert "Lint tools not detected" in md
