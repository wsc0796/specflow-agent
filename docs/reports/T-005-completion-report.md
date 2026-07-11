# T-005 completion report — Project context generator

## Result

Implemented `ProjectContextGenerator` that combines a T-003 `ScanResult` and
T-004 `TechnologyStack` into a deterministic, evidence-backed `PROJECT_CONTEXT.md`
artifact. The generator never re-traverses or reads files outside the safety scan
boundary.

T-005.1 hardened determinism (time-invariant markdown), evidence traceability
(Detection Evidence section), path sanitization (no absolute paths in output),
content hash via canonical JSON, and markdown escaping.

## Files changed

- `src/specflow/context.py`: `ProjectContext` model with `technology_evidence`,
  JSON-based `content_hash`, `ProjectContextGenerator` with injected `generated_at`,
  sanitized markdown rendering, `## Detection Evidence` section, `_esc` helper.
- `tests/test_context.py`: 22 tests including time-invariance, evidence preservation,
  path sanitization, pipe escaping, hash collision protection, gitignore verification.
- `.gitignore`: added `artifacts/`.
- `docs/tasks/T-005-project-context-generator.md`: task scope and acceptance contract.
- `AGENTS.md`, `README.md`: advance current task boundary to T-005.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Normal FastAPI → complete context | 8 sections present with correct values |
| Unknown project → "Unknown" stated | `language=unknown` and warning in markdown |
| Corrupted pyproject → warning in doc | `parse_warnings` in `## Scan Limits & Warnings` |
| .venv ignored | `.venv` recorded as ignored, no leaked entries |
| Oversized files not read | Recorded in context, not content-read |
| Multiple entry candidates listed | 2 entries + disclaimer in markdown |
| Time-invariant markdown | 2 tests: same input → identical output; different timestamps → same markdown |
| Evidence preserved | `technology_evidence` field populated, `## Detection Evidence` section present |
| Absolute path NOT in markdown | `str(tmp_path)` absent; no `C:` or `Users` in output |
| Pipe in name doesn't break table | `\|` escaping verified in table rows |
| JSON-based hash | SHA-256 of canonical JSON; pipe-in-name produces different hash |
| Artifact path escape rejected | 5 parametrized `bad_id` values raise error |
| artifacts/ gitignored | `.gitignore` assertion passes |
| Quality gate | `pytest -v`: 52 passed; `ruff check .`: passed |

## T-005.1 hardening (applied 2026-07-11)

1. **Determinism** — `generated_at` removed from markdown output; injected via
   parameter in tests for reproducibility.
2. **Evidence traceability** — `technology_evidence: list[Evidence]` added to
   `ProjectContext`; `## Detection Evidence` section renders file & match pairs.
3. **Path sanitization** — absolute `root_path` kept in model for internal use
   but never rendered into markdown.
4. **artifacts/ gitignored** — prevents accidental push of generated files
   containing local paths.
5. **JSON content hash** — replaces delimiter-based string concatenation with
   `json.dumps(sort_keys=True)` to eliminate collision risk.
6. **Markdown escaping** — `_esc()` handles `|` and backtick characters in
   table values and inline code.

## Next prerequisite

T-006 may begin the Prompt Registry. LLM, Context Builder, and Worker
implementations remain deferred.
