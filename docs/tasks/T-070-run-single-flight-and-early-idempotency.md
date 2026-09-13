# T-070 — Run Single-Flight and Early Idempotency

**Status:** FROZEN. Implementation requires the M9 specification-freeze commit
and a new focused session.

## Goal

Prevent concurrent equivalent runs in the supported single-process runtime
from independently consuming evidence, provider, and artifact resources while
preserving explicit ownership, auditable Run identities, deterministic follower
outcomes, and safe cleanup after every terminal path.

## Requirements

- **REQ-070-1 — Derive equivalence before expensive execution.** Introduce one
  canonical equivalence-key builder before evidence collection, semantic plan
  enrichment, provider calls, scheduler submission, or artifact-directory
  creation. The versioned key must include every semantic input that can change
  a run result:
  - canonical repository identity plus a deterministic early repository
    snapshot token obtained through the existing safe repository boundary;
  - the exact requirement hash;
  - execution mode and mock/live mode;
  - effective provider and model;
  - the complete execution-policy hash;
  - fixed-topology, schema, prompt/enrichment, sanitizer, and artifact-contract
    versions that affect behavior; and
  - any other runtime configuration demonstrated by tests to affect output.
  Request IDs and output-directory paths are audit/storage identities and must
  not make otherwise equivalent work appear semantically different. If a safe
  snapshot token cannot be derived, the run must fail before joining an
  in-flight owner.
- **REQ-070-2 — Add a process-local ownership coordinator.** For a key with no
  owner, exactly one caller becomes `owner`. A concurrent equivalent caller
  becomes `follower`, does not launch evidence/provider/scheduler/artifact work,
  and waits only for the bounded owner outcome. Registration and lookup must be
  thread-safe.
- **REQ-070-3 — Preserve audit identity.** The owner keeps the canonical
  execution/artifact identity. Each accepted Run API request retains its own
  durable `WorkflowRun` identity and records safe single-flight metadata,
  including `owner`/`follower` role and the owner Run ID where applicable.
  Followers may reference the owner's completed artifact directory only through
  the existing bounded relative-artifact contract. The API or persisted audit
  record must make coalescing observable; it must never masquerade as an
  independently executed run.
- **REQ-070-4 — Define deterministic follower outcomes.** On owner success, a
  follower receives the same terminal result class and an auditable shared
  artifact reference. On owner classified failure, a follower receives the
  same safe terminal classification without rerunning. On owner exception, all
  followers are released with a safe runtime failure. A follower wait timeout
  is explicit and must not start duplicate work.
- **REQ-070-5 — Guarantee cleanup.** Owner success, classified failure,
  unexpected exception, artifact failure, caller cancellation, and follower
  timeout paths must leave no permanently stuck in-flight entry. Cleanup must
  occur in a `finally`-equivalent path. A later request after cleanup may become
  a new owner and retry normally.
- **REQ-070-6 — Integrate with existing admission safely.** An equivalent
  follower must be able to join its owner without consuming a second expensive
  execution permit. A different key remains subject to the existing Run API
  concurrency/rate limits. Reordering admission must not weaken authentication,
  repository allowlisting, or per-minute accounting.
- **REQ-070-7 — Keep mock and CLI deterministic.** Mock mode must use the same
  ownership contract without timing randomness. Legacy and multi-agent CLI
  behavior, exit codes, deterministic run IDs, and completed artifact contracts
  must remain compatible.
- **REQ-070-8 — Use safe failure semantics.** Key derivation and ownership
  errors must use bounded `SpecFlowError`/Run error codes with no repository
  path, requirement text, key material, exception text, or credentials. Owner
  business rejection is not a runtime failure; owner infrastructure failure is
  never reported as success.
- **REQ-070-9 — Expected implementation surface.** Audit and normally limit the
  production change to a focused single-flight module plus
  `src/specflow/runner_multi.py`, `src/specflow/runs.py`,
  `src/specflow/api_security.py`, `src/specflow/policy/models.py`, and only the
  minimal CLI/legacy integration needed to preserve both entry points. Expected
  tests are `tests/test_run_single_flight.py`, `tests/test_runs.py`,
  `tests/test_api_security.py`, and `tests/test_cli_multi_agent.py`. If the
  implementation needs a different production module or persistence column,
  stop and amend this frozen specification before editing it.

## Boundaries

The following are explicit non-goals for T-070:

- No multi-process, cross-host, distributed, Redis, database-lock, file-lock, or
  durable-after-restart guarantee.
- No queue, background worker, resume engine, retry scheduler, or forced thread
  cancellation.
- No TTL result cache and no reuse of stale Agent/provider output; T-070 only
  coalesces work that is concurrently in flight.
- No topology, stage-dependency, schema, prompt, DLP, fallback, revision, or
  artifact-contract change beyond the explicit owner/follower audit metadata.
- No repository mutation support. If the early snapshot cannot establish safe
  equivalence, fail or keep requests distinct rather than guessing.
- No T-071 provider breaker, T-072 lane scheduler, or T-074 reusable cache work.

## Acceptance

- **AC-070-1:** Two equivalent concurrent direct callers produce exactly one
  evidence/provider/scheduler/artifact execution; one is auditable as owner and
  the other as follower.
- **AC-070-2:** Concurrent requests with different requirement, repository
  snapshot, policy, mode, provider, model, or relevant version do not coalesce.
- **AC-070-3:** Owner success, classified failure, unexpected exception,
  follower timeout/cancellation, cleanup, and later retry are covered with
  deterministic injected synchronization rather than sleeps.
- **AC-070-4:** Two equivalent Run API calls preserve distinct WorkflowRun audit
  identities, do not consume duplicate execution capacity, and expose the same
  safe outcome/artifact relationship. A different concurrent request still
  obeys the existing 429 boundary.
- **AC-070-5:** No test can leave an in-flight key after its owner terminal path;
  a focused invariant test inspects the coordinator through a supported query or
  injected fake rather than private global-state leakage.
- **AC-070-6:** Existing CLI/mock, Run API authentication/allowlist, rate-limit,
  runner failure, interruption recovery, and artifact tests remain green.
- **AC-070-7:** Targeted concurrency/API tests pass, followed by
  `uv run pytest -v`, `uv run ruff check .`,
  `uv run ruff format --check .`, and `git diff --check`.
- **AC-070-8:** `docs/reports/T-070-completion-report.md` records the key
  contract, owner/follower semantics, tests, known single-process limit, and
  exact validation output. One focused implementation commit is created, then
  work stops before T-071.
