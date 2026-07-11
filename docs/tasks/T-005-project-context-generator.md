# T-005 — Project context generator

## Goal

Combine a T-003 `ScanResult` and a T-004 `TechnologyStack` into a structured,
evidence-backed `PROJECT_CONTEXT.md` artifact written to a controlled artifacts
directory.

## Scope

- Define a typed `ProjectContext` model.
- Implement `ProjectContextGenerator` that takes scan + technology → context.
- Render deterministic Markdown with every section backed by evidence.
- Write output to `artifacts/<project_id>/PROJECT_CONTEXT.md`.
- Reject artifact path escape attempts.

## Out of scope

No LLM, Prompt Registry, Context Builder, RAG, Worker, or database scan writes.
The generator must not re-traverse or re-read files beyond what the scan allows.

## Acceptance tests

1. A normal FastAPI project produces a complete context with all sections.
2. An unknown project clearly states "Unknown" for language and stack.
3. Corrupted pyproject warnings appear in the generated document.
4. Ignored directories and oversized files are recorded but not read.
5. Multiple entry candidates are all listed.
6. The same input always produces identical output.
7. Artifact path escape attempts are rejected.
8. Quality gate: `pytest -v`, `ruff check .`, `ruff format --check .` all pass.
