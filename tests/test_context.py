from datetime import UTC, datetime
from pathlib import Path

import pytest

from specflow.context import (
    ContextGenerationError,
    ProjectContextGenerator,
)
from specflow.scanner import RepositoryScanner, ScanLimits
from specflow.technology import TechnologyStackDetector

# ── test-time constant ─────────────────────────────────────────
_FIXED_TIME = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)


# ── helpers ────────────────────────────────────────────────────

def _add_file(base: Path, relative: str, content: str = "") -> None:
    full = base / relative
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def _scan_tech(tmp_path: Path):
    scan = RepositoryScanner([tmp_path], ScanLimits()).scan(tmp_path)
    tech = TechnologyStackDetector().detect(scan)
    return scan, tech


def _generator() -> ProjectContextGenerator:
    return ProjectContextGenerator()


def _generate(ctx_gen, name, scan, tech):
    """Shortcut with fixed time for determinism."""
    return ctx_gen.generate(name, scan, tech, generated_at=_FIXED_TIME)


# ── normal FastAPI project ─────────────────────────────────────

def test_normal_fastapi_project_produces_complete_context(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi', 'pydantic', 'sqlalchemy', 'aiosqlite']\n"
              "[dependency-groups]\ndev = ['pytest', 'ruff']\n")
    _add_file(tmp_path, "app/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _add_file(tmp_path, "app/routers/users.py", "print('ok')")
    _add_file(tmp_path, "tests/test_app.py", "def test(): pass")

    scan, tech = _scan_tech(tmp_path)
    gen = _generator()
    ctx = _generate(gen, "demo-api", scan, tech)
    md = gen.render_markdown(ctx)

    # All sections present
    assert "## Project Overview" in md
    assert "## Directory Summary" in md
    assert "## Technology Stack" in md
    assert "## Detection Evidence" in md
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
    assert ctx.generated_at
    assert ctx.content_hash()

    # Markdown contains evidence but NOT the absolute path
    assert "demo-api" in md
    assert "python" in md
    assert "fastapi" in md
    assert str(tmp_path) not in md


# ── unknown project ────────────────────────────────────────────

def test_unknown_project_clearly_states_unknown(tmp_path: Path) -> None:
    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "empty-repo", scan, tech)
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
    ctx = _generate(_generator(), "broken-pyproject", scan, tech)
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
    ctx = _generate(_generator(), "venv-test", scan, tech)

    assert ".venv" in ctx.ignored_directories
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
    ctx = _generate(_generator(), "oversized-demo", scan, tech)
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
    ctx = _generate(_generator(), "multi-entry", scan, tech)
    md = _generator().render_markdown(ctx)

    assert len(ctx.entry_candidates) == 2
    assert "api/v1/users.py" in md
    assert "api/v1/orders.py" in md
    assert "NOT confirmed" in md


# ── deterministic output (T-005.1: time-invariant) ─────────────

def test_same_input_produces_identical_markdown(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi', 'pydantic']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    ctx1 = _generate(gen, "stable", scan, tech)
    ctx2 = _generate(gen, "stable", scan, tech)

    assert ctx1.content_hash() == ctx2.content_hash()
    assert gen.render_markdown(ctx1) == gen.render_markdown(ctx2)


def test_different_timestamps_produce_same_markdown(tmp_path: Path) -> None:
    """T-005.1: generated_at is stored on the model but NOT rendered into markdown."""
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    morning = gen.generate("p", scan, tech, generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    evening = gen.generate("p", scan, tech, generated_at=datetime(2026, 12, 31, tzinfo=UTC))

    assert morning.generated_at != evening.generated_at
    assert gen.render_markdown(morning) == gen.render_markdown(evening)


def test_different_project_name_changes_hash(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    a = _generate(gen, "project-a", scan, tech)
    b = _generate(gen, "project-b", scan, tech)

    assert a.content_hash() != b.content_hash()


# ── evidence traceability (T-005.1) ────────────────────────────

def test_technology_evidence_preserved_in_context(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi', 'pydantic']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "evidence-demo", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.technology_evidence
    assert any(e.file == "pyproject.toml" and "fastapi" in e.matched
               for e in ctx.technology_evidence)

    assert "## Detection Evidence" in md
    assert "pyproject.toml" in md
    assert "fastapi" in md  # appears in evidence table


# ── absolute path is NOT in rendered markdown (T-005.1) ────────

def test_absolute_root_path_not_in_markdown(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "print('ok')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "sanitized", scan, tech)
    md = _generator().render_markdown(ctx)

    # Model keeps the full path for internal use
    assert ctx.root_path
    # Rendered markdown must NOT leak it
    assert "**Root:**" not in md
    assert ctx.root_path not in md
    # Backslashes from Windows paths should not appear
    assert "C:" not in md
    assert "Users" not in md


# ── artifact path safety ───────────────────────────────────────

def test_artifact_is_written_to_controlled_directory(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print('hello')")
    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "safe-artifact", scan, tech)

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
    ctx = _generate(_generator(), "test", scan, tech)

    with pytest.raises(ContextGenerationError):
        _generator().write_artifact(ctx, bad_id, tmp_path / "artifacts")


# ── content hash via JSON (T-005.1) ────────────────────────────

def test_content_hash_is_stable(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "hash-test", scan, tech)

    h1 = ctx.content_hash()
    h2 = ctx.content_hash()
    assert h1 == h2
    assert len(h1) == 64


def test_different_fields_produce_different_hashes(tmp_path: Path) -> None:
    """T-005.1: field combinations must not collide via delimiter ambiguity."""
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    a = _generate(gen, "p|a", scan, tech)    # name with pipe
    b = _generate(gen, "p", scan, tech)      # plain name

    assert a.content_hash() != b.content_hash()


# ── markdown escaping (T-005.1) ────────────────────────────────

def test_pipe_in_project_name_does_not_break_table(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml",
              "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "print('ok')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "demo | staging", scan, tech)
    md = _generator().render_markdown(ctx)

    # The pipe must be escaped so the table stays intact
    assert "demo \\| staging" in md
    # The markdown should still be well-formed (no raw pipe in table value)
    lines = md.split("\n")
    for line in lines:
        if line.startswith("|") and "demo" in line:
            # Should contain escaped pipe, not raw `| demo |`
            assert "\\|" in line


# ── partial project ────────────────────────────────────────────

def test_partial_project_lists_missing_tools_as_unknowns(tmp_path: Path) -> None:
    _add_file(tmp_path, "requirements.txt", "fastapi\n")
    _add_file(tmp_path, "app.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "partial", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.language == "python"
    assert ctx.frameworks == ["fastapi"]
    assert ctx.test_framework is None
    assert ctx.lint_tools == []
    assert "Test framework not detected" in md
    assert "Lint tools not detected" in md


# ── .gitignore verification (T-005.1) ──────────────────────────

def test_artifacts_directory_is_gitignored() -> None:
    """T-005.1: artifacts/ must be listed in .gitignore to prevent
    accidental push of generated files containing local paths."""
    gitignore = Path(__file__).parent.parent / ".gitignore"
    content = gitignore.read_text()
    assert "artifacts/" in content
