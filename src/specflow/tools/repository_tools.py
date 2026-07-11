"""Bounded, deterministic, read-only repository Tools."""

from __future__ import annotations

import codecs
import hashlib
from pathlib import Path
from typing import Any

from specflow.tools.exceptions import BinaryFileError, RepositoryLimitError, ToolValidationError
from specflow.tools.models import ToolCall, ToolMetadata, ToolResult
from specflow.tools.registry import ToolRegistry
from specflow.tools.repository_policy import RepositoryAccessPolicy, RepositoryPolicyLimits
from specflow.tools.sanitization import sanitize_tool_text


class RepositoryToolSet:
    """Construct the three repository Tools bound to exactly one root."""

    def __init__(
        self,
        repository_root: Path,
        *,
        limits: RepositoryPolicyLimits | None = None,
    ) -> None:
        policy = RepositoryAccessPolicy(repository_root, limits)
        self._tools = (
            ListFilesTool(policy),
            SearchCodeTool(policy),
            ReadFileTool(policy),
        )

    @property
    def tools(self) -> tuple[ListFilesTool | SearchCodeTool | ReadFileTool, ...]:
        """Return the immutable tool collection in stable name order."""
        return tuple(sorted(self._tools, key=lambda tool: tool.metadata.name))

    def register_into(self, registry: ToolRegistry) -> None:
        """Explicitly register all repository Tools into a caller-owned registry."""
        for tool in self.tools:
            registry.register(tool)


class _RepositoryTool:
    def __init__(self, policy: RepositoryAccessPolicy, metadata: ToolMetadata) -> None:
        self._policy = policy
        self._metadata = metadata

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata


class ListFilesTool(_RepositoryTool):
    """List allowed repository files without reading their contents."""

    def __init__(self, policy: RepositoryAccessPolicy) -> None:
        super().__init__(
            policy,
            ToolMetadata(
                name="list_files",
                version="1.0.0",
                description="List allowed repository files in stable order.",
                input_model="ListFilesInput",
                output_model="ListFilesOutput",
                deterministic=True,
                read_only=True,
            ),
        )

    def execute(self, call: ToolCall) -> ToolResult:
        _reject_unknown_arguments(call.arguments, {"include", "exclude", "max_results"})
        include = _string_tuple(call.arguments.get("include", ()), "include")
        exclude = _string_tuple(call.arguments.get("exclude", ()), "exclude")
        max_results = _bounded_int(
            call.arguments.get("max_results", self._policy.limits.max_list_results),
            "max_results",
            self._policy.limits.max_list_results,
        )
        files: list[str] = []
        truncated = False
        for _, relative in self._policy.iter_allowed_files(include=include, exclude=exclude):
            if len(files) >= max_results:
                truncated = True
                break
            files.append(relative)
        return ToolResult.success(
            call_id=call.call_id,
            tool_name=call.tool_name,
            output={"files": files, "count": len(files), "truncated": truncated},
        )


class SearchCodeTool(_RepositoryTool):
    """Perform bounded plain-text search over allowed repository files."""

    def __init__(self, policy: RepositoryAccessPolicy) -> None:
        super().__init__(
            policy,
            ToolMetadata(
                name="search_code",
                version="1.0.0",
                description="Search allowed repository text using a literal query.",
                input_model="SearchCodeInput",
                output_model="SearchCodeOutput",
                deterministic=True,
                read_only=True,
            ),
        )

    def execute(self, call: ToolCall) -> ToolResult:
        _reject_unknown_arguments(
            call.arguments,
            {"query", "include", "exclude", "case_sensitive"},
        )
        query = _non_empty_text(call.arguments.get("query"), "query")
        if len(query) > 256:
            raise RepositoryLimitError("query exceeds 256 characters")
        include = _string_tuple(call.arguments.get("include", ()), "include")
        exclude = _string_tuple(call.arguments.get("exclude", ()), "exclude")
        case_sensitive = call.arguments.get("case_sensitive", False)
        if not isinstance(case_sensitive, bool):
            raise ToolValidationError("case_sensitive must be a boolean")

        needle = query if case_sensitive else query.casefold()
        matches: list[dict[str, object]] = []
        searched_files = 0
        truncated = False

        for _, relative in self._policy.iter_allowed_files(
            include=include,
            exclude=exclude,
        ):
            if searched_files >= self._policy.limits.max_search_files:
                truncated = True
                break
            try:
                path, _ = self._policy.resolve_file(relative)
                content, file_truncated = _read_text(
                    path,
                    self._policy.limits.max_file_bytes,
                )
            except (BinaryFileError, OSError):
                continue
            searched_files += 1
            truncated = truncated or file_truncated
            for line_number, line in enumerate(content.splitlines(), start=1):
                haystack = line if case_sensitive else line.casefold()
                count = haystack.count(needle)
                if not count:
                    continue
                excerpt = sanitize_tool_text(line.strip())[: self._policy.limits.max_excerpt_chars]
                matches.append(
                    {
                        "relative_path": relative,
                        "line_number": line_number,
                        "excerpt": excerpt,
                        "match_count": count,
                    }
                )
                if len(matches) >= self._policy.limits.max_search_matches:
                    truncated = True
                    break
            if len(matches) >= self._policy.limits.max_search_matches:
                break

        return ToolResult.success(
            call_id=call.call_id,
            tool_name=call.tool_name,
            output={
                "matches": matches,
                "searched_files": searched_files,
                "match_count": sum(int(match["match_count"]) for match in matches),
                "truncated": truncated,
            },
        )


class ReadFileTool(_RepositoryTool):
    """Read one bounded, allowed UTF-8 repository file."""

    def __init__(self, policy: RepositoryAccessPolicy) -> None:
        super().__init__(
            policy,
            ToolMetadata(
                name="read_file",
                version="1.0.0",
                description="Read one allowed repository text file with a byte limit.",
                input_model="ReadFileInput",
                output_model="ReadFileOutput",
                deterministic=True,
                read_only=True,
            ),
        )

    def execute(self, call: ToolCall) -> ToolResult:
        _reject_unknown_arguments(call.arguments, {"path"})
        requested = _non_empty_text(call.arguments.get("path"), "path")
        path, relative = self._policy.resolve_file(requested)
        content, truncated = _read_text(path, self._policy.limits.max_file_bytes)
        safe_content = _sanitize_file_content(content)
        return ToolResult.success(
            call_id=call.call_id,
            tool_name=call.tool_name,
            output={
                "relative_path": relative,
                "content": safe_content,
                "encoding": "utf-8",
                "truncated": truncated,
                "content_hash": hashlib.sha256(safe_content.encode("utf-8")).hexdigest(),
            },
        )


def _read_text(path: Path, max_bytes: int) -> tuple[str, bool]:
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    payload = data[:max_bytes]
    if b"\x00" in data:
        raise BinaryFileError("Binary repository files cannot be read")
    try:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        content = decoder.decode(payload, final=not truncated)
    except UnicodeDecodeError as exc:
        raise BinaryFileError("Repository file is not valid UTF-8 text") from exc
    return content, truncated


def _sanitize_file_content(content: str) -> str:
    """Sanitize source text while preserving its original line separators."""
    if not content:
        return ""
    sanitized: list[str] = []
    for line in content.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        line_ending = line[len(body) :]
        sanitized.append(f"{sanitize_tool_text(body)}{line_ending}")
    return "".join(sanitized)


def _non_empty_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolValidationError(f"{name} must be a non-empty string")
    return value.strip() if name != "path" else value


def _string_tuple(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or any(not isinstance(item, str) for item in value):
        raise ToolValidationError(f"{name} must be a list of strings")
    return tuple(value)


def _bounded_int(value: Any, name: str, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise RepositoryLimitError(f"{name} must be between 1 and {maximum}")
    return value


def _reject_unknown_arguments(arguments: Any, allowed: set[str]) -> None:
    unknown = sorted(set(arguments) - allowed)
    if unknown:
        raise ToolValidationError(f"Unknown Tool arguments: {', '.join(unknown)}")
