# T-004 completion report — Technology stack detector

## Result

Implemented a deterministic `TechnologyStackDetector` for the supported
Python/FastAPI stack. Every positive conclusion includes evidence from a
dependency file or source file; unsupported facts stay unknown.

T-004.1 integrated the detector with T-003 `ScanResult` via `SafeFileAccessor`
so the detector never independently traverses the filesystem.

## Delivered

- Python, FastAPI, Pydantic, SQLAlchemy, pytest, and Ruff detection from
  `pyproject.toml` and `requirements.txt` dependency declarations.
- Typed `TechnologyStack` and `Evidence` results.
- `SafeFileAccessor` — reads only files that passed T-003 safety checks
  (within allowed roots, not oversized, not in ignored directories).
- PEP 508 dependency name parsing: `~=`, `!=`, `;markers`, `[extras]`, `@url`.
- SQLite database confirmation from declared dependencies (`aiosqlite`, `sqlite`)
  only — source-code string matches no longer produce a database conclusion.
- `parse_warnings` list for corrupted `pyproject.toml` (no crash).
- FastAPI entry candidates identified via `SafeFileAccessor.python_files()`.

## Validation

| Scenario | Evidence |
| --- | --- |
| Supported pyproject stack | Detects all requested tools with dependency evidence. |
| requirements and entry candidates | Identifies entry file via safe accessor. |
| Unknown repository | Returns only unknown/empty values; no guessed stack. |
| Corrupted pyproject.toml | Produces `parse_warnings`, does not crash. |
| .venv isolation | FastAPI in `.venv` does not leak into project stack. |
| SQLite source-string | `sqlite` in code no longer produces database conclusion. |
| Version operators | `~=`, `!=`, `;markers`, `[extras]`, `@url` all parsed. |
| Oversized files | Not read by the accessor. |
| Quality gate | `pytest -v`: 13 tests; Ruff check/format: passed. |

## Scope boundary

The detector does not generate `PROJECT_CONTEXT.md`, write database scan
records, call an LLM, or infer a technology without concrete evidence.
Those capabilities remain for T-005 and later tasks.

## Revision history

| Version | Changes |
| --- | --- |
| T-004 | Initial: dependency parsing, entry scanning, technology identification. |
| T-004.1 | `SafeFileAccessor` integration, PEP 508 parsing, TOML error handling, SQLite source-string fix. |
