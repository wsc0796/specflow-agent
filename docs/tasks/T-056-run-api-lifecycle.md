# T-056 — Minimal Run API and SQLite Lifecycle

```yaml
task_id: T-056
title: Minimal Run API and SQLite Lifecycle
stage_state: closeout
goal: >
  Expose the existing controlled multi-agent mock executor through a minimal,
  project-bound HTTP API and persist its lifecycle in the existing WorkflowRun
  record.
allowed_scope:
  files:
    - src/specflow/db.py
    - src/specflow/runs.py
    - src/specflow/main.py
    - tests/test_runs.py
    - tests/test_projects.py
    - README.md
    - docs/reports/T-056-completion-report.md
  modules:
    - SQLite WorkflowRun persistence
    - FastAPI run boundary
    - existing multi-agent mock runner
  commands:
    - uv run pytest -v
    - uv run ruff check .
    - uv run ruff format --check .
    - uv build
forbidden_scope:
  - Do not add a queue, worker process, Redis, Docker, authentication, or a dashboard.
  - Do not call a live provider from HTTP or accept provider credentials in requests.
  - Do not accept an arbitrary repository path or an artifact output path from this API.
  - Do not alter the existing multi-agent orchestration, execution policy, or artifact schemas.
  - Do not modify a registered repository or execute shell commands.
inputs:
  - AGENTS.md
  - docs/00-SPEC-BASELINE.md
  - src/specflow/db.py
  - src/specflow/policy/models.py
  - src/specflow/runner_multi.py
acceptance:
  - POST /api/v1/runs accepts a registered project ID and non-empty requirement, then creates a persisted run.
  - The API invokes only the existing multi-agent mock executor and returns a terminal RunStatus.
  - GET /api/v1/runs/{run_id} returns the persisted lifecycle without an absolute artifact path or internal exception details.
  - GET /api/v1/runs/{run_id}/artifacts returns a bounded, relative-file artifact index only after artifacts exist.
  - WorkflowRun remains the one database record for status, hashes, safe error code, and artifact reference.
  - Existing SQLite databases receive additive nullable WorkflowRun columns during startup.
  - Missing projects, invalid payloads, missing runs, and runner failure have explicit, tested behavior.
verification:
  - command: uv run pytest -v
    proves: API contract, persistence lifecycle, migration, and all existing behavior pass.
  - command: uv run ruff check .
    proves: lint gate passes.
  - command: uv run ruff format --check .
    proves: formatting gate passes.
  - command: uv build
    proves: distributable package still builds.
outputs:
  - project-bound runs router/service/repository
  - additive SQLite migration guard
  - API contract tests
  - completion report
risks:
  - HTTP execution is synchronous and deliberately limited to short mock runs.
  - Existing runner identifiers are deterministic per repository and requirement; duplicate requests may be recorded as failed_runtime rather than retried automatically.
next_state: closed after focused commit, push, and passing remote CI
```

## L2 system model

| Dimension | T-056 decision |
| --- | --- |
| Object | A `WorkflowRun` is the sole durable record of one API-triggered, project-bound execution. |
| Truth source | SQLite `workflow_runs`; generated artifacts remain files under an application-controlled root. |
| Lifecycle | `created → running → terminal RunStatus`; this first slice is synchronous and has no resume/cancel worker. |
| Invariants | Project must already exist; request cannot select a provider, repository path, or output path; only relative artifact names are exposed. |
| Contracts | `POST /api/v1/runs`, `GET /api/v1/runs/{id}`, and `GET /api/v1/runs/{id}/artifacts`; unknown resources are 404. |
| Impact | DB startup adds only nullable metadata columns. Existing CLI runner behavior, project API, policies, and artifacts remain unchanged. |

## Design decisions

- `workflow_type` records `multi-agent`; `current_state` and `result_status` reuse
  `RunStatus` values rather than inventing API-only status words.
- The endpoint supports mock execution only. `mock` is accepted solely to reject
  `false`, making the boundary explicit instead of silently using credentials.
- `requirement_hash`, `repository_alias`, `policy_hash`, `artifact_directory`,
  and `error_code` are nullable, additive `WorkflowRun` columns. Existing
  SQLite files are reconciled at application startup with `ALTER TABLE` only
  for missing columns.
- `artifact_directory` is stored relative to the application-owned
  `data/runs/` root. The API returns filenames only; it never serves arbitrary
  filesystem paths or artifact contents.
- Runner exit codes are translated to existing statuses: `0 → completed`,
  `4 → completed_degraded`, `2 → failed_security`, all other nonzero codes →
  `failed_runtime`.
