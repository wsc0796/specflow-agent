# T-057 Completion Report — Run Interruption Recovery

## Result

**PASS (self-review approved).** The single-process mock Run API now resolves
durable records stranded in `running` by a previous process interruption at
application startup. It does not rerun or resume work.

## Delivered

- Startup calls a narrow `recover_interrupted_runs()` operation immediately
  after SQLite schema reconciliation.
- One SQL update changes only `running` rows to `failed_runtime`, records the
  safe `INTERRUPTED` code, stamps `finished_at`, and advances `version` once.
- Existing terminal/non-running statuses, result values, error codes, and
  versions remain untouched.
- Restart regression coverage proves the GET endpoint exposes the safe terminal
  state, a second startup is idempotent, and startup never invokes the runner.

## Test-subflow report

```yaml
scope: persisted Run API state transition and FastAPI lifespan startup
behavior_and_risks:
  - a killed synchronous executor must not leave a durable run falsely active
  - recovery must not rerun work or overwrite any non-running state
tests_added_or_changed:
  - restart integration test: running -> failed_runtime/INTERRUPTED, version +1
  - idempotent second-restart assertion
  - all eight non-running RunStatus values remain unchanged
commands_and_results:
  - uv run pytest tests/test_runs.py -v: 8 passed
  - uv run pytest -v: 669 passed, 2 skipped, 3 warnings
  - uv run ruff check .: passed
  - uv run ruff format --check .: passed
  - uv build: passed
  - python scripts/check_secrets.py: passed
  - git diff --check: passed
quality_gates:
  - no new skip or xfail
  - behavior has deterministic SQLite and API regression coverage
uncovered_risks:
  - recovery transaction atomicity relies on SQLite
  - multi-process leases, cancellation, resume, and retry remain out of scope
next_recommended_gate: remote GitHub Actions verification after push
```

## Acceptance evidence

| Criterion | Evidence |
| --- | --- |
| Interrupted run becomes safe terminal outcome | `test_startup_recovers_interrupted_running_run_once` checks GET status, result status, `INTERRUPTED`, and `finished_at`. |
| Recovery is durable and atomic | a single SQLAlchemy `UPDATE` runs inside `database.engine.begin()`; the same test observes persisted `version` 7 → 8. |
| No work is rerun | the restart test replaces `run_multi_agent` with a failing sentinel; startup still succeeds. |
| Non-running values are preserved | `test_startup_leaves_non_running_runs_untouched` covers all eight other `RunStatus` values. |
| Recovery is idempotent | the restart test opens the app twice and verifies the version remains 8. |

## Boundary check

- No dependency, schema, request DTO, provider, queue, worker, retry, resume,
  cancellation, authentication, or multi-instance behavior was added.
- The recovery does not persist raw exception text and only exposes the existing
  safe API fields.
- Untracked local `.claude/` files were not inspected, changed, staged, or
  included in this task.

## 90-day premortem

| Likely failure | Early signal | Current mitigation | Follow-up trigger |
| --- | --- | --- | --- |
| Multiple processes run against one SQLite file | two app instances start concurrently | scope stays single-process; startup resolves only durable stale state | introduce leases/worker ownership with a new concurrency spec |
| Process dies during recovery | a run remains `running` after restart | one transactional SQLite update and next startup retry | adopt operational monitoring and a database with stronger deployment semantics |
| User expects automatic retry | recovered run is terminal | explicit `INTERRUPTED` code distinguishes it from runner failure | specify retry/idempotency policy before adding any retry feature |

## Known limits

- This is interruption classification, not job recovery. It intentionally
  cannot resume, cancel, retry, or determine whether another process is still
  executing the run.
