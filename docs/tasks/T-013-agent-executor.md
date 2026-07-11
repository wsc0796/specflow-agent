# T-013 - Agent Executor

## Goal

Implement a deterministic Agent Executor on top of the T-012 Workflow State
Machine. The executor decides which abstract step handler should run for the
current workflow state, records structured execution results, advances the
workflow through legal transitions, and fails honestly when a handler fails.

## In scope

- `src/specflow/executor/` module.
- `AgentExecutor`.
- `StepHandler` protocol.
- `StepResult`.
- `ExecutionResult`.
- `ExecutionStatus`.
- `ExecutionError`.
- Deterministic step-to-state mapping.
- `start()` and `execute()` entry points, with `execute_next()` as the explicit
  one-step primitive.
- In-memory execution context and step result storage.
- Safe error redaction for execution results.
- Unit tests using fake/stub handlers only.

## Out of scope

- Analyze Worker.
- Generate Worker.
- Review Worker.
- Worker framework.
- Real LLM calls.
- Agent Loop or ReAct loop.
- LangGraph.
- Tool calling.
- RAG, embeddings, or vector databases.
- Redis.
- Automatic code modification.
- Workflow HTTP API.
- Database schema changes or persistence.
- Prompt Registry integration.
- Context Builder integration.
- Token Budget integration.
- Trace integration.
- Fallback integration.
- T-014 and later tasks.

## Required behavior

The Agent Executor must:

1. Determine the executable step from the current `WorkflowState`.
2. Call the matching `StepHandler`.
3. Advance the T-012 workflow state only through legal transitions.
4. Convert handler failure into `failed` workflow state.
5. Preserve structured step results, error type, sanitized error message, and
   full workflow history.
6. Support continuation from legal intermediate workflow snapshots.
7. Reject terminal workflow execution from `completed` or `failed`.
8. Prevent repeated execution of the same step in one executor instance.
9. Derive prior completed steps from valid workflow history during recovery
   without fabricating missing historical `StepResult` payloads.
10. Reject invalid handler results.
11. Never hide an exception as success.

## Step mapping

```text
created -> start -> analyzing
analyzing -> analyze -> generating
generating -> generate -> reviewing
reviewing -> review -> completed
```

Failure from `analyzing`, `generating`, or `reviewing` must transition to
`failed`. Failure while starting from `created` must first enter `analyzing`,
then transition to `failed` so the history remains auditable.

## Models

`StepResult`:

- `metadata`

`ExecutionStatus`:

- `success`
- `failed`

`ExecutionResult`:

- `status`
- `executed_step`
- `previous_state`
- `current_state`
- `success`
- `metadata`
- `error_type`
- `error_message`
- `history`

`StepHandler`:

- protocol with `execute(execution_context) -> StepResult`.

## Acceptance criteria

1. `created` starts execution and enters `analyzing`.
2. Fake handlers can drive the full chain to `completed`.
3. Analyze handler failure enters `failed`.
4. Generate handler failure enters `failed`.
5. Review handler failure enters `failed`.
6. Failure result records failed step and error type.
7. `completed` cannot be executed again.
8. `failed` cannot be silently resumed by normal execute.
9. Legal intermediate workflow snapshots can be restored and continued.
10. Illegal workflow history is rejected through T-012 validation.
11. The same step is not called twice in one executor instance.
12. Invalid handler results fail clearly.
13. Sensitive error messages are redacted.
14. Existing tests continue to pass.

## Validation

Before completion:

```powershell
uv sync --all-groups
uv run pytest tests/test_agent_executor.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Write a completion report under `docs/reports/`, create one focused Git commit,
and push to GitHub. Do not start T-014.
