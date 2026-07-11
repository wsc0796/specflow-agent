# T-016 - Generate Worker

## Goal

Implement `GenerateWorker`, the second real business Worker in M4.

`GenerateWorker` consumes the original requirement, a valid `AnalysisOutput`,
and project context to produce a deterministic `GenerationOutput`. It generates
a bounded specification and implementation plan only; it does not modify code,
run commands, call tools, or advance workflow state.

## In scope

- `src/specflow/workers/generate.py`.
- `GenerationOutput` structured model.
- Consumption and validation of T-015 `AnalysisOutput`.
- Dependency-injected use of:
  - Prompt Registry
  - Context Builder
  - Token Budget Manager
  - LLM Client abstraction
  - Trace Recorder
  - Fallback Manager
- `WorkerStepHandler` / `AgentExecutor` integration tests.
- Prompt asset update for `generate_spec`.

## Out of scope

- Review Worker.
- Automatic code modification.
- Git commits or test execution by the Worker.
- Tool calling.
- Real provider SDK integration.
- API key loading.
- Workflow state mutation inside the Worker.
- Planner, ReAct, LangGraph, RAG, embeddings, Redis, or database persistence.

## Input

- `WorkerContext.requirement`.
- `WorkerContext.prior_outputs` containing `analysis_json`.
- Dependency-injected `ProjectContext`.

## Output

`GenerationOutput` must include:

- `requirement_summary`
- `proposed_solution`
- `architecture_or_design`
- `affected_components`
- `implementation_steps`
- `api_or_data_changes`
- `test_plan`
- `risks`
- `acceptance_criteria_mapping`
- `analysis_hash`
- `requires_review`
- `degraded`
- stable `generation_hash`

The Worker returns:

- `generation_json`
- `generation_hash`
- `analysis_hash`

inside `WorkerResult.output`.

## Required behavior

1. Missing or invalid `AnalysisOutput` must return a controlled Worker failure.
2. A degraded `AnalysisOutput` may continue, but generated output must propagate
   `degraded=true` and `requires_review=true`.
3. `analysis_hash` must be preserved.
4. Prompt rendering uses the existing Prompt Registry and Context Builder.
5. Token budgeting uses the existing Token Budget Manager and response reserve.
6. LLM execution uses the provider-neutral `LLMClient` protocol only.
7. Runtime failures and invalid structured responses produce degraded
   `GenerationOutput` values with `requires_review=true`.
8. Trace records metadata only and must not store raw prompt, requirement,
   response content, or secrets.

## Validation

Before completion:

```powershell
uv run pytest tests/test_generate_worker.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Write a completion report under `docs/reports/`, create one focused Git commit,
and push to GitHub. Do not start T-017 until T-016 is complete.
