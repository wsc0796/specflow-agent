# T-019 completion report - Safe Read-only Repository Tools

## Result

Implemented three real repository Tools on top of the frozen T-018 Tool
Framework:

- `list_files`
- `search_code`
- `read_file`

The tools are explicitly registered, bound to one repository root at
construction, deterministic, bounded, sanitized, and read-only.

## Numbering note

The M5 execution attachment called this combined framework/tool slice T-018.
The repository had already completed and pushed T-018 Tool Framework before the
attachment was applied. This task therefore keeps immutable history and records
the real repository tools as T-019. The attachment's later task numbers are
mapped forward from this point.

## Architecture

```text
ToolCall
  -> ToolExecutor
  -> explicit ToolRegistry
  -> RepositoryToolSet
       -> RepositoryAccessPolicy (one validated root)
       -> list_files
       -> search_code
       -> read_file
```

`RepositoryAccessPolicy` owns path containment, symlink/reparse-point rejection,
ignored directories, sensitive filename rules, glob validation, and hard limits.
The three Tools own their operation-specific input and output contracts.

## Safety behavior

- Only relative repository paths are accepted.
- Parent traversal, absolute paths, resolved escapes, and links/reparse points
  are rejected.
- Dependency, cache, Git, build, and distribution directories are pruned.
- Sensitive files use explicit names and filename patterns rather than arbitrary
  substring checks.
- Binary and non-UTF-8 files are not returned as text.
- Listing, searching, file reads, patterns, excerpts, matches, and scan size are
  bounded.
- Source text is redacted while retaining line structure.
- Outputs contain repository-relative paths, never the bound absolute root.
- No subprocess, shell, write, delete, Git, HTTP, database, Worker, or Tool-loop
  behavior was added.

## Tests

`tests/test_repository_tools.py` adds 37 cases covering stable listing,
include/exclude filters, truncation, ignored and sensitive paths, literal search,
line numbers, secret redaction, binary skipping, bounded matches, safe reads,
stable hashes, traversal and absolute path rejection, POSIX symlink escape,
cross-platform reparse-point boundary logic, missing roots, no subprocess use,
and repository immutability.

The existing 29 T-018 Tool Framework tests remain unchanged and pass.

## Quality gates

- `uv sync --all-groups`: passed.
- `uv run pytest tests/test_tool_framework.py -v`: 29 passed.
- `uv run pytest tests/test_repository_tools.py -v`: 36 passed, 1 skipped.
- `uv run pytest -v`: 319 passed, 2 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 86 files already formatted.
- `git diff --check`: passed.

The skipped test is the POSIX symlink integration case because creating symlinks
can require elevated privileges on Windows. A separate policy-level
reparse-point test executes on Windows and is not skipped.

The existing warning is a third-party FastAPI/Starlette `TestClient`
deprecation warning and is unchanged by T-019.

## Known limitations

- Search supports bounded literal text only, not regex.
- Text decoding is UTF-8 only.
- Content hashes identify returned sanitized content; a truncated hash does not
  identify unread bytes.
- Tools do not select themselves, retry, loop, call Workers, or change workflow
  state.
- There are no write, shell, Git, or automatic code-modification tools.

## Next task

T-020 OpenAI-compatible LLM Provider is the next permitted task. No T-020 code
is included in this task.
