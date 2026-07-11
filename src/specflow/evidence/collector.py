"""Bounded, deterministic evidence collector using repository tools."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from specflow.evidence.exceptions import EvidenceLimitError
from specflow.evidence.keywords import extract_keywords
from specflow.evidence.models import (
    EvidenceBundle,
    EvidenceCollectionConfig,
    EvidenceExcerpt,
    ToolCallRecord,
)
from specflow.tools import ToolCall, ToolExecutor, ToolStatus
from specflow.tools.sanitization import sanitize_tool_text


class EvidenceCollector:
    """Collect repository evidence using registered read-only tools."""

    def __init__(
        self,
        executor: ToolExecutor,
        repository_root: Path,
        *,
        config: EvidenceCollectionConfig | None = None,
    ) -> None:
        self._executor = executor
        self._root = repository_root
        self._config = config or EvidenceCollectionConfig()
        self._records: list[ToolCallRecord] = []
        self._call_counter = 0

    @property
    def tool_call_records(self) -> tuple[ToolCallRecord, ...]:
        """Return recorded tool calls."""
        return tuple(self._records)

    def collect(
        self,
        *,
        run_id: str,
        requirement: str,
        project_summary: str = "",
        technology_stack: tuple[str, ...] = (),
    ) -> EvidenceBundle:
        """Collect repository evidence for a requirement."""
        warnings: list[str] = []
        keywords = extract_keywords(
            requirement,
            max_keywords=self._config.max_search_keywords,
            technology_hints=technology_stack,
        )

        files_output = self._execute_tool(
            "list_files", {"include": ["*.py", "*.md", "*.yaml", "*.yml", "*.toml", "*.cfg"]}
        )
        all_matches: list[dict[str, Any]] = []
        searched_files: set[str] = set()
        total_searched = 0
        truncated = bool(files_output.get("truncated", False))

        for keyword in keywords[: self._config.max_search_keywords]:
            if self._call_counter >= self._config.max_tool_calls:
                warnings.append("Tool call limit reached during search")
                truncated = True
                break
            search_result = self._execute_tool(
                "search_code",
                {"query": keyword, "include": ["*.py"], "case_sensitive": False},
            )
            if search_result is None:
                continue
            matches: list[dict[str, Any]] = list(search_result.get("matches", []))
            for match in matches:
                path = str(match.get("relative_path", ""))
                searched_files.add(path)
                all_matches.append(match)
            total_searched += int(search_result.get("searched_files", 0))
            if search_result.get("truncated"):
                truncated = True

        matched_files = sorted(searched_files)

        selected_files = self._rank_files(matched_files, all_matches)[
            : self._config.max_selected_files
        ]

        excerpts: list[EvidenceExcerpt] = []
        source_hashes: dict[str, str] = {}
        for path in selected_files:
            if self._call_counter >= self._config.max_tool_calls:
                warnings.append("Tool call limit reached during file reads")
                truncated = True
                break
            read_result = self._execute_tool("read_file", {"path": path})
            if read_result is None:
                continue
            content_hash = str(read_result.get("content_hash", ""))
            source_hashes[path] = content_hash
            if read_result.get("truncated"):
                truncated = True
                warnings.append(f"File truncated: {path}")

            for match in all_matches:
                if match.get("relative_path") == path:
                    excerpts.append(
                        EvidenceExcerpt(
                            relative_path=path,
                            line_number=int(match.get("line_number", 1)),
                            excerpt=str(match.get("excerpt", "")),
                            match_count=int(match.get("match_count", 1)),
                        )
                    )

        total_chars = sum(len(e.excerpt) for e in excerpts)
        if total_chars > self._config.max_total_evidence_chars:
            truncated = True
            warnings.append("Total evidence exceeds character limit")

        bundle = EvidenceBundle(
            run_id=run_id,
            requirement=requirement,
            repository_root=str(self._root.resolve()),
            project_summary=project_summary,
            technology_stack=technology_stack,
            searched_terms=keywords,
            matched_files=tuple(matched_files),
            selected_files=tuple(selected_files),
            excerpts=tuple(excerpts[: self._config.max_search_matches]),
            source_hashes=source_hashes,
            tool_call_records=tuple(self._records),
            truncated=truncated,
            warnings=tuple(warnings),
        )
        return bundle

    def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """Execute one tool call and record it."""
        if self._call_counter >= self._config.max_tool_calls:
            raise EvidenceLimitError("Tool call limit exceeded")
        self._call_counter += 1
        call_id = f"evidence-{self._call_counter:03d}"
        started = perf_counter()
        call = ToolCall.build(call_id=call_id, tool_name=tool_name, arguments=arguments)
        result = self._executor.execute(call)
        duration_ms = max(0, int((perf_counter() - started) * 1000))

        args_summary = ", ".join(
            f"{k}={sanitize_tool_text(str(v))[:80]}" for k, v in sorted(arguments.items())
        )

        if result.status == ToolStatus.SUCCESS:
            output_summary = f"ok, {len(str(result.output))} chars"
            self._records.append(
                ToolCallRecord(
                    call_id=call_id,
                    tool_name=tool_name,
                    status="success",
                    arguments_summary=args_summary,
                    output_summary=output_summary,
                    duration_ms=duration_ms,
                    truncated=bool(result.output.get("truncated", False)),
                )
            )
            return dict(result.output)
        else:
            self._records.append(
                ToolCallRecord(
                    call_id=call_id,
                    tool_name=tool_name,
                    status="failed",
                    arguments_summary=args_summary,
                    output_summary=str(result.error_type or "unknown"),
                    duration_ms=duration_ms,
                    error_type=result.error_type,
                )
            )
            return None

    @staticmethod
    def _rank_files(
        files: list[str],
        matches: list[dict[str, Any]],
    ) -> list[str]:
        """Rank files by match count and path relevance, with stable tie-breaking."""
        scores: dict[str, int] = {}
        for match in matches:
            path = str(match.get("relative_path", ""))
            count = int(match.get("match_count", 1))
            scores[path] = scores.get(path, 0) + count

        def sort_key(path: str) -> tuple[int, int, str]:
            score = -scores.get(path, 0)
            priority = 0
            lowered = path.lower()
            if "src" in lowered.split("/"):
                priority -= 1
            if any(
                segment in lowered
                for segment in ["service", "model", "api", "route", "schema", "controller"]
            ):
                priority -= 1
            return (priority, score, path)

        return sorted(files, key=sort_key)
