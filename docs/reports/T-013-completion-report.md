# T-013 completion report - Agent Executor

## Result

Implemented the deterministic Agent Executor on top of the T-012 Workflow State
Machine. The executor can start a workflow, call abstract step handlers,
advance legal workflow states, preserve structured step results, fail honestly,
redact sensitive error messages, and continue from valid intermediate workflow
snapshots. Restored executors derive already completed steps from the validated
workflow history so handlers receive an auditable recovery context without
inventing missing historical step-result payloads.

## Core models

- `AgentExecutor`: coordinates deterministic step execution and workflow state
  advancement through `start()`, `execute()`, `execute_next()`, and
  `execute_until_complete()`.
- `StepHandler`: protocol for fake/stub handlers in T-013.
- `StepResult`: structured handler metadata.
- `ExecutionResult`: one-step execution outcome with state, metadata, error,
  and history.
- `ExecutionStatus`: `success` or `failed`.
- `ExecutionError`: explicit executor failure contract.

## State machine relationship

T-012 owns state rules and history validation. T-013 does not create its own
state rules; it delegates all state transitions to `WorkflowEngine`.

The T-013 executor maps states to steps:

```text
created -> start -> analyzing
analyzing -> analyze -> generating
generating -> generate -> reviewing
reviewing -> review -> completed
```

Handler failure from active states transitions to `failed` and returns a failed
`ExecutionResult` instead of hiding the exception as success.

## Scope delivered

- Created `docs/tasks/T-013-agent-executor.md`.
- Added `src/specflow/executor/` modules:
  - `engine.py`
  - `models.py`
  - `handlers.py`
  - `exceptions.py`
  - `__init__.py`
- Added `tests/test_agent_executor.py`.
- Updated `README.md` and `AGENTS.md`.

## Test scenarios

| Requirement | Evidence |
| --- | --- |
| Start from `created` | `test_created_start_enters_analyzing_without_worker_handler` |
| Ordinary execute entry point | `test_execute_alias_runs_current_step` |
| Three fake handlers complete workflow | `test_three_fake_handlers_complete_full_chain` |
| Restored context records prior steps | `test_restored_context_marks_prior_steps_completed_from_history` |
| Analyze failure | `test_analyze_handler_failure_enters_failed` |
| Generate failure | `test_generate_handler_failure_enters_failed` |
| Review failure | `test_review_handler_failure_enters_failed` |
| Failure result structure | `test_failure_result_preserves_history` |
| Completed cannot execute again | `test_completed_state_cannot_execute_again` |
| Failed cannot silently resume | `test_failed_state_cannot_be_silently_resumed` |
| Legal intermediate recovery | `test_legal_intermediate_snapshot_can_restore_and_continue` |
| Illegal history rejected | `test_illegal_history_restore_is_rejected` |
| Step not called twice | `test_same_step_is_not_called_twice_in_one_executor` |
| Invalid handler result fails | `test_invalid_handler_result_fails_clearly` |
| Sensitive error redaction | `test_sensitive_error_message_is_redacted` |

## Validation

```powershell
uv sync --all-groups
uv run pytest tests/test_agent_executor.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Result:

- `uv run pytest tests/test_agent_executor.py -v`: 15 passed.
- `uv sync --all-groups`: passed.
- `uv run pytest -v`: 162 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 61 files already formatted.
- `git diff --check`: passed.

## Known limits

- Executor state is in memory only.
- Step handlers are fake/stub callables only.
- No Analyze Worker, Generate Worker, or Review Worker exists.
- No Prompt Registry, Context Builder, Token Budget, LLM Client, Trace, or
  Fallback integration exists in T-013.
- T-014 Worker Framework remains the next permitted task.
