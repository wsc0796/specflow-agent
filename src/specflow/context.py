"""T-005 — Project context generator.

Combines a T-003 ScanResult with a T-004 TechnologyStack and renders a
deterministic, evidence-backed PROJECT_CONTEXT.md.  Never re-traverses
or reads files outside the safety scan boundary.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from specflow.scanner import ScanResult
from specflow.technology import TechnologyStack


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
    generated_at: str = ""

    def content_hash(self) -> str:
        """Stable SHA-256 digest of all context fields."""
        raw = (
            f"{self.project_name}|{self.root_path}|{self.language}|"
            f"{','.join(sorted(self.frameworks))}|"
            f"{self.validation_library}|{self.orm}|{self.database}|"
            f"{self.test_framework}|{','.join(sorted(self.lint_tools))}|"
            f"{','.join(sorted(self.dependency_files))}|"
            f"{','.join(sorted(self.entry_candidates))}|"
            f"{','.join(sorted(self.top_level_directories))}|"
            f"{self.total_files}|"
            f"{','.join(sorted(self.ignored_directories))}|"
            f"{','.join(sorted(self.oversized_files))}|"
            f"{','.join(sorted(self.parse_warnings))}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()


class ContextGenerationError(Exception):
    """Raised when the generator cannot produce a safe artifact."""


class ProjectContextGenerator:
    """Generate ProjectContext from scan + technology, render to Markdown,
    and write the artifact to a controlled directory."""

    # ── public API ──────────────────────────────────────────────

    def generate(
        self,
        project_name: str,
        scan: ScanResult,
        tech: TechnologyStack,
    ) -> ProjectContext:
        """Build a ProjectContext from a safety scan and technology stack."""
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

        return ProjectContext(
            project_name=project_name,
            root_path=scan.root,
            language=tech.language,
            frameworks=sorted(tech.frameworks),
            validation_library=tech.validation_library,
            orm=tech.orm,
            database=tech.database,
            test_framework=tech.test_framework,
            lint_tools=sorted(tech.lint_tools),
            dependency_files=sorted(tech.dependency_files),
            entry_candidates=tech.application_entry_candidates,
            top_level_directories=top_dirs,
            total_files=scan.total_files,
            ignored_directories=scan.ignored_directories,
            oversized_files=oversized,
            parse_warnings=tech.parse_warnings,
            generated_at=datetime.now(UTC).isoformat(),
        )

    def render_markdown(self, ctx: ProjectContext) -> str:
        """Render a ProjectContext to deterministic Markdown.

        Sections appear in a fixed order.  Empty lists and ``None`` values
        are represented explicitly so the output never silently omits
        information.
        """
        lines: list[str] = []
        _ = lines.append

        _("# Project Context")
        _("")
        _(f"**Project:** {ctx.project_name}")
        _(f"**Root:** {ctx.root_path}")
        _(f"**Generated:** {ctx.generated_at}")
        _("")

        # ── Project Overview ──
        _("## Project Overview")
        _("")
        _("| Field | Value |")
        _("| --- | --- |")
        _(f"| Language | {ctx.language} |")
        _(f"| Frameworks | {self._list_value(ctx.frameworks)} |")
        _(f"| Validation | {self._opt(ctx.validation_library)} |")
        _(f"| ORM | {self._opt(ctx.orm)} |")
        _(f"| Database | {self._opt(ctx.database)} |")
        _("")

        # ── Directory Summary ──
        _("## Directory Summary")
        _("")
        _(f"- **Total files (scanned):** {ctx.total_files}")
        _(f"- **Top-level directories:** {self._list_value(ctx.top_level_directories)}")
        if ctx.ignored_directories:
            _(f"- **Ignored directories:** {self._list_value(ctx.ignored_directories)}")
        if ctx.oversized_files:
            _(f"- **Oversized files (not read):** {self._list_value(ctx.oversized_files)}")
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
            _(f"| Language | {ctx.language} |")
            _(f"| Frameworks | {self._list_value(ctx.frameworks)} |")
            _(f"| Validation library | {self._opt(ctx.validation_library)} |")
            _(f"| ORM | {self._opt(ctx.orm)} |")
            _(f"| Database | {self._opt(ctx.database)} |")
            _(f"| Test framework | {self._opt(ctx.test_framework)} |")
            _(f"| Lint tools | {self._list_value(ctx.lint_tools)} |")
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
                _(f"- `{path}`")
        else:
            _("- _None detected_")
        _("")

        # ── Dependency Files ──
        _("## Dependency Files")
        _("")
        if ctx.dependency_files:
            for path in ctx.dependency_files:
                _(f"- `{path}`")
        else:
            _("- _None detected_")
        _("")

        # ── Testing & Linting ──
        _("## Testing & Linting")
        _("")
        _(f"- **Test framework:** {self._opt(ctx.test_framework)}")
        _(f"- **Lint tools:** {self._list_value(ctx.lint_tools)}")
        _("")

        # ── Scan Limits & Warnings ──
        if ctx.parse_warnings or ctx.oversized_files or ctx.ignored_directories:
            _("## Scan Limits & Warnings")
            _("")
            if ctx.parse_warnings:
                _("### Parse Warnings")
                _("")
                for w in ctx.parse_warnings:
                    _(f"- {w}")
                _("")
            if ctx.oversized_files:
                _("### Oversized Files")
                _("")
                _("The following files exceeded the size limit and were not read:")
                _("")
                for f in ctx.oversized_files:
                    _(f"- `{f}`")
                _("")
            if ctx.ignored_directories:
                _("### Ignored Directories")
                _("")
                for d in ctx.ignored_directories:
                    _(f"- `{d}`")
                _("")

        # ── Unknowns ──
        _("## Unknowns")
        _("")
        unknowns = self._collect_unknowns(ctx)
        if unknowns:
            for u in unknowns:
                _(f"- {u}")
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
