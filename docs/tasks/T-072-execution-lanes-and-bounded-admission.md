# T-072 — Execution Lanes and Bounded Admission

**Status:** FROZEN. Implementation requires T-071 to be closed and a new focused
session.

## Goal

Introduce explicit, bounded execution-resource lanes for local/tool work and
live provider work, with optional safe side-effect isolation, without replacing
the fixed six-agent orchestration model or silently discarding accepted work.

## Requirements

- **REQ-072-1 — Keep orchestration and resource governance separate.** The
  Coordinator continues to own the fixed topology, stages, dependencies,
  schemas, and revision semantics. A lane manager governs only where and how
  bounded work is admitted and executed.
- **REQ-072-2 — Define named lanes.** At minimum define `local_tool` for bounded
  repository/tool execution and `provider` for live LLM calls. A `side_effect`
  lane may be added only for currently identifiable non-provider work whose
  failure contract is explicit. Required artifact/checkpoint writes remain
  critical and may not be converted into best-effort discarded work.
- **REQ-072-3 — Bound active and queued work.** Each lane has positive,
  policy-backed maximum concurrency and queue/admission capacity. Admission must
  be atomic and thread-safe. Zero remaining capacity produces a safe classified
  saturation error rather than an unbounded queue, implicit blocking, or hidden
  executor growth.
- **REQ-072-4 — Never silently discard.** Every accepted submission returns a
  resolvable Future/result handle and eventually completes, fails, or is
  explicitly cancelled. Every rejected submission raises a safe saturation
  error before a Future is exposed. Abort/reject is allowed; discard and
  discard-oldest policies are forbidden.
- **REQ-072-5 — Preserve deadline behavior.** Queued work that cannot start
  before the run deadline is explicitly cancelled and accounted for. Already
  started synchronous Python work follows the existing T-062 boundary: queued
  work is cancelled, but the scheduler waits for started threads to exit before
  releasing shared capacity. No task may remain unresolved after timeout.
- **REQ-072-6 — Release capacity on every path.** Success, classified failure,
  unexpected exception, submission failure, cancellation, timeout, and executor
  shutdown must release active/queue permits exactly once. A failed submission
  must not leak capacity.
- **REQ-072-7 — Route by execution class, not Agent role.** Multiple agents may
  use the same provider lane, and an Agent may use local/tool then provider work.
  Lane assignment must not create dynamic topology, new stages, or per-Agent
  thread pools.
- **REQ-072-8 — Preserve T-070/T-071 semantics.** A single-flight follower does
  not acquire duplicate lane capacity. An OPEN provider circuit rejects before
  provider-lane network execution. Lane saturation remains distinct from
  provider failure, retry exhaustion, and wall-time budget errors.
- **REQ-072-9 — Prepare safe metrics.** The lane manager exposes bounded counts
  and timestamps needed by T-073: lane, submitted, started, completed, active,
  queued, rejected, and cancelled. T-072 need not redesign `metrics.json`.
- **REQ-072-10 — Expected implementation surface.** Expected production files
  are a focused `src/specflow/coordinator/execution_lanes.py`,
  `src/specflow/coordinator/scheduler.py`, `src/specflow/runner_multi.py`, and
  the minimum execution policy/default/validator modules; provider/local
  adapters may change only to submit through their lane. Expected tests are
  `tests/test_execution_lanes.py`, `tests/test_scheduler.py`,
  `tests/test_execution_policy.py`, and `tests/test_cli_multi_agent.py`. Any
  proposal to replace the Coordinator, introduce a general scheduler, or move
  critical artifacts to best-effort side effects requires a spec amendment.

## Boundaries

The following are explicit non-goals for T-072:

- Depends on closed T-071 and must retain T-070 single-flight guarantees.
- No general-purpose DAG scheduler, dynamic graph, dynamic Agent discovery,
  peer-to-peer messaging, process pool, asyncio migration, or background job
  system.
- No Redis/shared semaphore, multi-process admission, distributed queue, or
  deployment scaling claim.
- No silent discard, unresolved Future, unbounded queue, unbounded thread
  creation, caller-runs surprise, or forced termination of Python threads.
- No topology, schema, prompt, DLP, retry, fallback, review, revision, or
  artifact-contract change.
- No T-073 artifact redesign or T-074 caching in this task.

## Acceptance

- **AC-072-1:** Unit tests prove per-lane concurrency and queue/admission bounds
  with barriers/events, not timing sleeps.
- **AC-072-2:** Saturation rejects explicitly with the correct lane and safe
  error code; rejected work has no unresolved Future and never executes later.
- **AC-072-3:** Accepted work resolves on success, exception, cancellation, and
  deadline paths; capacity returns to its original value exactly once after
  every path.
- **AC-072-4:** Tests prove local/tool and provider lanes are isolated: saturating
  one does not consume the other's permits. Optional side-effect behavior, if
  implemented, is equally bounded and never discards required work.
- **AC-072-5:** Scheduler tests preserve sequential stages, parallel agents
  within a stage, fixed six-agent topology, prior-output propagation, T-062
  timeout waiting, and deterministic result ordering/contracts.
- **AC-072-6:** Integration tests prove single-flight followers do not acquire a
  second permit and OPEN circuits do not submit provider network work.
- **AC-072-7:** Existing CLI/mock, policy, scheduler, runtime budget, schema,
  artifact, T-070, and T-071 tests remain green.
- **AC-072-8:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-072-9:** `docs/reports/T-072-completion-report.md` records lane mapping,
  capacity semantics, timeout behavior, tests, and single-process limitations.
  One focused implementation commit is created, then work stops before T-073.
