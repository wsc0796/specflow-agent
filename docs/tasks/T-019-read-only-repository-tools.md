# T-019 - Safe Read-only Repository Tools

## Goal

Extend the completed T-018 Tool Framework with three repository-root-bound,
deterministic, read-only tools:

- `list_files`
- `search_code`
- `read_file`

This task is the current-repository equivalent of the attachment's
"T-018 Safe Read-only Repository Tools" slice. T-018 remains the already
completed framework commit; its history and contracts are not rewritten.

## Building

- A repository access policy bound to one validated root.
- Stable file listing with bounded include/exclude patterns.
- Bounded plain-text code search with line-numbered, sanitized excerpts.
- Bounded text-file reads with truncation and stable content hashes.
- Explicit registration of the three tools in a caller-owned registry.
- Cross-platform path containment, symlink/reparse-point, ignored-directory,
  sensitive-file, binary-file, and output-limit enforcement.

## Required safety behavior

1. Tool calls accept relative paths only and cannot replace the bound root.
2. `..`, absolute paths, resolved escapes, and symlink/reparse-point paths are rejected.
3. Ignored directory names are matched as path components, not substrings.
4. Sensitive files are matched by explicit names or filename patterns, not arbitrary
   substring containment.
5. `.git`, virtual environments, dependency, cache, build, and distribution
   directories are not traversed.
6. Binary files are never returned as text.
7. File bytes, scanned files, matches, excerpts, results, patterns, and tool calls
   are bounded.
8. Returned content and errors are sanitized.
9. No output contains the absolute repository root.
10. Repository tools never write to the repository.

## Contracts

`list_files` returns:

- `files`: sorted relative POSIX paths
- `count`
- `truncated`

`search_code` returns:

- `matches`: sorted records containing `relative_path`, `line_number`,
  `excerpt`, and per-line `match_count`
- `searched_files`
- `match_count`
- `truncated`

`read_file` returns:

- `relative_path`
- `content`
- `encoding`
- `truncated`
- `content_hash` for the returned sanitized content

## Not building

- File write, delete, patch, shell, subprocess, Git, test-runner, HTTP, or database tools.
- Permission Policy beyond the repository tools' mandatory safety boundary.
- Worker Tool Integration, tool selection, retries, loops, ReAct, LangGraph, RAG,
  embeddings, or automatic code modification.
- T-020 or later work.

## Validation

```powershell
uv sync --all-groups
uv run pytest tests/test_tool_framework.py -v
uv run pytest tests/test_repository_tools.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Write `docs/reports/T-019-completion-report.md`, create one focused commit, and
push it before starting T-020.
