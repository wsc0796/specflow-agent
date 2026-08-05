# T-062 — Runtime Boundary Remediation

## Goal

Correct the verified safety and observability regressions in the uncommitted
runtime-hardening work before it can be reviewed or committed.

## Allowed scope

- Revalidate a persisted Project repository path against the configured API
  allowlist when a Run is created.
- Make the in-process run limiter count only requests that obtained a
  concurrency permit.
- Preserve the runner's persisted, safe error code in the Run API response.
- Ensure the scheduler does not return while an already-started executor is
  still running; accurately document this synchronous-thread limitation.
- Add focused regression tests, reconcile user-facing claims, and write a
  completion report.

## Non-goals

- Multi-process or distributed rate limiting.
- Authentication/authorization beyond the existing opt-in API-key boundary.
- Background jobs, queues, retries, resume, or forced termination of arbitrary
  Python threads.
- New deployment capabilities.

## Acceptance

1. A Project saved before allowlist activation cannot be run outside the
   configured roots.
2. A request rejected only because a run is already active does not consume a
   per-minute run quota.
3. A runner manifest error such as `TIME_BUDGET_EXCEEDED` is returned as the
   Run record's safe `error_code`.
4. When a stage deadline expires, the scheduler cancels queued work and waits
   for started synchronous work to exit before returning control.
5. Focused tests, full pytest, Ruff checks, formatting, secret scan, build and
   `git diff --check` have recorded outcomes.
