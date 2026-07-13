# T-056 Completion Report — Minimal Run API and SQLite Lifecycle

## Result

**PASS (independent review approved).** SpecFlow now exposes a bounded HTTP service slice for
running the existing multi-agent mock workflow against an already registered
project and querying the persisted lifecycle and artifact index.

## Delivered

- `POST /api/v1/runs` accepts only `project_id`, a non-empty requirement, and
  the fixed `mock: true` mode.
- `GET /api/v1/runs/{run_id}` returns lifecycle status, hashes, safe error code,
  and artifact availability without an absolute filesystem path or raw error.
- `GET /api/v1/runs/{run_id}/artifacts` returns at most 32 direct artifact
  filenames from an application-controlled root.
- The existing `WorkflowRun` table remains the run truth source. Its additive
  run metadata is reconciled for existing SQLite databases at startup.
- The FastAPI application now reports the released package version (`1.0.1`).

## Evidence

| Check | Result |
| --- | --- |
| API lifecycle, validation, safe failure, artifact index, SQLite compatibility | `tests/test_runs.py`: 6 passed |
| Full suite | `667 passed, 2 skipped, 3 warnings` |
| Lint | `uv run ruff check .` passed |
| Format | `uv run ruff format --check .` passed |
| Package | `uv build` produced source distribution and wheel |
| Secret scan | `python scripts/check_secrets.py` passed |
| Diff hygiene | `git diff --check` passed |

## Boundary check

- No new dependency, queue, worker process, Docker configuration, live provider
  invocation, authentication, dashboard, or repository modification capability.
- The API never accepts a repository path, output directory, provider, or
  credential. It selects a registered project and uses the existing mock
  executor only.
- Artifact content and absolute paths are not exposed through the API.

## Independent review

An independent spec/safety review found no blocker or high-severity issue. It
identified and this task fixed two scope-contained findings: generic runner
exceptions now have a tested safe `failed_runtime` outcome, and an empty
artifact directory now returns `404` instead of a misleading empty index.

## 90-day premortem

| Likely failure | Early signal | Current mitigation | Follow-up trigger |
| --- | --- | --- | --- |
| Mock work blocks HTTP too long | request latency grows with repository size | scope is synchronous mock-only, with existing runtime budgets | introduce a job queue only after a measured latency need and a new spec |
| Existing SQLite file lacks new columns | startup/API SQL error after upgrade | idempotent nullable-column reconciliation plus legacy DB test | adopt versioned migrations before any non-additive schema change |
| Artifact path is tampered with | artifact query returns unexpected files | resolved path must remain under `data/runs`; filenames are direct, non-symlink files | add authorization and immutable artifact storage before multi-user exposure |
| Live credentials leak into HTTP scope | request schema or docs grow provider fields | `mock` is constrained to literal `true`; no provider fields exist | define a separate credential and provider boundary before live execution |

## Known limits

- Requests execute synchronously in one application process; there is no
  cancellation, retry queue, polling worker, authentication, or multi-instance
  concurrency contract.
- A missing registered repository is recorded as the safe terminal status
  `failed_security` with `REPOSITORY_UNAVAILABLE`; internal exception text is
  intentionally not persisted or returned.
