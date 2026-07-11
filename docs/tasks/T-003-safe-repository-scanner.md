# T-003 — Safe repository scanner

## Goal

Safely enumerate metadata beneath an explicitly allowed local repository root.

## Scope

- Resolve and validate the requested root against configured allowed roots.
- Reject missing paths, path traversal, and locations outside those roots.
- Skip `.git`, `.venv`, and `node_modules` directories.
- Enforce maximum file count and per-file size limits.
- Return a structured, content-free scan result.

## Out of scope

No database writes, HTTP endpoint, technology detection, context generation, LLM,
workflow state changes, or reading file contents. Symlinks resolving outside the
repository are skipped.

## Input and output

`RepositoryScanner(allowed_roots, limits).scan(requested_root)` accepts a path and
returns its resolved root, files (relative path, size, and oversized flag),
directories, ignored directories, and total file count. Rejected paths and file
count overflow raise explicit scanner errors.

## Acceptance tests

1. A normal repository returns structured files and directories.
2. A missing path is rejected.
3. A `..` request resolving outside the allowed root is rejected.
4. A repository path outside an allowed root is rejected.
5. `.git`, `.venv`, and `node_modules` are excluded and recorded as ignored.
6. An oversized file is represented as metadata without content access.
7. More than the configured file limit is rejected.

