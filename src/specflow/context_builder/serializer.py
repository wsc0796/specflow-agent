"""Deterministic ProjectContext serialization for prompt input."""

from __future__ import annotations

from specflow.context import ProjectContext, _redact_secrets, _strip_control


class ProjectContextSerializer:
    """Serialize ProjectContext to stable, path-free text."""

    def serialize(self, ctx: ProjectContext) -> str:
        lines: list[str] = []
        append = lines.append

        append("# Project Context")
        append("")
        append(f"project_name: {self._safe(ctx.project_name)}")
        append(f"language: {self._safe(ctx.language)}")
        append(f"frameworks: {self._list(ctx.frameworks)}")
        append(f"validation_library: {self._optional(ctx.validation_library)}")
        append(f"orm: {self._optional(ctx.orm)}")
        append(f"database: {self._optional(ctx.database)}")
        append(f"test_framework: {self._optional(ctx.test_framework)}")
        append(f"lint_tools: {self._list(ctx.lint_tools)}")
        append(f"dependency_files: {self._list(ctx.dependency_files)}")
        append(f"entry_candidates: {self._list(ctx.entry_candidates)}")
        append(f"top_level_directories: {self._list(ctx.top_level_directories)}")
        append(f"total_files: {ctx.total_files}")
        append(f"ignored_directories: {self._list(ctx.ignored_directories)}")
        append(f"oversized_files: {self._list(ctx.oversized_files)}")
        append(f"parse_warnings: {self._list(ctx.parse_warnings)}")
        append("technology_evidence:")
        for evidence in sorted(ctx.technology_evidence, key=lambda item: (item.file, item.matched)):
            append(f"- {self._safe(evidence.file)}: {self._safe(evidence.matched)}")
        if not ctx.technology_evidence:
            append("- none")

        return "\n".join(lines)

    @staticmethod
    def _optional(value: str | None) -> str:
        return ProjectContextSerializer._safe(value) if value else "not_detected"

    @staticmethod
    def _list(items: list[str]) -> str:
        if not items:
            return "none"
        return ", ".join(sorted(ProjectContextSerializer._safe(item) for item in items))

    @staticmethod
    def _safe(value: str) -> str:
        return _strip_control(_redact_secrets(value))
