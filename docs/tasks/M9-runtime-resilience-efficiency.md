# M9 — Runtime Resilience & Efficiency

**Status:** FROZEN FOR SEQUENTIAL IMPLEMENTATION. This document authorizes only
the task sequence below; it does not authorize implementing more than one task
per focused change.

## Goal

Add bounded, auditable runtime resilience and efficiency controls to SpecFlow
Agent without replacing the fixed six-agent topology, weakening security or
schema boundaries, or claiming distributed or production guarantees that have
not been demonstrated.

## Requirements

- **REQ-M9-1 — Preserve the runtime contract.** The six-agent topology, stage
  dependencies, deterministic orchestration, strict handoff schemas, bounded
  revision, evidence grounding, DLP rules, safe artifacts, and fail-closed
  required-agent behavior remain invariants throughout M9.
- **REQ-M9-2 — Transfer concepts, not code.** The milestone may use engineering
  patterns observed in the authorized `cms-flow` reference—single-process
  single-flight, circuit breaking, execution-resource isolation, bounded
  admission, saturation metrics, content-addressed caching, and preflight
  validation—but must implement Python designs native to SpecFlow. No
  `cms-flow` source may be copied into production code.
- **REQ-M9-3 — Execute in the frozen order.** Each task requires its own audit,
  targeted tests, full quality gates, completion report, focused commit, and
  stop point before the next task begins.

  | Order | Task | Dependency gate |
  | --- | --- | --- |
  | 1 | T-070 — Run Single-Flight and Early Idempotency | M9 spec freeze |
  | 2 | T-071 — Provider Resilience Guard | T-070 closed |
  | 3 | T-072 — Execution Lanes and Bounded Admission | T-071 closed |
  | 4 | T-073 — Runtime Saturation and Latency Metrics | T-072 closed |
  | 5 | T-074 — Content-Addressed Evidence and Context Cache | T-073 closed |
  | 6 | T-075 — Unified Run Preflight Validator | T-074 closed |
  | 7 | Milestone runtime review | T-070 through T-075 closed |
  | 8 | T-076 — Java/Maven Repository Profile and `cms-flow` Benchmark | runtime review approved |

- **REQ-M9-4 — Use explicit failure semantics.** Duplicate ownership, open
  circuits, saturated lanes, invalid cache entries, and preflight failures must
  become safe, classified, auditable outcomes. Accepted work must never be
  silently discarded, and no rejected operation may be reported as provider or
  workflow success.
- **REQ-M9-5 — Keep observability safe.** Metrics and audit fields may contain
  bounded identifiers, hashes, categories, counts, lanes, roles, states, and
  durations. They must not contain prompts, requirements, repository contents,
  absolute local paths, credentials, raw provider bodies, or unbounded cache
  keys.
- **REQ-M9-6 — Keep guarantees local.** T-070 through T-075 provide only
  single-process guarantees. They must not claim multi-process coordination,
  distributed locks, shared rate limiting, durable job execution, background
  workers, or forced cancellation of running Python threads.
- **REQ-M9-7 — Authorize Java narrowly and late.** The frozen T-076
  specification is the sole authorization to expand repository understanding
  from the Python MVP to the listed Java/Maven evidence. Earlier tasks must not
  add Java support, and T-076 must not imply general polyglot, compiler, build,
  or parser support.
- **REQ-M9-8 — Preserve existing entry points.** Legacy CLI, multi-agent CLI,
  deterministic mock mode, the mock-only Run API, and the existing 12-case
  portfolio benchmark must retain their documented contracts unless an
  individual frozen task explicitly names and tests a compatible extension.

## Boundaries

The following are explicit milestone non-goals:

- No Redis, Celery, message queue, background worker, distributed lock, vector
  store, LangGraph, or general-purpose DAG scheduler.
- No dynamic agents, peer-to-peer agent chat, topology changes, extra revision
  rounds, schema bypass, or ungrounded Agent output.
- No silent executor discard policy. The `cms-flow` reference contains
  discard-style paths; those are explicitly rejected for SpecFlow accepted
  work and critical side effects.
- No TTL-only reuse of Agent output, plan output, review output, provider
  response, or artifact bundle.
- No live-provider validation, deployment, publication, production-readiness,
  or performance claim without a separately authorized and recorded gate.
- No Java support before T-076 and no Gradle, Kotlin, Android, arbitrary XML,
  Java compilation, Maven execution, or dependency resolution in T-076.
- No task may begin merely because its ID appears here. Its predecessor must be
  closed and its own frozen specification must be read in the new session.

## Acceptance

- **AC-M9-1:** This milestone document and T-070 through T-076 use the repository
  task-spec structure and define goals, requirement IDs, explicit non-goals,
  failure semantics, expected production/test files, regression coverage, and
  executable quality gates.
- **AC-M9-2:** The dependency order is unambiguous, with a mandatory runtime
  review between T-075 and T-076.
- **AC-M9-3:** T-070 through T-075 retain the Python-only product boundary; only
  T-076 explicitly authorizes the named Java/Maven profile delta.
- **AC-M9-4:** Every implementation task requires targeted tests plus
  `uv run pytest -v`, `uv run ruff check .`, and
  `uv run ruff format --check .`, followed by a completion report and one
  focused commit.
- **AC-M9-5:** The specification-freeze diff contains documentation only and
  confirms that no runtime implementation, benchmark fixture, dependency, or
  generated artifact was added.
- **AC-M9-6:** The specification-freeze report records files, architecture
  decisions, task dependencies, unresolved risks, validation evidence, and the
  no-runtime-implementation confirmation.
