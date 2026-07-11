# T-014 - Worker Framework

## Goal

Create a unified, deterministic Worker Framework that future tasks can use for
Analyze, Generate, and Review workers. T-014 defines Worker contracts,
registration, and the adapter that connects Workers to the existing T-013
`AgentExecutor` without implementing any real business Worker.

## In scope

- `src/specflow/workers/` module.
- `WorkerRole`.
- `WorkerContext`.
- `WorkerResult`.
- `WorkerMetadata`.
- `Worker` protocol.
- Minimal `BaseWorker`.
- Deterministic `WorkerRegistry`.
- `WorkerStepHandler` adapter for T-013 `StepHandler`.
- Worker-specific exceptions.
- Unit tests using fake/stub/failing workers only.

## Out of scope

- AnalyzeWorker.
- GenerateWorker.
- ReviewWorker.
- Planner.
- Multi-agent communication.
- Agent Loop or ReAct loop.
- LangGraph.
- Tool calling.
- LLM calls.
- Prompt Registry integration.
- Context Builder integration.
- Token Budget integration.
- Trace or Fallback integration changes.
- RAG, embeddings, vector databases, Redis, or database persistence.
- HTTP API.
- Automatic code modification.
- T-015 and later tasks.

## Architecture boundary

```text
WorkflowEngine      -> state legality
AgentExecutor       -> step timing, success/failure, workflow advancement
WorkerStepHandler   -> WorkerResult <-> StepResult adapter
WorkerRegistry      -> explicit role/name lookup
Worker              -> one business step only
```

The Worker Framework must not duplicate `AgentExecutor`. Workers must not
receive an `AgentExecutor`, call `WorkflowEngine.transition()`, call the next
Worker, or decide workflow state transitions.

## Required models

`WorkerRole`:

- `analyze`
- `generate`
- `review`

`WorkerContext`:

- `run_id`
- `requirement`
- `project_context`
- `prior_outputs`
- `metadata`

`WorkerResult`:

- `worker_name`
- `worker_role`
- `success`
- `output`
- `metadata`
- `error_type`
- `error_message`
- `requires_review`

`WorkerMetadata`:

- `name`
- `role`
- `version`
- `description`

## Required behavior

1. Worker metadata must be stable and validated.
2. Worker context must reject missing requirements and invalid structured data.
3. Worker result success and error fields must be consistent.
4. Worker error messages must be sanitized.
5. Registry must register Workers explicitly.
6. Registry must reject duplicate roles.
7. Registry must reject duplicate names.
8. Registry lookup by missing role must fail clearly.
9. Registry metadata listing must be deterministic.
10. Adapter must call one Worker and convert success into `StepResult`.
11. Adapter must convert Worker failure into a controlled exception so
    `AgentExecutor` transitions to `failed`.
12. Adapter must reject non-`WorkerResult` values.
13. Adapter must not mutate workflow state directly.

## Validation requirements

Before completion:

```powershell
uv sync --all-groups
uv run pytest tests/test_worker_framework.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Write a completion report under `docs/reports/`, create one focused Git commit,
and push to GitHub. Do not start T-015.
