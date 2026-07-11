"""Evidence collection models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from specflow.evidence.exceptions import EvidenceCollectionError
from specflow.tools.sanitization import sanitize_tool_text


@dataclass(frozen=True)
class EvidenceExcerpt:
    """One bounded, sanitized excerpt from a repository file."""

    relative_path: str
    line_number: int
    excerpt: str
    match_count: int = 1

    def __post_init__(self) -> None:
        if not self.relative_path.strip():
            raise EvidenceCollectionError("EvidenceExcerpt.relative_path must not be empty")
        if self.line_number < 1:
            raise EvidenceCollectionError("EvidenceExcerpt.line_number must be positive")
        if self.match_count < 1:
            raise EvidenceCollectionError("EvidenceExcerpt.match_count must be positive")


@dataclass(frozen=True)
class ToolCallRecord:
    """Sanitized record of one tool execution."""

    call_id: str
    tool_name: str
    status: str
    arguments_summary: str
    output_summary: str
    duration_ms: int
    truncated: bool = False
    error_type: str | None = None

    def __post_init__(self) -> None:
        if not self.call_id.strip():
            raise EvidenceCollectionError("ToolCallRecord.call_id must not be empty")
        if not self.tool_name.strip():
            raise EvidenceCollectionError("ToolCallRecord.tool_name must not be empty")
        if self.status not in {"success", "failed"}:
            raise EvidenceCollectionError("ToolCallRecord.status must be success or failed")
        if self.duration_ms < 0:
            raise EvidenceCollectionError("ToolCallRecord.duration_ms must not be negative")


@dataclass(frozen=True)
class EvidenceCollectionConfig:
    """Bounded configuration for evidence collection."""

    max_search_keywords: int = 10
    max_search_matches: int = 100
    max_selected_files: int = 5
    max_file_bytes: int = 262_144
    max_total_evidence_chars: int = 50_000
    max_tool_calls: int = 30
    max_excerpt_chars: int = 240

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise EvidenceCollectionError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class EvidenceBundle:
    """Complete, deterministic evidence bundle for one repository analysis."""

    run_id: str
    requirement: str
    repository_root: str
    project_summary: str = ""
    technology_stack: tuple[str, ...] = ()
    searched_terms: tuple[str, ...] = ()
    matched_files: tuple[str, ...] = ()
    selected_files: tuple[str, ...] = ()
    excerpts: tuple[EvidenceExcerpt, ...] = ()
    source_hashes: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))
    tool_call_records: tuple[ToolCallRecord, ...] = ()
    truncated: bool = False
    warnings: tuple[str, ...] = ()
    evidence_hash: str = ""

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise EvidenceCollectionError("EvidenceBundle.run_id must not be empty")
        if not self.requirement.strip():
            raise EvidenceCollectionError("EvidenceBundle.requirement must not be empty")
        if not self.repository_root.strip():
            raise EvidenceCollectionError("EvidenceBundle.repository_root must not be empty")
        for excerpt in self.excerpts:
            if not isinstance(excerpt, EvidenceExcerpt):
                raise EvidenceCollectionError(
                    "EvidenceBundle.excerpts must contain EvidenceExcerpt"
                )
        for record in self.tool_call_records:
            if not isinstance(record, ToolCallRecord):
                raise EvidenceCollectionError("ToolCallRecord must be ToolCallRecord")
        if not self.evidence_hash:
            object.__setattr__(self, "evidence_hash", self._calculate_hash())

    def serialized_context(self) -> str:
        """Return evidence as a bounded text block for prompt injection."""
        parts: list[str] = []
        parts.append("## Repository Evidence\n")
        parts.append(f"Project summary: {sanitize_tool_text(self.project_summary)}")
        if self.technology_stack:
            parts.append(f"Technology: {', '.join(self.technology_stack)}")
        if self.searched_terms:
            parts.append(f"Searched: {', '.join(self.searched_terms)}")
        parts.append(f"Matched files: {len(self.matched_files)}")
        parts.append("")
        for excerpt in self.excerpts:
            parts.append(
                f"- {excerpt.relative_path}:{excerpt.line_number} "
                f"`{sanitize_tool_text(excerpt.excerpt)}`"
            )
        if self.truncated:
            parts.append("\n[Evidence collection was truncated]")
        if self.warnings:
            parts.append("\nWarnings:")
            for warning in self.warnings:
                parts.append(f"- {sanitize_tool_text(warning)}")
        return "\n".join(parts)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable mapping."""
        return {
            "run_id": self.run_id,
            "requirement": sanitize_tool_text(self.requirement),
            "repository_root": self.repository_root,
            "project_summary": sanitize_tool_text(self.project_summary),
            "technology_stack": list(self.technology_stack),
            "searched_terms": list(self.searched_terms),
            "matched_files": list(self.matched_files),
            "selected_files": list(self.selected_files),
            "excerpts": [
                {
                    "relative_path": e.relative_path,
                    "line_number": e.line_number,
                    "excerpt": sanitize_tool_text(e.excerpt),
                    "match_count": e.match_count,
                }
                for e in self.excerpts
            ],
            "source_hashes": dict(self.source_hashes),
            "tool_call_records": [
                {
                    "call_id": r.call_id,
                    "tool_name": r.tool_name,
                    "status": r.status,
                    "arguments_summary": sanitize_tool_text(r.arguments_summary),
                    "output_summary": sanitize_tool_text(r.output_summary),
                    "duration_ms": r.duration_ms,
                    "truncated": r.truncated,
                    "error_type": r.error_type,
                }
                for r in self.tool_call_records
            ],
            "truncated": self.truncated,
            "warnings": [sanitize_tool_text(w) for w in self.warnings],
            "evidence_hash": self.evidence_hash,
        }

    def _calculate_hash(self) -> str:
        payload = {
            "matched_files": sorted(self.matched_files),
            "selected_files": sorted(self.selected_files),
            "searched_terms": sorted(self.searched_terms),
            "excerpts": sorted((e.relative_path, e.line_number, e.excerpt) for e in self.excerpts),
            "truncated": self.truncated,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
