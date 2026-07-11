# T-011 - Fallback System

## Goal

Create an Agent Runtime Failure Handling layer so runtime failures remain
predictable, recoverable, explainable, and traceable without introducing Worker,
Agent Loop, or Workflow behavior.

## In scope

- `src/specflow/fallback/` module.
- `FallbackLevel` model.
- `FallbackResult` model.
- Retry strategy with bounded retry count.
- JSON repair strategy for extracting a JSON object from noisy text.
- Rule baseline strategy for explicit degraded output.
- `FallbackManager`.
- Failure contract and explicit errors.
- Trace integration through metadata-only fallback fields.
- Unit tests for success, retry, repair, baseline, and sensitive data handling.

## Out of scope

- Worker orchestration.
- Agent Loop.
- Workflow-state changes.
- LangGraph.
- RAG or embeddings.
- Redis.
- Automatic code generation.
- Model-specific provider behavior.
- Automatic planning or reasoning.

## Required behavior

`FallbackManager.execute()` must:

1. Run an operation once.
2. Retry bounded transient failures.
3. If JSON is required and raw content is not valid JSON, attempt JSON repair.
4. If retry and repair cannot produce a valid result, return a rule baseline
   degraded result.
5. Never hide failure as a successful AI result.
6. Never expose raw API keys, passwords, or tokens in fallback output.

## Models

`FallbackLevel`:

- `none`
- `retry`
- `json_repair`
- `rule_baseline`

`FallbackResult`:

- `status`
- `fallback_level`
- `content`
- `confidence`
- `requires_review`
- `error_type`
- `retry_count`

## Trace integration

T-010 trace metadata must support:

- `fallback_level`
- `retry_count`

Trace integration must remain metadata-only and must not store prompt content,
user message content, raw response content, API keys, passwords, or tokens.

## Acceptance criteria

1. Normal success returns `status="success"` and `fallback_level="none"`.
2. First failure followed by retry success returns `fallback_level="retry"` and
   `retry_count=1`.
3. Noisy text containing a JSON object can be repaired into valid JSON with
   `fallback_level="json_repair"`.
4. Full failure path returns `status="degraded"`, `fallback_level="rule_baseline"`,
   `requires_review=True`, and low confidence.
5. Sensitive data does not appear in fallback results.
6. Trace model can carry fallback metadata without storing sensitive content.
7. The implementation does not introduce Worker, Agent Loop, Workflow,
   LangGraph, RAG, embeddings, Redis, or automatic code generation.

## Validation

Before completion:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Write a completion report under `docs/reports/` and create one focused Git
commit. Do not start M4.
