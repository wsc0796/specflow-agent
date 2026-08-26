# T-073 — Runtime Saturation and Latency Metrics

**Status:** FROZEN. Implementation requires T-072 to be closed and a new focused
session.

## Goal

Make the single-flight, provider-resilience, and execution-lane behavior added
by T-070 through T-072 observable through deterministic, bounded, DLP-safe run
metrics and traces without changing orchestration or claiming production
monitoring coverage.

## Requirements

- **REQ-073-1 — Record the full execution timeline.** For each admitted unit of
  work record UTC submission, start, and completion timestamps plus monotonic
  queue and execution durations. Durations must be non-negative integers and
  must not be derived solely from wall-clock subtraction.
- **REQ-073-2 — Record lane saturation.** Emit the execution lane, active/queued
  snapshot where meaningful, accepted count, completed count, cancellation
  count, and rejection/saturation count. Counts must distinguish a rejected
  submission from an accepted task that later fails.
- **REQ-073-3 — Record provider behavior.** Where a real or mock response already
  exposes bounded latency, carry provider duration, retry count, provider/model
  alias, breaker state/transition, and circuit rejection count into the run
  metrics. Do not infer provider duration from the whole Agent duration when it
  is not measurable; represent unavailable values explicitly.
- **REQ-073-4 — Record single-flight behavior.** Record `owner`/`follower` role,
  follower wait duration, and coalesced-follower count. A follower must not be
  counted as an independent provider or lane execution.
- **REQ-073-5 — Preserve metric semantics across outcomes.** Completed,
  completed-degraded, rejected, budget-exceeded, circuit-open, saturated,
  timed-out, and failed accepted runs must report the metrics accumulated before
  their terminal outcome when the existing artifact boundary can safely persist
  them. Preflight failures that never create a run artifact must remain explicit
  rather than fabricating zero-duration execution.
- **REQ-073-6 — Version the artifact contract.** Additive fields must have stable
  names, types, units, and documented availability. If the `metrics.json` schema
  version changes, the benchmark normalizer and contract tests must be updated
  without rewriting the approved historical baseline as if it were newly
  measured.
- **REQ-073-7 — Keep values safe and bounded.** Metrics/traces may contain safe
  aliases, enums, booleans, counts, hashes, timestamps, and durations. They must
  never contain requirement text, prompts, evidence excerpts, provider bodies,
  credentials, exception messages, absolute paths, raw cache keys, or unbounded
  labels. All persisted strings remain subject to existing artifact sanitization
  and DLP rules.
- **REQ-073-8 — Keep clocks testable.** Inject monotonic and wall-clock sources at
  the metric boundary. Tests must not depend on sleeps or exact machine speed.
- **REQ-073-9 — Expected implementation surface.** Expected production files
  are `src/specflow/evaluation/metrics.py`,
  `src/specflow/coordinator/scheduler.py`, `src/specflow/runner_multi.py`,
  `src/specflow/agents/adapter.py`, and the minimal trace/single-flight/breaker/
  lane modules needed to expose safe observations. Expected tests are
  `tests/test_runtime_metrics.py`, `tests/test_agent_trace.py`,
  `tests/test_evaluation_multi_agent.py`, `tests/test_benchmark.py`,
  `tests/test_cli_multi_agent.py`, and relevant failure-artifact tests. A new
  metrics backend, endpoint, or dependency requires a spec amendment.

## Boundaries

The following are explicit non-goals for T-073:

- Depends on closed T-072; T-070 through T-072 behavior may receive audit hooks
  but must not be redesigned in this task.
- No Prometheus, OpenTelemetry, metrics database, dashboard, remote exporter,
  telemetry network call, sampling service, or deployment work.
- No high-cardinality raw labels, repository paths, requirements, prompts,
  evidence, provider payloads, exception bodies, or cache keys.
- No timing-based performance acceptance threshold and no claim that local mock
  timings predict live-provider or production performance.
- No topology, schema, retry, fallback, DLP, revision, cache, or preflight
  behavior change.
- No historical benchmark result may be relabeled as newly observed evidence.

## Acceptance

- **AC-073-1:** Deterministic tests verify submission ≤ start ≤ completion,
  queue duration, execution duration, and unavailable provider duration using
  injected clocks.
- **AC-073-2:** Tests cover accepted/completed, queued, rejected, cancelled,
  timed-out, circuit-open, owner, and follower metric paths without sleeps.
- **AC-073-3:** Follower metrics show coalescing but zero independent provider
  calls/lane submissions; circuit rejection is not counted as provider success;
  saturation rejection is not counted as an accepted execution.
- **AC-073-4:** Completed and failed artifact tests validate the additive
  `metrics.json`/trace contract and non-negative typed values.
- **AC-073-5:** DLP regression tests prove that requirement text, paths,
  credentials, raw provider errors, and cache/equivalence key material cannot
  enter metrics or traces.
- **AC-073-6:** Existing A/B metrics, normalized 12-case benchmark, trace,
  scheduler, CLI/mock, T-070, T-071, and T-072 tests remain green.
- **AC-073-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-073-8:** `docs/reports/T-073-completion-report.md` records field
  definitions, units, availability, safe-data review, tests, and known local
  timing limits. One focused implementation commit is created, then work stops
  before T-074.
