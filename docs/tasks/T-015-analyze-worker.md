# T-015 - Analyze Worker

## Goal

Implement the first real business Worker: `AnalyzeWorker`.

`AnalyzeWorker` analyzes a user requirement against a validated project context
and returns a deterministic, structured `AnalysisOutput`. It does not generate a
specification, modify code, call other Workers, or mutate workflow state.

## In scope

- `src/specflow/workers/analyze.py`.
- `AnalysisOutput` structured model.
- Dependency-injected use of:
  - Prompt Registry
  - Context Builder
  - Token Budget Manager
  - LLM Client abstraction
  - Trace Recorder
  - Fallback Manager
- `WorkerResult` integration through the existing Worker Framework.
- `WorkerStepHandler` / `AgentExecutor` integration tests.
- Prompt asset update for `analyze_requirement`.

## Out of scope

- Generate Worker.
- Review Worker.
- Worker loops or automatic retry workflows beyond the existing Fallback System.
- Tool calling.
- Real provider SDK integration.
- API key loading.
- Repository file modification.
- Workflow state mutation inside the Worker.
- Planner, ReAct, LangGraph, RAG, embeddings, Redis, or database persistence.

## Input

- `WorkerContext.requirement`.
- Dependency-injected `ProjectContext`.
- Worker metadata and runtime settings.

## Output

`AnalysisOutput` must include:

- `requirement_summary`
- `goals`
- `non_goals`
- `assumptions`
- `affected_components`
- `risks`
- `acceptance_criteria`
- `evidence`
- `requires_review`
- `degraded`
- stable `analysis_hash`

The output is serialized into `WorkerResult.output` as:

- `analysis_json`
- `analysis_hash`

## Required behavior

1. Worker metadata is stable and role is `analyze`.
2. Requirement and project context validation failures return controlled
   `WorkerResult` failures.
3. Prompt rendering uses the existing Prompt Registry and Context Builder.
4. Token budgeting uses the existing Token Budget Manager.
5. LLM execution uses the provider-neutral `LLMClient` protocol only.
6. Runtime failures and invalid structured responses produce degraded
   `AnalysisOutput` values with `requires_review=true`.
7. Trace records metadata only: worker identity, prompt hash, context hash,
   fallback level, and retry count.
8. Trace must not store raw prompt, raw requirement, response content, or secrets.
9. Output serialization and hashing must be deterministic.

## Validation

Before completion:

```powershell
uv sync --all-groups
uv run pytest tests/test_analyze_worker.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Write a completion report under `docs/reports/`, create one focused Git commit,
and push to GitHub. Do not start T-016 until T-015 is complete.
