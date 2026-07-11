# Milestone 1 — Project Scanner Foundation

Date: 2026-07-11

## Delivered

- Runnable FastAPI foundation and health endpoint.
- SQLite-backed Project registration and lookup API.
- Safe, metadata-only repository traversal with allowed-root validation, resolved
  path containment, ignored directories, file-count limits, and file-size flags.
- Task specifications, completion reports, test/lint gate, and focused commits.

## User flow demonstrated

1. Register a local repository path as a Project.
2. Invoke the deterministic scanner with an explicit allowed-root policy.
3. Receive structured directory and file metadata without reading file contents.

## Validation

- `uv run pytest -v`: 11 passed.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- T-002 also received a real Uvicorn HTTP smoke test for project registration and
  lookup.

## Included commits

- `b7d1a8d` — FastAPI project foundation.
- `6677f8d` — SQLite Project registry.
- `305e246` — milestone-record and GitHub-push workflow rule.
- `3dee121` — safe repository traversal.

## Known limitations

- The scanner is a library capability; no scan HTTP endpoint or database write is
  exposed yet.
- No technology-stack identification or `PROJECT_CONTEXT.md` generation exists.
- No LLM, worker, or workflow-state behavior exists.

## Next gate

T-004 must identify only the supported Python/FastAPI stack and include concrete
evidence for every result. T-005 may then generate `PROJECT_CONTEXT.md`.

