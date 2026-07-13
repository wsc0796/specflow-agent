---
task_id: T-057
title: Run Interruption Recovery
stage_state: closeout
owner: Codex
branch: main
---

# Goal

On application startup, durably resolve a `WorkflowRun` left in `running` by a
previous process interruption to the existing safe terminal state
`failed_runtime`, with error code `INTERRUPTED`.

# Context and Inputs

- `WorkflowRun` is the sole durable lifecycle record for the mock-only Run API.
- T-056 commits `running` before the synchronous executor starts. A process kill
  between that commit and terminal persistence currently leaves a misleading
  permanent `running` record.
- There is no worker, lease, cancellation, resume, or multi-instance contract.

## L2 system model

| Dimension | Decision |
| --- | --- |
| Object | A persisted `WorkflowRun` represents one controlled execution attempt. |
| Truth source | SQLite `workflow_runs.current_state`, `result_status`, `error_code`, `finished_at`, and `version`. |
| Lifecycle | Startup changes only stale `running` to terminal `failed_runtime`; all other states remain unchanged. |
| Invariants | Recovery does not rerun work, expose exception details, or overwrite a terminal outcome; each recovered row advances its version once. |
| Contracts | Existing GET returns the recovered status and `INTERRUPTED`; no request/response schema is added. |
| Impact | FastAPI lifespan invokes recovery after schema reconciliation; existing create and artifact flows remain unchanged. |

# Allowed Scope

## Files

- `src/specflow/runs.py`
- `src/specflow/main.py`
- `tests/test_runs.py`
- `docs/tasks/T-057-run-interruption-recovery.md`
- `docs/reports/T-057-completion-report.md`
- `AGENTS.md`

## Modules

- Run lifecycle service and FastAPI startup lifecycle
- Isolated SQLite/FastAPI lifecycle regression tests

## Commands

- `uv run pytest tests/test_runs.py -v`
- `uv run pytest -v`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv build`
- `python scripts/check_secrets.py`
- `git diff --check`

# Forbidden Scope

- Do not add a queue, worker process, lease, cancellation, resume, retry, authentication, or multi-instance behavior.
- Do not add dependencies or alter the database schema.
- Do not rerun interrupted work or invoke a live provider.
- Do not change existing terminal-state mappings, artifact policy, public request schemas, or repository write boundaries.
- Do not modify unrelated local `.claude/` files.

# Acceptance Criteria

- [ ] Starting the app turns every already-persisted `running` run into `failed_runtime` with `result_status=failed_runtime`, `error_code=INTERRUPTED`, a non-null `finished_at`, and a one-step version advance.
- [ ] The recovery is one atomic persisted update and does not rerun workflow execution.
- [ ] `created`, completed, degraded, rejected, security-failed, budget-exceeded, cancelled, and already runtime-failed records remain untouched.
- [ ] A second startup is idempotent: the recovered row is not changed again.
- [ ] The existing GET endpoint exposes only the safe terminal status and error code.

# Verification

| Command / Check | Proves | Required |
|---|---|---|
| focused run API tests | restart recovery plus existing API boundary | yes |
| full pytest suite | no regression across the project | yes |
| Ruff check and format | static quality and format | yes |
| `uv build` | distributable package still builds | yes |
| secret scan and diff check | no leaked data or whitespace damage | yes |
| remote CI | the same gates pass in a clean environment | yes before close |

# Testing Subflow

- Required: yes
- Trigger reason: persisted state transition and FastAPI startup behavior.
- Test matrix / eval cases:

| Acceptance / risk | Normal | Boundary | Failure / security | Test layer | Evidence |
| --- | --- | --- | --- | --- | --- |
| Interrupted run recovery | Seed `running`, restart app, GET shows safe terminal state | Version advances exactly once | No executor call occurs during startup | SQLite + FastAPI integration | lifecycle regression test |
| Terminal state preservation | Seed representative terminal/non-running rows | Restart twice | Recovery must not overwrite published failure codes | SQLite integration | state/value assertions |
| API safety | GET recovered run | `finished_at` present | no raw internal detail | API integration | JSON assertions |

- Quality-gate exceptions: none.
- Uncovered risks: a hard kill during the recovery transaction relies on SQLite transaction atomicity; multi-process coordination and resume semantics are explicitly out of scope.

# Deliverables

- Narrow startup recovery function and lifespan integration
- Restart/idempotency regression coverage
- Completion report with validation evidence and residual risk

# Risks and Rollback

- Risk: misclassifying a genuinely active run in a multi-process deployment. Current scope is a single-process mock service; no active lease exists.
- Rollback point: revert the focused task commit. It changes no schema or external request DTO.

# Next Allowed State

`closed` after focused commit, push, and passing remote CI.
