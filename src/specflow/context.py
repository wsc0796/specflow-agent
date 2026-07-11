"""T-005.2 — Project context generator (security hardening).

Combines a T-003 ScanResult with a T-004 TechnologyStack and renders a
deterministic, evidence-backed PROJECT_CONTEXT.md.  Never re-traverses
or reads files outside the safety scan boundary.

T-005.2 adds:
- Evidence redaction (URL credentials, tokens, API keys)
- Control-character stripping (project_name, warnings, evidence)
- Clarified content_hash (document identity; excludes root_path)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from specflow.scanner import ScanResult
from specflow.technology import Evidence, TechnologyStack

# ── sanitization patterns ──────────────────────────────────────

# URL credentials: https://user:pass@host → https://<credentials>@host
_URL_CREDENTIALS = re.compile(r"(https?://)[^/@]+:[^/@]+@")

# Common token / key patterns
_TOKEN_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}"), "sk-<redacted>"),
    (re.compile(r"eyJ[a-zA-Z0-9_-]{12,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]*"), "<jwt>"),
    (re.compile(r"token[=:]\s*\S+", re.IGNORECASE), "token=<redacted>"),
    (re.compile(r"api_key[=:]\s*\S+", re.IGNORECASE), "api_key=<redacted>"),
    (re.compile(r"secret[=:]\s*\S+", re.IGNORECASE), "secret=<redacted>"),
    (re.compile(r"password[=:]\s*\S+", re.IGNORECASE), "password=<redacted>"),
]

# Control characters to strip (keep printable + space + common Unicode)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _redact_secrets(text: str) -> str:
    """Remove URL credentials and token patterns from *text*.

    Does NOT redact dependency version specifiers (e.g. ``fastapi==0.115``).
    """
    text = _URL_CREDENTIALS.sub(r"\1<credentials>@", text)
    for pattern, replacement in _TOKEN_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _strip_control(text: str) -> str:
    """Replace newlines/tabs with space; remove other C0 control characters."""
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    text = text.replace("\t", " ")
    return _CONTROL_RE.sub("", text)


def _sanitize_evidence(raw: list[Evidence]) -> list[Evidence]:
    """Return a copy of *raw* with secrets redacted and control chars stripped."""
    return [
        Evidence(
            file=_strip_control(_redact_secrets(e.file)),
            matched=_strip_control(_redact_secrets(e.matched)),
        )
        for e in raw
    ]


def _sanitize_text(value: str) -> str:
    """Strip control characters from a single text value."""
    return _strip_control(value)


# ── ProjectContext ─────────────────────────────────────────────

@dataclass(frozen=True)
class ProjectContext:
    """Structured, evidence-backed project context.

    Every populated section is traceable to scan metadata or technology evidence;
    empty sections are recorded explicitly rather than omitted.
    """

    project_name: str
    root_path: str
    language: str = "unknown"
    frameworks: list[str] = field(default_factory=list)
    validation_library: str | None = None
    orm: str | None = None
    database: str | None = None
    test_framework: str | None = None
    lint_tools: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    entry_candidates: list[str] = field(default_factory=list)
    top_level_directories: list[str] = field(default_factory=list)
    total_files: int = 0
    ignored_directories: list[str] = field(default_factory=list)
    oversized_files: list[str] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    technology_evidence: list[Evidence] = field(default_factory=list)
    generated_at: str = ""

    def content_hash(self) -> str:
        """SHA-256 digest of content-significant fields.

        Represents the identity of the *document content* — two contexts
        with identical content but different root_path produce the same hash.
        Excludes: root_path, generated_at (both are deployment/runtime details).
        """
        payload: dict[str, object] = {
            "project_name": self.project_name,
            "language": self.language,
            "frameworks": sorted(self.frameworks),
            "validation_library": self.validation_library,
            "orm": self.orm,
            "database": self.database,
            "test_framework": self.test_framework,
            "lint_tools": sorted(self.lint_tools),
            "dependency_files": sorted(self.dependency_files),
            "entry_candidates": sorted(self.entry_candidates),
            "top_level_directories": sorted(self.top_level_directories),
            "total_files": self.total_files,
            "ignored_directories": sorted(self.ignored_directories),
            "oversized_files": sorted(self.oversized_files),
            "parse_warnings": sorted(self.parse_warnings),
            "technology_evidence": sorted(
                f"{e.file}|{e.matched}" for e in self.technology_evidence
            ),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def source_hash(self) -> str:
        """SHA-256 of content_hash + root_path — for project-level dedup.

        Two identical repos cloned to different paths produce the same
        content_hash but different source_hash.
        """
        return hashlib.sha256(
            f"{self.content_hash()}|{self.root_path}".encode()
        ).hexdigest()


class ContextGenerationError(Exception):
    """Raised when the generator cannot produce a safe artifact."""


# ── ProjectContextGenerator ────────────────────────────────────

class ProjectContextGenerator:
    """Generate ProjectContext from scan + technology, render to Markdown,
    and write the artifact to a controlled directory."""

    # ── public API ──────────────────────────────────────────────

    def generate(
        self,
        project_name: str,
        scan: ScanResult,
        tech: TechnologyStack,
        generated_at: datetime | None = None,
    ) -> ProjectContext:
        """Build a ProjectContext from a safety scan and technology stack.

        Sanitization (secret redaction, control-character stripping) is
        applied to *project_name*, *warnings*, and *evidence* before the
        context is stored — so no downstream consumer (artifact writer or
        future LLM Context Builder) can accidentally expose raw values.
        """
        timestamp = (generated_at or datetime.now(UTC)).isoformat()
        top_dirs = sorted(
            {
                d.split("/", 1)[0]
                for d in scan.directories
                if d and "/" not in d
            }
            | {
                f.path.split("/", 1)[0]
                for f in scan.files
                if "/" in f.path
            }
        )
        oversized = sorted(
            f.path for f in scan.files if f.is_oversized
        )

        safe_name = _sanitize_text(project_name)
        safe_evidence = _sanitize_evidence(list(tech.evidence))
        safe_warnings = [_sanitize_text(w) for w in tech.parse_warnings]

        return ProjectContext(
            project_name=safe_name,
            root_path=scan.root,
            language=tech.language,
            frameworks=sorted(tech.frameworks),
            validation_library=tech.validation_library,
            orm=tech.orm,
            database=tech.database,
            test_framework=tech.test_framework,
            lint_tools=sorted(tech.lint_tools),
            dependency_files=sorted(tech.dependency_files),
            entry_candidates=sorted(tech.application_entry_candidates),
            top_level_directories=top_dirs,
            total_files=scan.total_files,
            ignored_directories=scan.ignored_directories,
            oversized_files=oversized,
            parse_warnings=safe_warnings,
            technology_evidence=safe_evidence,
            generated_at=timestamp,
        )

    def render_markdown(self, ctx: ProjectContext) -> str:
        """Render a ProjectContext to deterministic Markdown.

        Sections appear in a fixed order.  Empty lists and ``None`` values
        are represented explicitly.  The output never includes the absolute
        *root_path* or time-varying *generated_at*.
        """
        lines: list[str] = []
        _ = lines.append

        _("# Project Context")
        _("")
        _(f"**Project:** {self._esc(ctx.project_name)}")
        _("")

        # ── Project Overview ──
        _("## Project Overview")
        _("")
        _("| Field | Value |")
        _("| --- | --- |")
        _(f"| Language | {self._esc(ctx.language)} |")
        _(f"| Frameworks | {self._esc(self._list_value(ctx.frameworks))} |")
        _(f"| Validation | {self._esc(self._opt(ctx.validation_library))} |")
        _(f"| ORM | {self._esc(self._opt(ctx.orm))} |")
        _(f"| Database | {self._esc(self._opt(ctx.database))} |")
        _("")

        # ── Directory Summary ──
        _("## Directory Summary")
        _("")
        _(f"- **Total files (scanned):** {ctx.total_files}")
        _(f"- **Top-level directories:** {self._esc(self._list_value(ctx.top_level_directories))}")
        if ctx.ignored_directories:
            _(f"- **Ignored directories:** {self._esc(self._list_value(ctx.ignored_directories))}")
        if ctx.oversized_files:
            _(
                f"- **Oversized files (not read):** "
                f"{self._esc(self._list_value(ctx.oversized_files))}"
            )
        _("")

        # ── Technology Stack ──
        _("## Technology Stack")
        _("")
        if ctx.language == "unknown":
            _("**No supported technology stack detected.**")
            _("")
        else:
            _("| Component | Detected |")
            _("| --- | --- |")
            _(f"| Language | {self._esc(ctx.language)} |")
            _(f"| Frameworks | {self._esc(self._list_value(ctx.frameworks))} |")
            _(f"| Validation library | {self._esc(self._opt(ctx.validation_library))} |")
            _(f"| ORM | {self._esc(self._opt(ctx.orm))} |")
            _(f"| Database | {self._esc(self._opt(ctx.database))} |")
            _(f"| Test framework | {self._esc(self._opt(ctx.test_framework))} |")
            _(f"| Lint tools | {self._esc(self._list_value(ctx.lint_tools))} |")
            _("")

        # ── Detection Evidence ──
        _("## Detection Evidence")
        _("")
        _("_Every conclusion below is backed by a concrete file and match string._")
        _("")
        if ctx.technology_evidence:
            _("| File | Matched |")
            _("| --- | --- |")
            seen: set[tuple[str, str]] = set()
            for ev in ctx.technology_evidence:
                key = (ev.file, ev.matched)
                if key not in seen:
                    seen.add(key)
                    _(f"| `{self._esc(ev.file)}` | `{self._esc(ev.matched)}` |")
        else:
            _("- _No detection evidence recorded_")
        _("")

        # ── Application Entry Candidates ──
        _("## Application Entry Candidates")
        _("")
        _(
            "_These files contain `FastAPI(` and are candidates. "
            "They are NOT confirmed application entry points._"
        )
        _("")
        if ctx.entry_candidates:
            for path in ctx.entry_candidates:
                _(f"- `{self._esc(path)}`")
        else:
            _("- _None detected_")
        _("")

        # ── Dependency Files ──
        _("## Dependency Files")
        _("")
        if ctx.dependency_files:
            for path in ctx.dependency_files:
                _(f"- `{self._esc(path)}`")
        else:
            _("- _None detected_")
        _("")

        # ── Testing & Linting ──
        _("## Testing & Linting")
        _("")
        _(f"- **Test framework:** {self._esc(self._opt(ctx.test_framework))}")
        _(f"- **Lint tools:** {self._esc(self._list_value(ctx.lint_tools))}")
        _("")

        # ── Scan Limits & Warnings ──
        if ctx.parse_warnings or ctx.oversized_files or ctx.ignored_directories:
            _("## Scan Limits & Warnings")
            _("")
            if ctx.parse_warnings:
                _("### Parse Warnings")
                _("")
                for w in ctx.parse_warnings:
                    _(f"- {self._esc(w)}")
                _("")
            if ctx.oversized_files:
                _("### Oversized Files")
                _("")
                _("The following files exceeded the size limit and were not read:")
                _("")
                for f in ctx.oversized_files:
                    _(f"- `{self._esc(f)}`")
                _("")
            if ctx.ignored_directories:
                _("### Ignored Directories")
                _("")
                for d in ctx.ignored_directories:
                    _(f"- `{self._esc(d)}`")
                _("")

        # ── Unknowns ──
        _("## Unknowns")
        _("")
        unknowns = self._collect_unknowns(ctx)
        if unknowns:
            for u in unknowns:
                _(f"- {self._esc(u)}")
        else:
            _("- _All supported dimensions were detected._")
        _("")

        return "\n".join(lines)

    def write_artifact(
        self,
        ctx: ProjectContext,
        project_id: str,
        artifacts_root: Path,
    ) -> Path:
        """Write PROJECT_CONTEXT.md into ``artifacts/<project_id>/``.

        Raises ``ContextGenerationError`` if *project_id* attempts path escape.
        """
        safe_id = project_id.strip()
        if not safe_id or ".." in safe_id or "/" in safe_id or "\\" in safe_id:
            raise ContextGenerationError(
                f"Invalid project_id for artifact path: {project_id!r}"
            )

        target_dir = (artifacts_root / safe_id).resolve()
        try:
            target_dir.relative_to(artifacts_root.resolve())
        except ValueError:
            raise ContextGenerationError(
                f"Artifact path escapes root: {project_id!r}"
            )

        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / "PROJECT_CONTEXT.md"
        output_path.write_text(self.render_markdown(ctx), encoding="utf-8")
        return output_path

    # ── helpers ─────────────────────────────────────────────────

    @staticmethod
    def _opt(value: str | None) -> str:
        return value if value else "_Not detected_"

    @staticmethod
    def _list_value(items: list[str]) -> str:
        if not items:
            return "_None_"
        return ", ".join(items)

    @staticmethod
    def _esc(value: str) -> str:
        """Escape ``|`` and backticks so values don't break Markdown tables."""
        return value.replace("|", "\\|").replace("`", "\\`")

    @staticmethod
    def _collect_unknowns(ctx: ProjectContext) -> list[str]:
        unknowns: list[str] = []
        if ctx.language == "unknown":
            unknowns.append("Language could not be determined")
        if not ctx.frameworks:
            unknowns.append("No supported framework detected")
        if not ctx.validation_library:
            unknowns.append("Validation library not detected")
        if not ctx.orm:
            unknowns.append("ORM not detected")
        if not ctx.database:
            unknowns.append("Database not detected")
        if not ctx.test_framework:
            unknowns.append("Test framework not detected")
        if not ctx.lint_tools:
            unknowns.append("Lint tools not detected")
        if not ctx.entry_candidates:
            unknowns.append("No FastAPI entry candidates found")
        return unknowns
