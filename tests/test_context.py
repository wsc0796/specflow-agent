from datetime import UTC, datetime
from pathlib import Path

import pytest

from specflow.context import (
    ContextGenerationError,
    ProjectContextGenerator,
    _redact_secrets,
    _sanitize_evidence,
    _sanitize_text,
    _strip_control,
)
from specflow.scanner import RepositoryScanner, ScanLimits
from specflow.technology import Evidence, TechnologyStackDetector

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
    return ctx_gen.generate(name, scan, tech, generated_at=_FIXED_TIME)


# ── normal FastAPI project ─────────────────────────────────────


def test_normal_fastapi_project_produces_complete_context(tmp_path: Path) -> None:
    _add_file(
        tmp_path,
        "pyproject.toml",
        "[project]\ndependencies = ['fastapi', 'pydantic', 'sqlalchemy', 'aiosqlite']\n"
        "[dependency-groups]\ndev = ['pytest', 'ruff']\n",
    )
    _add_file(tmp_path, "app/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _add_file(tmp_path, "app/routers/users.py", "print('ok')")
    _add_file(tmp_path, "tests/test_app.py", "def test(): pass")

    scan, tech = _scan_tech(tmp_path)
    gen = _generator()
    ctx = _generate(gen, "demo-api", scan, tech)
    md = gen.render_markdown(ctx)

    assert "## Project Overview" in md
    assert "## Detection Evidence" in md
    assert ctx.language == "python"
    assert ctx.frameworks == ["fastapi"]
    assert ctx.content_hash()
    assert ctx.source_hash()
    assert str(tmp_path) not in md


# ── unknown project ────────────────────────────────────────────


def test_unknown_project_clearly_states_unknown(tmp_path: Path) -> None:
    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "empty-repo", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.language == "unknown"
    assert "**No supported technology stack detected.**" in md


# ── corrupted pyproject warning ─────────────────────────────────


def test_corrupted_pyproject_warning_appears_in_document(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "{{{ not toml")
    _add_file(tmp_path, "main.py", "print('hello')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "broken-pyproject", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.parse_warnings == ["pyproject.toml could not be parsed"]
    assert "pyproject.toml could not be parsed" in md


# ── .venv isolation ────────────────────────────────────────────


def test_venv_is_ignored_in_context(tmp_path: Path) -> None:
    _add_file(tmp_path, ".venv/lib/fastapi/__init__.py", "")
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "src/main.py", "print('hello')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "venv-test", scan, tech)

    assert ".venv" in ctx.ignored_directories
    for entry in ctx.entry_candidates:
        assert ".venv" not in entry


# ── deterministic output ────────────────────────────────────────


def test_same_input_produces_identical_markdown(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi', 'pydantic']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    ctx1 = _generate(gen, "stable", scan, tech)
    ctx2 = _generate(gen, "stable", scan, tech)

    assert ctx1.content_hash() == ctx2.content_hash()
    assert gen.render_markdown(ctx1) == gen.render_markdown(ctx2)


def test_different_timestamps_produce_same_markdown(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    morning = gen.generate("p", scan, tech, generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    evening = gen.generate("p", scan, tech, generated_at=datetime(2026, 12, 31, tzinfo=UTC))

    assert morning.generated_at != evening.generated_at
    assert gen.render_markdown(morning) == gen.render_markdown(evening)


# ── content_hash vs source_hash (T-005.2) ──────────────────────


def test_content_hash_excludes_root_path(tmp_path: Path) -> None:
    """content_hash identifies the document, not the deployment path."""
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    # Same content, different root_path in model — content_hash matches
    ctx = _generate(gen, "p", scan, tech)
    h1 = ctx.content_hash()

    # Manually construct same content with a different root_path
    from dataclasses import replace

    ctx2 = replace(ctx, root_path="/other/path")
    h2 = ctx2.content_hash()

    assert h1 == h2  # root_path excluded from content_hash
    assert ctx.source_hash() != ctx2.source_hash()  # source_hash includes it


def test_source_hash_differs_for_different_paths(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    from dataclasses import replace

    ctx_a = _generate(gen, "p", scan, tech)
    ctx_b = replace(ctx_a, root_path="/other/path")

    assert ctx_a.content_hash() == ctx_b.content_hash()
    assert ctx_a.source_hash() != ctx_b.source_hash()


# ── evidence traceability ──────────────────────────────────────


def test_technology_evidence_preserved_in_context(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi', 'pydantic']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "evidence-demo", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.technology_evidence
    assert any(
        e.file == "pyproject.toml" and "fastapi" in e.matched for e in ctx.technology_evidence
    )
    assert "## Detection Evidence" in md


# ── absolute path is NOT in rendered markdown ──────────────────


def test_absolute_root_path_not_in_markdown(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "print('ok')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "sanitized", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.root_path
    assert "**Root:**" not in md
    assert ctx.root_path not in md


# ── markdown escaping ──────────────────────────────────────────


def test_pipe_in_project_name_does_not_break_table(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "print('ok')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "demo | staging", scan, tech)
    md = _generator().render_markdown(ctx)

    assert "demo \\| staging" in md
    for line in md.split("\n"):
        if line.startswith("|") and "demo" in line:
            assert "\\|" in line


# ── artifact path safety ───────────────────────────────────────


def test_artifact_is_written_to_controlled_directory(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print('hello')")
    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "safe-artifact", scan, tech)

    out = _generator().write_artifact(ctx, "proj-001", tmp_path / "artifacts")
    assert out.exists()
    assert out.name == "PROJECT_CONTEXT.md"


@pytest.mark.parametrize(
    "bad_id",
    [
        "../escape",
        "sub/../../etc",
        "..\\windows",
        "",
        "  ",
    ],
)
def test_path_escape_is_rejected(tmp_path: Path, bad_id: str) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "test", scan, tech)

    with pytest.raises(ContextGenerationError):
        _generator().write_artifact(ctx, bad_id, tmp_path / "artifacts")


# ── T-005.2: secret redaction ──────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected_contains,expected_absent",
    [
        (
            "https://user:pass@example.com/repo.git",
            "https://<credentials>@example.com",
            "user:pass",
        ),
        ("sk-abc123def456ghi789jkl012mno345pqr678stu", "sk-<redacted>", "abc123def"),
        ("token=ghp_abcdef123456789", "token=<redacted>", "ghp_abcdef"),
        ("api_key=secret123", "api_key=<redacted>", "secret123"),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4", "<jwt>", "eyJhbGci"),
    ],
)
def test_redact_secrets_strips_credentials(raw, expected_contains, expected_absent):
    result = _redact_secrets(raw)
    assert expected_contains in result
    assert expected_absent not in result


def test_redact_secrets_preserves_dependency_specifiers():
    """fastapi==0.115 must NOT be redacted — it's a version, not a secret."""
    result = _redact_secrets("fastapi==0.115 pydantic>=2.0")
    assert result == "fastapi==0.115 pydantic>=2.0"


def test_tainted_evidence_is_redacted_in_full_pipeline(tmp_path: Path) -> None:
    """T-005.2: inject URL credentials, API key, JWT into TechnologyStack.evidence
    and verify the full generate → render pipeline redacts them.

    The old version of this test relied on normal TechStackDetector output (no
    secrets present). This version injects real tainted Evidence and asserts
    that raw secrets are absent from both the ProjectContext model AND the
    rendered markdown.
    """
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi', 'pydantic']\n")
    _add_file(tmp_path, "main.py", "print('ok')")

    scan, tech = _scan_tech(tmp_path)

    # Inject tainted evidence that the detector would NOT normally produce
    tech.evidence.extend(
        [
            Evidence(
                file="pyproject.toml",
                matched="pkg @ https://deployer:s3cret-pass@private.repo.com/pkg.whl",
            ),
            Evidence(
                file="config.ini",
                matched="api_key=sk-proj-abc123def456ghi789jkl",
            ),
            Evidence(
                file="auth.py",
                matched="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.signed",
            ),
        ]
    )

    ctx = _generate(_generator(), "secret-test", scan, tech)
    md = _generator().render_markdown(ctx)

    # Raw secrets MUST NOT appear in the model evidence
    all_evidence_text = "|".join(f"{e.file}|{e.matched}" for e in ctx.technology_evidence)
    for secret in ["deployer:s3cret-pass", "sk-proj-abc123", "eyJhbGciOiJIUzI1NiJ9"]:
        assert secret not in all_evidence_text, f"Raw secret leaked into ProjectContext: {secret}"

    # Raw secrets MUST NOT appear in rendered markdown
    for secret in ["deployer:s3cret-pass", "sk-proj-abc123", "eyJhbGciOiJIUzI1NiJ9"]:
        assert secret not in md, f"Raw secret leaked into markdown: {secret}"

    # Redacted placeholders MUST be present
    assert "<credentials>" in md
    assert "api_key=<redacted>" in md
    assert "<jwt>" in md

    # Also verify the raw secrets aren't hiding behind redacted markers
    assert "sk-proj-abc123" not in md


# ── T-005.2: control character stripping ───────────────────────


def test_newlines_stripped_from_project_name(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)

    ctx = _generate(_generator(), "line1\nline2\r\nline3", scan, tech)
    assert "\n" not in ctx.project_name
    assert "\r" not in ctx.project_name
    assert "line1 line2 line3" in ctx.project_name


def test_tabs_stripped_from_project_name(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)

    ctx = _generate(_generator(), "proj\tname", scan, tech)
    assert "\t" not in ctx.project_name
    assert "proj name" in ctx.project_name


def test_control_characters_removed_from_warnings(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "{{{ bad")
    _add_file(tmp_path, "main.py", "print('hello')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "ctrl-warn", scan, tech)
    md = _generator().render_markdown(ctx)

    for w in ctx.parse_warnings:
        assert "\n" not in w
        assert "\r" not in w
        assert "\x00" not in w
    assert "pyproject.toml could not be parsed" in md


def test_sanitize_text_removes_null_bytes():
    assert "\x00" not in _sanitize_text("hello\x00world")


def test_sanitize_evidence_strips_control_and_secrets():
    raw = [
        Evidence(file="pyproject.toml", matched="https://user:pass@x.com\n"),
    ]
    clean = _sanitize_evidence(raw)
    assert clean[0].matched == "https://<credentials>@x.com "
    assert "\n" not in clean[0].matched


# ── T-005.2: markdown injection via newlines ────────────────────


def test_newlines_in_evidence_do_not_inject_markdown(tmp_path: Path) -> None:
    """A newline in evidence must not create fake headings or table rows."""
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "print('ok')")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "safe", scan, tech)
    md = _generator().render_markdown(ctx)

    for line in md.split("\n"):
        # No injected fake heading
        if line.startswith("#") and "Project Context" not in line and "## " not in line:
            assert not line.startswith("### injected"), f"Injected heading: {line!r}"


# ── partial project ────────────────────────────────────────────


def test_partial_project_lists_missing_tools_as_unknowns(tmp_path: Path) -> None:
    _add_file(tmp_path, "requirements.txt", "fastapi\n")
    _add_file(tmp_path, "app.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "partial", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.language == "python"
    assert ctx.test_framework is None
    assert "Test framework not detected" in md


# ── .gitignore verification ────────────────────────────────────


def test_artifacts_directory_is_gitignored():
    gitignore = Path(__file__).parent.parent / ".gitignore"
    assert "artifacts/" in gitignore.read_text()


# ── oversized files ────────────────────────────────────────────


def test_oversized_files_recorded_not_read(tmp_path: Path) -> None:
    scanner = RepositoryScanner([tmp_path], ScanLimits(max_file_size_bytes=10))
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "small.py", "print('ok')")
    (tmp_path / "huge.py").write_bytes(b"x" * 100)

    scan = scanner.scan(tmp_path)
    tech = TechnologyStackDetector().detect(scan)
    ctx = _generate(_generator(), "oversized-demo", scan, tech)
    md = _generator().render_markdown(ctx)

    assert ctx.oversized_files
    assert any("huge.py" in f for f in ctx.oversized_files)
    assert "Oversized Files" in md


# ── multiple entry candidates ──────────────────────────────────


def test_multiple_entry_candidates_all_listed(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "api/v1/users.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _add_file(tmp_path, "api/v1/orders.py", "from fastapi import FastAPI\nrouter = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "multi-entry", scan, tech)
    md = _generator().render_markdown(ctx)

    assert len(ctx.entry_candidates) == 2
    assert "api/v1/users.py" in md
    assert "api/v1/orders.py" in md


# ── different project name changes hash ────────────────────────


def test_different_project_name_changes_hash(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    a = _generate(gen, "project-a", scan, tech)
    b = _generate(gen, "project-b", scan, tech)

    assert a.content_hash() != b.content_hash()


# ── content hash stability ─────────────────────────────────────


def test_content_hash_is_stable(tmp_path: Path) -> None:
    _add_file(tmp_path, "pyproject.toml", "[project]\ndependencies = ['fastapi']\n")
    _add_file(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    scan, tech = _scan_tech(tmp_path)
    ctx = _generate(_generator(), "hash-test", scan, tech)

    assert ctx.content_hash() == ctx.content_hash()
    assert len(ctx.content_hash()) == 64


def test_different_fields_produce_different_hashes(tmp_path: Path) -> None:
    _add_file(tmp_path, "main.py", "print(1)")
    scan, tech = _scan_tech(tmp_path)
    gen = _generator()

    a = _generate(gen, "p|a", scan, tech)
    b = _generate(gen, "p", scan, tech)

    assert a.content_hash() != b.content_hash()


# ── unit tests for sanitization primitives ─────────────────────


def test_strip_control_leaves_printable_text():
    assert _strip_control("hello world") == "hello world"
    assert _strip_control("line1\nline2") == "line1 line2"


def test_strip_control_removes_null_and_bell():
    assert "\x00" not in _strip_control("a\x00b")
    assert "\x07" not in _strip_control("a\x07b")
