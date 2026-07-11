# T-017 - Review Worker

## Goal

Implement `ReviewWorker`, the third real business Worker in M4.

`ReviewWorker` consumes the original requirement, a valid `AnalysisOutput`, a
valid `GenerationOutput`, and project context to produce a deterministic
`ReviewOutput`.

## In scope

- `src/specflow/workers/review.py`.
- `ReviewOutput`, `ReviewIssue`, and `ReviewDecision` structured models.
- Consumption and validation of T-015 `AnalysisOutput`.
- Consumption and validation of T-016 `GenerationOutput`.
- Dependency-injected use of:
  - Prompt Registry
  - Context Builder
  - Token Budget Manager
  - LLM Client abstraction
  - Trace Recorder
  - Fallback Manager
- `WorkerStepHandler` / `AgentExecutor` integration tests.
- New `review_generation` prompt asset.

## Out of scope

- Automatic review loop.
- `REVIEWING -> GENERATING -> REVIEWING` retry flow.
- Automatic code modification.
- Tool calling.
- Real provider SDK integration.
- API key loading.
- Workflow state mutation inside the Worker.
- Planner, ReAct, LangGraph, RAG, embeddings, Redis, or database persistence.

## Required semantic distinction

`ReviewWorker` execution failure is different from a business `REJECT`.

- Runtime failure, exceptions, invalid required input, or unparsable output:
  controlled Worker failure or degraded output as specified below.
- Business `decision=REJECT`:
  successful Worker execution, `requires_revision=true`, and workflow may
  transition from `reviewing` to `completed`.

T-017 does not implement automatic rework loops.

## Output

`ReviewOutput` must include:

- `decision`: `PASS` or `REJECT`
- `summary`
- `issues`
- `missing_requirements`
- `risk_findings`
- `acceptance_criteria_results`
- `severity`
- `requires_revision`
- `requires_human_review`
- `analysis_hash`
- `generation_hash`
- `degraded`
- stable `review_hash`

`ReviewIssue` includes:

- `code`
- `severity`
- `message`
- `related_requirement`
- `suggestion`

## Validation

Before completion:

```powershell
uv run pytest tests/test_review_worker.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Write a completion report under `docs/reports/`, create one focused Git commit,
and push to GitHub. Do not start M5.
