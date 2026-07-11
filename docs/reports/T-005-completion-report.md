# T-005 completion report — Project context generator

## Result

Implemented `ProjectContextGenerator` that combines a T-003 `ScanResult` and
T-004 `TechnologyStack` into a deterministic, evidence-backed `PROJECT_CONTEXT.md`
artifact. The generator never re-traverses or reads files outside the safety scan
boundary.

## Revision history

| Version | Changes |
| --- | --- |
| T-005 | Initial implementation: `ProjectContext`, `ProjectContextGenerator`, 7-section Markdown, artifact writer, 16 tests |
| T-005.1 | Determinism (time-invariant markdown), evidence traceability (`## Detection Evidence`), path sanitization, JSON content_hash, markdown escaping, 22 tests |
| T-005.2 | Secret redaction (URL credentials, tokens, API keys, JWT), control-character stripping for markdown injection prevention, clarified content_hash vs source_hash semantics, 33 tests |

## T-005.2 hardening (applied 2026-07-11)

1. **Secret redaction** — `_redact_secrets()` strips URL credentials (`user:pass@host`),
   API keys (`sk-...`), JWT tokens, `token=`/`api_key=`/`secret=`/`password=` patterns.
   Applied to all Evidence before storage. Does NOT redact dependency version specifiers.
2. **Control-character stripping** — `_sanitize_text()` and `_strip_control()` remove
   `\r`, `\n`, `\t`, and C0 control characters from project_name, warnings, and evidence.
   Prevents markdown injection via embedded newlines.
3. **content_hash semantics** — `content_hash()` now excludes `root_path` (identifies
   document content). `source_hash()` = `hash(content_hash + root_path)` for project-level
   dedup across different clone paths.
4. **Sanitization happens at context creation** — `generate()` applies redaction before
   returning the `ProjectContext`, so no downstream consumer can expose raw values.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| URL credentials redacted | `user:pass@host` → `<credentials>` in output |
| API key / token redacted | `sk-xxx`, `token=xxx`, `api_key=xxx`, JWT all masked |
| Dependency specifiers preserved | `fastapi==0.115` unchanged |
| Control chars stripped from names | `\n`, `\r`, `\t`, `\x00` removed from project_name |
| Control chars stripped from warnings | Parse warnings free of control characters |
| Evidence sanitized before storage | Both file and matched fields cleaned |
| Markdown injection prevented | Newlines in evidence cannot create fake headings |
| content_hash excludes root_path | Same content, different path → same hash |
| source_hash includes root_path | Different path → different source_hash |
| Quality gate | `pytest -v`: 69 passed; `ruff check .`: passed |

## Files changed

- `src/specflow/context.py`: `_redact_secrets`, `_strip_control`, `_sanitize_evidence`,
  `_sanitize_text`, `source_hash()`, updated `content_hash()`, integrated sanitization into `generate()`.
- `tests/test_context.py`: 33 tests covering redaction, control chars, hash semantics, injection prevention.
- `.gitignore`: `artifacts/` (T-005.1).
- `docs/tasks/T-005-project-context-generator.md`: task scope.
- `AGENTS.md`, `README.md`: current task boundary.

## Next prerequisite

T-006 may begin the Prompt Registry. LLM, Context Builder, and Worker
implementations remain deferred.
