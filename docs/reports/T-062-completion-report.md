# T-062 Completion Report — Runtime Boundary Remediation

## Result

**PASS.** The uncommitted runtime-hardening changes now close the verified
allowlist, quota, scheduler-lifecycle, and safe-error propagation gaps.

## Delivered

- Run creation revalidates the persisted Project repository path against the
  active allowlist. A Project registered before the allowlist was enabled, or
  later redirected through a link, cannot bypass that boundary.
- The run limiter acquires a concurrency permit before committing a request to
  its minute window. A concurrency-only 429 therefore does not consume quota;
  this is covered at both limiter and HTTP endpoint boundaries.
- The Run API reads failed manifests from the runner's actual output directory
  and preserves safe classified errors such as `TIME_BUDGET_EXCEEDED`. It
  rejects links, locations outside the artifact root, and non-code values.
- A scheduler deadline cancels queued futures and waits for started synchronous
  executors to return before the caller can release shared run capacity. This
  is intentionally documented as bounded detection plus draining, not forced
  cancellation of arbitrary Python threads.
- Added public-boundary regression coverage for all four behaviours and
  formatted the pre-existing `tests/test_mcp_server.py` violation so the
  repository-wide format gate is clean.

## Validation

| Gate | Result |
| --- | --- |
| `uv run pytest -q` | 740 passed, 3 skipped, 3 warnings |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed |
| `python scripts/check_secrets.py` | passed |
| `uv build` | passed |
| `git diff --check` | passed |

## Known limits

- The limiter is process-local. Multi-process deployments need a shared
  limiter.
- The runtime is synchronous. A third-party executor that ignores its own I/O
  timeout can delay the failure response, but cannot continue after API run
  capacity has been released.
- This task does not add workers, queues, retries, forced thread termination,
  authentication beyond the existing opt-in API key, or deployment work.
