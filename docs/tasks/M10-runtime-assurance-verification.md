# M10 — Runtime Assurance Verification

**Status:** DRAFT FOR FREEZE. This document proposes a task sequence and its
boundaries. It does not authorize implementation. Freezing this document is a
separate, documentation-only commit that must confirm no runtime implementation,
benchmark fixture, dependency, or generated artifact was added (AC-M10-7).

## Relationship to M9

M9 (T-070 through T-076) and M10 answer different questions.

| Milestone | Question answered | Phase |
| --- | --- | --- |
| M9 · Runtime Resilience & Efficiency | Nothing that should not begin may begin; overload stays bounded | Ex-ante validation and execution-time control |
| M10 · Runtime Assurance Verification | Do the boundaries the system already declares actually hold? | Ex-post acceptance and guarantee verification |

M10 does not modify any M9 behavior. It supplies evidence for claims M9 and its
predecessors already made.

## Goal

Use executable, reproducible evidence that requires no live provider to verify
that SpecFlow Agent's **already declared** runtime guarantees — explicit failure
classification, fail-closed required-agent behavior, no silent discard, bounded
observability data, artifact integrity, and single-process limits — hold under
specified faults; and to list explicitly which declarations remain unverified
instead of leaving them to read as established.

## Requirements

- **REQ-M10-1 — Verify existing declarations, do not invent capabilities.**
  Every assurance target must trace to an existing declaration: M9 REQ-M9-4,
  REQ-M9-5, REQ-M9-6; the T-075 failure mapping; the T-057 interruption
  recovery contract; the T-071 circuit state machine; the artifact integrity
  contract; or the documented fail-closed behavior. M10 adds no product
  capability, no agent, and no topology change.

- **REQ-M10-2 — Declarations must be machine-checkable.** A guarantee may not
  exist only as prose. Each verified guarantee has a stable identifier, an
  evidence type that is executable or mechanically decidable, a result of
  `verified`, `unverified`, or `not_applicable`, and evidence references (test
  node, report path, or command).

- **REQ-M10-3 — Fault injection is deterministic and dependency-free.**
  Injection occurs through an explicit failpoint interface using injected clocks
  and explicit triggering. No `sleep`, process signal, network I/O, real timer,
  or live provider call. Failpoints are inert by default on every production
  path and must not be activatable by environment variable or external input.

- **REQ-M10-4 — Interrupted runs must land in a classified outcome.** After
  interruption at any failpoint, the run must fall inside the existing
  classified outcome set (completed, completed-degraded, failed, rejected,
  preflight failure, interrupted-lifecycle outcome) and must be expressible by
  the existing lifecycle and artifact boundaries. The following are never
  permitted: silent discard, a partial artifact presented as complete, a
  degraded result that reads as success, or an unclassifiable hanging state.

- **REQ-M10-5 — Verification adds no new side-effect surface.** Failpoints and
  audit fields obey REQ-M9-5 and must not contain prompts, requirement text,
  repository contents, absolute paths, credentials, raw provider bodies, or
  unbounded cache keys. No new network service, daemon, background thread, or
  remote telemetry.

- **REQ-M10-6 — Keep single-process guarantees honest.** Every M10 conclusion
  is valid only in a single process. Cross-process, multi-process, and
  restart-time orchestration recovery must be reported as explicitly
  **unverified**. They may not be approximated by a substitute experiment or
  described as verified on the strength of one.

- **REQ-M10-7 — `unverified` is a first-class output, not a defect.** The
  ledger must be able to report `unverified` honestly. Marking a declaration
  unverified is a valid deliverable; relaxing a judgement so the ledger looks
  better violates this milestone.

- **REQ-M10-8 — Execute in the frozen order.** Each task requires its own audit,
  targeted tests, full quality gates, completion report, focused commit, and
  stop point before the next task begins.

  | Order | Task | Dependency gate |
  | --- | --- | --- |
  | 1 | T-077 — Guarantee Boundary Ledger and Declaration Registry | M10 spec freeze |
  | 2 | T-078 — Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed |
  | 3 | T-079 — Unresolved-Item Aggregation and Assurance Status | T-078 closed |
  | 4 | T-080 — Evidence Freshness and Snapshot Integrity Bound | T-079 closed |
  | 5 | Milestone assurance review | T-077 through T-080 closed |
  | 6 | T-081 — Multi-Process Boundary Probe (explicitly non-claiming) | assurance review approved |

- **REQ-M10-9 — Preserve existing contracts.** The six-agent topology, stage
  dependencies, deterministic orchestration, handoff schemas, bounded revision,
  evidence grounding, DLP rules, safe artifacts, fail-closed required-agent
  behavior, and the documented legacy CLI, mock-only Run API, and 12-case
  benchmark contracts remain invariants throughout M10. No historical benchmark
  result may be relabeled as newly observed evidence.

- **REQ-M10-10 — Later task specifications depend on observed evidence.** The
  field-level design of T-079 depends on which outcomes T-078 actually
  produces, and the probe design of T-081 depends on the assurance review. Their
  specifications must be written after their predecessor closes, not pre-filled
  here. The committed artifacts for T-079 through T-081 are therefore
  **boundary and dependency definitions only**.

## Boundaries

The following are explicit milestone non-goals:

- No M9 task is implemented, reopened, or redesigned. M10 must not begin before
  the M9 tasks it cites are closed, and must not modify their behavior.
- No new agent, no new stage, no topology change, no dynamic agent, no
  peer-to-peer agent chat, no general-purpose DAG scheduler.
- No multi-process coordination, distributed lock, shared rate limiting,
  durable job queue, background worker, or forced cancellation of running Python
  threads.
- No resume, continuation, compensation, reconciliation, or replay capability.
  M10 only verifies what already happens after interruption. If verification
  shows that a recovery capability is missing, that becomes a proposal
  **after** M10 and must not be implemented inside it.
- No live-provider validation, deployment, publication, production-readiness, or
  performance claim.
- No third-party chaos-engineering dependency, fault-injection proxy, container
  or network interference, Prometheus, OpenTelemetry, metrics database,
  dashboard, remote exporter, or telemetry network call.
- No ledger pass obtained by weakening a judgement, skipping a case, or
  pre-filling evidence that was never produced.
- No Java, Gradle, Maven, Kotlin, or Android surface. The T-076 authorization
  does not extend into M10.
- No task may begin merely because its ID appears here. Its predecessor must be
  closed and its own frozen specification must be read in the new session.

## Acceptance

- **AC-M10-1:** This document and T-077 through T-081 use the repository
  task-spec structure and define goals, requirement IDs, explicit non-goals,
  failure semantics, expected production/test files, regression coverage, and
  executable quality gates.
- **AC-M10-2:** Every verified guarantee traces to an existing declaration
  source; no M10-invented guarantee exists.
- **AC-M10-3:** The ledger can report `unverified`, and the milestone permits a
  task to close in that state.
- **AC-M10-4:** Fault-injection cases pass deterministically in CI with no clock
  waits, no network I/O, and no provider calls.
- **AC-M10-5:** Every interrupt-matrix case records the interruption point, the
  expected classification, the observed classification, the boundary proved,
  and the boundary left unproved.
- **AC-M10-6:** Each implementation task requires targeted tests followed by
  `uv run pytest -v`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`, plus a `docs/reports/T-0XX-completion-report.md` and one
  focused commit.
- **AC-M10-7:** The specification-freeze diff contains documentation only and
  confirms that no runtime implementation, benchmark fixture, dependency, or
  generated artifact was added.
- **AC-M10-8:** The specification-freeze report records files, architecture
  decisions, task dependencies, unresolved risks, validation evidence, and the
  no-runtime-implementation confirmation.

## Open questions for reviewers

These are unresolved by design and must be settled before or during the freeze,
not silently decided during implementation.

1. **Milestone scope.** Is M10 the right container for the interrupt matrix, or
   does the matrix alone justify its own milestone with T-080 and T-081 split
   out?
2. **T-081 placement.** T-081 observes a boundary M10 explicitly refuses to
   claim. Confirm it belongs inside M10 with a non-claiming label rather than in
   a later milestone.
3. **Interrupt-matrix batch size.** Is Batch 1 (four interruption points, listed
   in T-078) the correct first increment, or is the artifact-write point alone
   sufficient to prove no partial artifact is presented as complete?
4. **`undetermined` policy.** When existing contracts do not define the
   behavior at an interruption point, should the case block the milestone close
   or be recorded as `undetermined` and routed to the ledger as `unverified`?
   T-078 currently specifies the latter.
5. **Evidence-hash finding.** T-080 asserts a code-level observation about
   `EvidenceBundle._calculate_hash()` field coverage. It is a source-code
   inference and has not been executed. Confirm whether it belongs in M10 or
   belongs in a narrower correctness task.
