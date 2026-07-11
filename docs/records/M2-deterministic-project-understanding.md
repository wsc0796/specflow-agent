# Milestone 2 — Deterministic Project Understanding

Date: 2026-07-11

## Goal

Extend the safe repository scanner with deterministic technology identification
and evidence-backed PROJECT_CONTEXT.md generation — still without any LLM,
Prompt, or Worker. Every conclusion must be traceable to a concrete file and
match string.

## Delivered

- Evidence-backed Python/FastAPI technology stack detection (`TechnologyStackDetector`).
- Integration with T-003 `ScanResult` via `SafeFileAccessor` — the detector
  never independently traverses the filesystem.
- PEP 508 dependency name parsing (`~=`, `!=`, `;markers`, `[extras]`, `@url`).
- Graceful handling of corrupted `pyproject.toml` (`parse_warnings`).
- `ProjectContext` model and `ProjectContextGenerator` that combines scan + tech.
- Deterministic, time-invariant `PROJECT_CONTEXT.md` with 8 structured sections.
- Evidence traceability — `## Detection Evidence` table with file/match pairs.
- Secret redaction — URL credentials, API keys, JWT, token/secret patterns
  sanitized before context storage.
- Control-character stripping — prevents markdown injection via embedded newlines.
- `content_hash` (document identity, path-independent) vs `source_hash`
  (project identity, includes deployment path).
- Artifact path-escape rejection and `artifacts/` gitignore.
- Markdown table/value escaping.

## Included commits

- `63583c5` — T-004: Python/FastAPI technology stack detection.
- `52bb98a` — T-004.1: integrate detector with safe scanner, harden edge cases.
- `5894e83` — T-005: evidence-backed PROJECT_CONTEXT.md generation.
- `9b06079` — T-005.1: determinism, evidence traceability, path sanitization.
- `924ec7d` — T-005.2: secret redaction, control-character stripping, hash semantics.

## Validation

- `uv run pytest -v`: 69 passed (14 health/API/projects, 7 scanner, 13 technology, 33 context, 2 gitignore/hash).
- `uv run ruff check .`: passed.

## Architecture result

```text
Repository Path
  → RepositoryScanner     (T-003: allowed-root, ignore, limits)
  → ScanResult
  → SafeFileAccessor      (T-004.1: enforces scan boundary)
  → TechnologyStackDetector (T-004: dependency + source analysis)
  → TechnologyStack       (evidence + parse_warnings)
  → ProjectContextGenerator (T-005: combine + sanitize + render)
  → ProjectContext         (sanitized, evidence-backed)
  → PROJECT_CONTEXT.md     (deterministic, no absolute path, no secrets)
```

## Known limitations

- No HTTP scan endpoint — scanner and detector are library capabilities.
- `ProjectScan` database records not yet written on scan.
- `ProjectContext` not yet persisted to database.
- Technology detection is limited to the supported Python/FastAPI stack.
- Entry candidates use substring matching (no AST-based comment awareness).
- The weak integration test for evidence redaction (noted in review) should be
  hardened with explicit `Evidence` injection in a future cleanup pass.

## What was deliberately excluded

No LLM, Prompt Registry, Context Builder, RAG, Worker, LangGraph, Redis, or
automatic code modification.

## Next gate

M3 — Agent Infrastructure: Prompt Registry (T-006), Context Builder (T-007),
Token Budget Manager (T-008), LLM Client (T-009), Trace (T-010),
FallbackHandler (T-011).
