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
- `b60dd7a` — M2 closure: updated T-004 report, hardened evidence redaction test.

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

## User flow

```text
Local Repository
  → RepositoryScanner          (T-003: path validation, allowed-root enforce,
  → ScanResult                    ignore policy, file/size limits)
  → SafeFileAccessor           (T-004.1: reads only files that passed safety scan)
  → TechnologyStackDetector    (T-004: dependency parsing + source analysis)
  → TechnologyStack + Evidence (every conclusion backed by file + match string)
  → ProjectContextGenerator    (T-005: combine scan + tech into structured model)
  → Secret Redaction           (T-005.2: strip URL credentials, API keys, JWTs)
  → Sanitization               (T-005.2: strip control characters from all text)
  → PROJECT_CONTEXT.md         (T-005.1: deterministic, time-invariant, no abs path)
  → content_hash               (T-005.1: JSON-based, path-independent)
  → source_hash                (T-005.2: content_hash + root_path for dedup)
```

The system can now register a project via the HTTP API, safely scan its
repository, identify the Python/FastAPI technology stack, and produce a
deterministic, evidence-backed, sanitized `PROJECT_CONTEXT.md` — all without
calling an LLM.

## Known limitations

- No HTTP scan endpoint — scanner and detector are library capabilities.
- `ProjectScan` database records not yet written on scan.
- `ProjectContext` not yet persisted to database.
- Technology detection is limited to the supported Python/FastAPI stack.
- Entry candidates use substring matching (no AST-based comment awareness).
- End-to-end evidence-redaction test hardened with explicit tainted `Evidence`
  injection (URL credentials, API key, JWT) in `b60dd7a`.

## What was deliberately excluded

No LLM, Prompt Registry, Context Builder, RAG, Worker, LangGraph, Redis, or
automatic code modification.

## Next gate

M3 — Agent Infrastructure: Prompt Registry (T-006), Context Builder (T-007),
Token Budget Manager (T-008), LLM Client (T-009), Trace (T-010),
FallbackHandler (T-011).
