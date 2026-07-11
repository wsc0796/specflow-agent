# T-014 completion report - Worker Framework

## Result

Implemented the Worker Framework for future Analyze, Generate, and Review
workers without implementing any real business Worker. The framework defines
structured Worker contracts, deterministic registration, and an adapter that
connects Workers to the existing T-013 `AgentExecutor`.

## Worker Framework architecture

```text
WorkflowEngine
  -> AgentExecutor
  -> WorkerStepHandler
  -> WorkerRegistry
  -> Worker Protocol / BaseWorker
```

## Worker and Executor boundaries

- `WorkflowEngine` owns state legality and transition history.
- `AgentExecutor` owns step timing, success/failure handling, and workflow
  advancement.
- `WorkerRegistry` owns explicit role/name registration and deterministic lookup.
- `WorkerStepHandler` adapts `WorkerResult` into T-013 `StepResult`.
- `Worker` only executes one business step and does not mutate workflow state.

## WorkerContext and WorkerResult contracts

- `WorkerContext` carries `run_id`, `requirement`, `project_context`,
  deterministic `prior_outputs`, and structured metadata.
- `WorkerResult` carries worker identity, success/failure, constrained output,
  metadata, error type/message, and `requires_review`.
- Successful `WorkerResult` values cannot carry error fields.
- Failed `WorkerResult` values must include an error message.
- Worker error messages are sanitized before reaching executor results.

## Registry behavior

- Workers are registered explicitly.
- Duplicate roles are rejected.
- Duplicate names are rejected.
- Missing-role lookup fails clearly.
- Metadata listing is deterministic by `WorkerRole`.
- No module auto-scan, dynamic import, or global singleton exists.

## Adapter behavior

- `WorkerStepHandler` implements the T-013 `StepHandler` shape.
- Worker success becomes a `StepResult`.
- Worker failure or exception raises `WorkerExecutionError`.
- `AgentExecutor` remains responsible for transitioning to `failed`.
- The adapter does not directly modify workflow state.

## Scope delivered

- Created `docs/tasks/T-014-worker-framework.md`.
- Added `src/specflow/workers/` modules:
  - `models.py`
  - `base.py`
  - `registry.py`
  - `adapter.py`
  - `exceptions.py`
  - `__init__.py`
- Added `tests/test_worker_framework.py`.
- Updated `README.md` and `AGENTS.md`.

## Test scenarios

- Valid and invalid worker metadata.
- Valid and invalid worker context.
- WorkerResult success/failure contracts.
- Registry registration, duplicate role/name rejection, missing lookup, and
  deterministic metadata ordering.
- Adapter conversion from WorkerResult to StepResult.
- Fake Worker integration with AgentExecutor.
- Worker failure and exception paths driving AgentExecutor to `failed`.
- Invalid Worker return values.
- Reserved adapter metadata cannot be overwritten by Worker metadata.
- Worker call count / no repeated step execution.
- Sensitive error-message redaction.

## Validation

```powershell
uv sync --all-groups
uv run pytest tests/test_worker_framework.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Result:

- `uv run pytest tests/test_worker_framework.py -v`: 27 passed.
- `uv sync --all-groups`: passed.
- `uv run pytest -v`: 189 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 68 files already formatted.
- `git diff --check`: passed.

## Known limits

- No real Analyze Worker.
- No real Generate Worker.
- No real Review Worker.
- No Prompt Registry, Context Builder, Token Budget, LLM Client, Trace, or
  Fallback integration is added in T-014.
- Worker context is in memory only.
- T-015 Analyze Worker remains the next permitted task.
