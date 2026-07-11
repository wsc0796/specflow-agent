# T-003 completion report — Safe repository scanner

## Result

Implemented a deterministic, metadata-only `RepositoryScanner`. It accepts an
explicit allowed-root policy and never reads file contents or changes database or
workflow state.

## Files changed

- `src/specflow/scanner.py`: path validation, safe traversal, ignore policy,
  metadata result types, and resource-limit errors.
- `tests/test_scanner.py`: required positive, rejection, ignore, oversized-file,
  and file-count scenarios.
- `docs/tasks/T-003-safe-repository-scanner.md`: scope and acceptance contract.
- `AGENTS.md`, `docs/00-SPEC-BASELINE.md`, and `README.md`: advance the current
  task boundary without enabling later features.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Allowed-root / resolve validation | Missing, parent-escape, and outside-root tests reject requests. |
| Ignore policy | Test confirms `.git`, `.venv`, and `node_modules` are not traversed. |
| File limits | Test raises `FileLimitExceededError` above the configured count. |
| Size limits | Test records an oversized file as metadata with its byte size. |
| Structured result | Normal scan test asserts root-relative file and directory records. |
| Quality gate | `pytest -v`: 11 passed; Ruff check and format check: passed. |

## Manual-review notes

The scanner does not expose an HTTP endpoint and does not store `ProjectScan`
records yet. Both integrations are deliberately deferred so T-003 remains only the
safe traversal capability required by the frozen task order.

## Next prerequisite

T-004 may consume the scanner's structured metadata to identify the Python/FastAPI
technology stack with evidence. It must not generate `PROJECT_CONTEXT.md`.

