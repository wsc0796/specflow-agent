# T-071 — Provider Resilience Guard

**Status:** FROZEN. Implementation requires T-070 to be closed and a new focused
session.

## Goal

Add deterministic, bounded resilience state around live provider/model calls so
repeated transient provider failures open an explicit circuit and later allow
bounded half-open probes, while preserving existing retry, fallback, error,
mock, schema, and audit semantics.

## Requirements

- **REQ-071-1 — Scope state by provider resource.** Maintain independent
  process-local state for the exact `(provider, model)` key authorized here.
  The key must use bounded normalized identifiers and must not contain base
  URLs, API keys, prompts, request bodies, repository data, or tenant/user data.
- **REQ-071-2 — Implement the state machine.** Provide explicit
  `CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN` behavior with configurable positive
  thresholds, open duration, and bounded half-open probe count. Use an injected
  monotonic clock so transition tests require no wall-clock sleeps.
- **REQ-071-3 — Count only classified provider availability failures.** Reuse
  the existing error taxonomy. Provider timeout, rate limit, server, and
  connection failures may count toward opening. Authentication, model-not-found,
  invalid JSON, schema mismatch, security, policy, artifact, and local coding
  errors must retain their existing classifications and must not be mislabeled
  as circuit health failures.
- **REQ-071-4 — Keep one retry owner.** The guard wraps actual live provider
  attempts and reports their result; it must not create a second retry loop.
  Existing AgentRunner/FallbackManager retry budgets remain the retry owners.
  Failure accounting occurs once per real provider attempt, not once per
  fallback result or degraded envelope.
- **REQ-071-5 — Reject open circuits explicitly.** An OPEN circuit rejects
  before network I/O with a new safe provider-circuit error. The rejection is
  non-retryable within the same request, may flow into the existing honest
  fallback/degraded path where that path is already allowed, and must never look
  like a successful provider response. A HALF_OPEN probe is exclusive up to the
  configured probe bound; excess probes are rejected explicitly.
- **REQ-071-6 — Integrate both live pipelines.** Legacy and multi-agent live
  calls must pass through the same guard contract. Mock mode bypasses live
  resilience state entirely: it neither opens a circuit nor consumes half-open
  probes, and remains deterministic.
- **REQ-071-7 — Clean up safely.** Every permitted call must release its probe
  slot after success or failure. Exceptions must not strand a HALF_OPEN probe or
  corrupt another provider/model's state. State access must be thread-safe.
- **REQ-071-8 — Keep audit data bounded.** Expose only safe state, transition,
  rejection, failure-count, provider alias, and model alias metadata required by
  T-073. Do not log exception bodies, credentials, prompts, raw provider output,
  or unbounded registry keys.
- **REQ-071-9 — Expected implementation surface.** Expected production files
  are a focused `src/specflow/llm/resilience.py`,
  `src/specflow/llm/providers/openai_compatible.py` or a shared LLM decorator,
  `src/specflow/agents/adapter.py`, `src/specflow/runner.py`,
  `src/specflow/runner_multi.py`, and the minimum policy/error/default files.
  Expected tests are `tests/test_provider_resilience.py`,
  `tests/test_openai_compatible_provider.py`, `tests/test_fallback.py`,
  `tests/test_cli.py`, and `tests/test_cli_multi_agent.py`. If integration would
  duplicate retry/fallback ownership or require a third-party dependency, stop
  and amend the specification with evidence before editing.

## Boundaries

The following are explicit non-goals for T-071:

- Depends on closed T-070; do not reopen its equivalence contract except for
  compatible audit hooks.
- No Resilience4j or other third-party resilience dependency unless a separately
  reviewed spec amendment proves the standard library design insufficient.
- No Agent-level circuit: six agents sharing one provider/model share that
  provider resource state; Agent IDs do not create separate breakers.
- No distributed breaker, persistence across restart, external health probe,
  provider failover router, load balancer, or background recovery task.
- No new retry budget, unbounded probe traffic, sleep-based tests, or network
  dependent tests.
- No change to schema validation, DLP, topology, revision, or business
  PASS/REJECT semantics.

## Acceptance

- **AC-071-1:** Deterministic unit tests cover CLOSED success, counted failures,
  threshold opening, OPEN rejection without transport calls, clock-driven
  transition to HALF_OPEN, probe success closing, probe failure reopening, and
  excess probe rejection.
- **AC-071-2:** Separate provider/model keys do not share failure state; bounded
  registry behavior and thread safety are covered.
- **AC-071-3:** Tests prove counted transient failures versus excluded auth,
  model, JSON, schema, security, and internal failures using the existing
  taxonomy.
- **AC-071-4:** Integration tests prove retry counts are unchanged, one real
  attempt is counted once, circuit rejection is safe/non-success, and allowed
  fallback remains honest and degraded.
- **AC-071-5:** Mock clients remain deterministic and never alter or consult live
  breaker state. No test performs network I/O.
- **AC-071-6:** Existing live-provider transport safety, CLI/mock, fallback,
  schema, DLP, and T-070 concurrency tests remain green.
- **AC-071-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-071-8:** `docs/reports/T-071-completion-report.md` records the state key,
  counted failures, retry ownership, mock boundary, tests, and known
  single-process limit. One focused implementation commit is created, then work
  stops before T-072.
