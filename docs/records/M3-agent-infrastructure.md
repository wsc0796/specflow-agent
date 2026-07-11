# Milestone 3 - Agent Infrastructure

## Status

Completed.

Milestone 3 establishes the Agent runtime foundation without starting Agent
Workflow implementation. The system now has deterministic prompt assets,
context assembly, token budgeting, provider-neutral LLM request/response
contracts, metadata-only tracing, and explicit fallback behavior.

## Completed capabilities

- T-006 Prompt Registry
  - File-based prompt definitions.
  - Prompt metadata and version isolation.
  - Strict rendering and template-variable validation.
  - Stable prompt hashes.
- T-007 Context Builder
  - Deterministic `BuiltContext` assembly.
  - Project context, prompt definition, and user requirement composition.
  - Stable context hashes and source tracking.
  - Existing context redaction preserved.
- T-008 Token Budget Manager
  - Deterministic token estimation.
  - Budget policy enforcement.
  - Priority-based trimming.
  - `removed_sections` tracking.
  - Stable budgeted context hashes.
- T-009 LLM Client
  - Provider-neutral LLM request/response models.
  - Deterministic mock client.
  - Explicit runtime exceptions.
  - No network provider SDK integration.
- T-010 Trace System
  - Metadata-only LLM traces.
  - Stable JSON trace storage.
  - Success and failure trace records.
  - No prompt, response, or secret content persisted.
- T-011 Fallback System
  - Bounded retry strategy.
  - JSON repair strategy.
  - Honest rule-baseline degraded output.
  - `FallbackResult` model.
  - Trace metadata fields for `fallback_level` and `retry_count`.

## Git commits

- `ce5f042` - `feat(prompts): add prompt registry`
- `bb07514` - `feat(context): add deterministic context builder`
- `5e9be6d` - `feat(budget): add token budget manager`
- `7205aac` - `feat(llm): add llm client abstraction`
- `8186322` - `feat(trace): add llm execution tracing`
- `0b7c251` - `docs(record): complete llm runtime foundation checkpoint`
- `85965e0` - `feat(fallback): add fallback strategy system`

## Validation

Final validation after T-011:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Result:

- `uv run pytest -v`: 135 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 49 files already formatted.

The skipped test is the existing Windows directory-symlink integration test,
which requires administrator privileges. A non-skipped Windows containment
boundary test remains in the scanner suite.

## Current capability

SpecFlow Agent can now:

1. Understand repository structure and technology evidence.
2. Generate sanitized project context.
3. Load and render versioned prompts as engineering assets.
4. Assemble deterministic LLM input context.
5. Enforce token budgets before runtime execution.
6. Represent LLM calls through provider-neutral contracts.
7. Record safe metadata traces.
8. Return predictable fallback results when runtime execution fails.

## Explicit limitations

- No Analyze Worker.
- No Generate Worker.
- No Review Worker.
- No Agent Loop.
- No Workflow orchestration.
- No LangGraph.
- No Redis.
- No RAG or embeddings.
- No real LLM provider integration.
- No automatic code generation.

## Next milestone

M4 - Agent Workflow.

Recommended next tasks:

1. Create a task spec for the first Worker boundary.
2. Start with Analyze Worker only.
3. Use existing Prompt Registry, Context Builder, Token Budget, LLM Client,
   Trace, and Fallback modules instead of creating a new orchestration layer.
