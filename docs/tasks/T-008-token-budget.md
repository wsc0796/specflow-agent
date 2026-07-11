# T-008 - Token Budget Manager

## Goal

Create a deterministic token-budget control layer that accepts a T-007
`BuiltContext`, estimates its size, detects budget overflow, trims low-priority
context sections, records removed sections, and returns a stable `BudgetResult`.

## Preflight note

`docs/records/M3-agent-infrastructure.md` does not exist yet because Milestone 3
is still in progress. T-008 must not create or close the M3 milestone record.

## In scope

- `src/specflow/token_budget/` module.
- Deterministic token estimation.
- `BudgetPolicy` model.
- `BudgetResult` model.
- Context-over-budget detection.
- Deterministic context trimming.
- Priority-based retention strategy.
- `removed_sections` tracking.
- Stable `context_hash` after budgeting.
- Unit tests for success and failure paths.

## Out of scope

- LLM calls.
- Automatic summarization.
- RAG, embeddings, vector stores, Redis, LangGraph, MCP, or Java support.
- Worker orchestration.
- Workflow-state changes.
- Prompt rendering or Prompt Registry changes.
- Repository scanning.
- Provider-specific tokenizers.

## Required API

```python
manager = TokenBudgetManager(policy=BudgetPolicy(max_tokens=800))
result = manager.apply(built_context)
```

`apply()` must accept:

- `BuiltContext`

`apply()` must return `BudgetResult` containing:

- `context`
- `policy`
- `original_estimated_tokens`
- `final_estimated_tokens`
- `was_trimmed`
- `removed_sections`
- `context_hash`

## Budget policy

`BudgetPolicy` must support:

- `max_tokens`
- `reserved_response_tokens`
- `estimation_chars_per_token`
- `section_priorities`

The effective input budget is:

```text
max_tokens - reserved_response_tokens
```

Invalid policies must fail explicitly.

## Retention strategy

The manager must preserve high-priority content before low-priority content.
The default priority order is:

1. `system_message`
2. `requirement`
3. `project_overview`
4. `technology_stack`
5. `source_tracking` (non-removable `BuiltContext.sources` metadata)
6. `evidence`
7. `warnings`
8. `unknowns`

When trimming is required, the manager may remove lower-priority sections from
`user_message`, but it must not remove:

- `system_message`
- prompt identity
- prompt hash
- project context hash
- source tracking metadata

`source_tracking` priority documents its protected metadata priority. It is not
removed from `user_message` because source tracking lives in `BuiltContext.sources`.

## Acceptance criteria

1. Small `BuiltContext` input is fully retained.
2. Oversized context triggers deterministic trimming.
3. Higher-priority sections are retained before lower-priority sections.
4. `removed_sections` records each removed section in deterministic order.
5. Equal inputs and policy produce equal `context_hash`.
6. Sensitive raw values do not reappear after budgeting.
7. Invalid or impossible budgets fail explicitly.
8. The implementation does not call an LLM, summarize, use embeddings/RAG,
   introduce Worker orchestration, modify runtime workflow state, or write to
   the database.

## Validation

Before completion:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Write a completion report under `docs/reports/` and create one focused Git
commit. Push to `origin/main`. Do not start T-009.
