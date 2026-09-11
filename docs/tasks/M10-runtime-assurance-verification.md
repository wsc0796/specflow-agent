# M10 — Runtime Assurance Verification

**Status:** DRAFT FOR FREEZE — REVISION 4 (addresses the re-review of PR #6).
Implementation is not authorized. Freezing this document is a separate,
documentation-only commit that must confirm no runtime implementation, benchmark
fixture, dependency, or generated artifact was added (AC-M10-7).

**Reader precondition:** this document cites M9 boundary clauses. Those clauses
are reproduced in Appendix A so that a reviewer or implementer without this
repository's branch history can read the dependencies. The original M9 sources
on this branch are authoritative; Appendix A is a reading copy. See REQ-M10-6
for source traceability and REQ-M10-12 for the separate implementation gate.

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
observability data, artifact integrity as actually implemented, and
single-process limits — hold under specified faults; and to record explicitly
which declarations are unverified or refuted instead of leaving them to read as
established.

## Requirements

### Verification scope and semantics

- **REQ-M10-1 — Verify existing declarations, do not invent capabilities.**
  Every assurance target must trace to a declaration that exists in the
  repository at a named declaration-source commit: an M9 clause copied in Appendix A,
  the T-075 failure mapping, the T-057 interruption recovery contract, the T-071
  circuit state machine, the artifact write path in `runner_multi.py` and
  `artifacts/store.py`, or documented fail-closed behavior. M10 adds no product
  capability, no agent, and no topology change. Record the declaration-source
  version (path, clause, commit) separately from the tested-code commit and
  effective configuration attached to execution evidence. Revision 4 starts at
  `START_HEAD=9adcddb46f2977ea122966c1167e48fe2592d8be`; that is revision
  provenance, not a substitute for either version binding. M9 declarations
  originate at `02c1d3fe9bcd8c95d6bb7cf3959328844598e473`; predecessor/source-code
  declarations must likewise name their own source commit. Future M10 experiments
  must name the code actually executed after the implementation gates are met.

- **REQ-M10-2 — Verification semantics are part of the specification.** The
  following four conditions define verification. A status may not be derived
  without all four, and each is separately checkable:

  | Question | Required by | A valid substitute does not exist |
  | --- | --- | --- |
  | Does the declaration source exist and is it the one being verified? | Declared source reference at its named declaration-source commit | Merely finding a similarly named file |
  | Did the evidence actually get produced? | A recorded execution outcome | Merely finding a test node, command, or report name |
  | Does the evidence match the code version and configuration being verified? | A recorded version or commit binding | Assuming a historical report applies to current code |
  | Do the assertions cover the declared boundary? | A recorded mapping from assertion to declaration clause | Treating any passing test as proof of the whole declaration |

- **REQ-M10-3 — States are distinct; nothing collapses into `unverified`.** The
  ledger uses four distinct states and must not merge them:

  | State | Meaning |
  | --- | --- |
  | `verified` | All four REQ-M10-2 conditions are satisfied for this declaration |
  | `declared` | The declaration exists but no evidence has been produced that targets it |
  | `refuted` | Valid recorded evidence contradicts the declaration; fault cases must satisfy REQ-M10-4 |
  | `not_applicable` | The declaration does not apply to the verified configuration |

  A **skipped** test, a **missing** execution result, a **version mismatch**, or
  an **expired or superseded** report must not produce `verified`. A
  contradiction must produce `refuted` and **must be preserved as `refuted`**
  through every summary; re-labelling it `unverified`, merging it into an
  aggregate, or dropping it from a rollup is a specification violation.

- **REQ-M10-4 — Distinguish tool correctness from claim correctness from
  milestone closure.** These are three separate verdicts that must never be
  reported as one:

  | Verdict | Question | May be reported as |
  | --- | --- | --- |
  | Mechanism verdict | Did the verification mechanism work as designed? | Yes, on its own terms |
  | Claim verdict | Did the verified declaration hold? | Yes, on its own terms |
  | Closure verdict | May this task or milestone close? | Per REQ-M10-5 |

  No execution, no actual target-fault injection, a wrong injection location or
  hit count, or incomplete observations means the mechanism failed. Such a case
  supports neither the declaration nor its refutation. A valid experiment may
  support the declaration only within its recorded coverage, or contradict it
  as `violated` / `refuted`. A mechanism that correctly reports `violated` is a
  working mechanism, **not** a passed assurance result.

- **REQ-M10-5 — Audit delivery and assurance acceptance are separate.** An
  audit task may complete its discovery, ledger, and report deliverables while
  declarations remain `declared` or `refuted`, provided it records each gap or
  contradiction, evidence, affected declaration, and effect on assurance
  acceptance. That completion does not establish the guarantee. If a valid
  counterexample violates a required guarantee, including REQ-M10-8 / AC-078-6,
  M10 assurance acceptance must fail even when the audit mechanism works.
  A required guarantee with missing or invalid evidence cannot pass either. A
  `refuted` declaration must not be closed by relaxing an expectation, widening a
  tolerance, re-labelling the state, or reclassifying the case as
  `undetermined`. Fixing the contradiction is out of scope for M10 and becomes a
  separately authorized change; recording it does not authorize a repair.

- **REQ-M10-6 — Traceable, readable citation.** Every external declaration cited
  by M10 or by a task under it must be readable by a reviewer **without leaving
  the repository, the branch, or the pull request.** This is satisfied when the
  cited source is present on this branch or on a merged ancestor of it. A
  citation that resolves only through branch history the reviewer cannot reach is
  a specification defect. Appendix A may aid reading but cannot replace a
  readable original source or implementation-completion evidence.

  Resolution note (revision 3): the cited M9 clauses are present on this branch
  at `docs/tasks/M9-runtime-resilience-efficiency.md`, and the corresponding
  specification is published on branch `docs/m9-runtime-resilience-specs`.
  Appendix A remains a reading copy of the original source; no repeated branch
  publication is needed.

### Injection and observability constraints

- **REQ-M10-7 — Fault injection is deterministic and dependency-free.**
  Injection occurs through an explicit failpoint interface using injected clocks
  and explicit triggering. No `sleep`, process signal, network I/O, real timer,
  or live provider call. Failpoints are inert by default on every production
  path and must not be activatable by environment variable, configuration, HTTP
  input, requirement text, or repository content. A registration must be scoped,
  released on completion, and isolated so one test's registration cannot affect
  another test, including under parallel execution.

- **REQ-M10-8 — Interrupted runs must land in a classified outcome.** After
  interruption at any failpoint, the run must fall inside the existing
  classified outcome set and must be expressible by the existing lifecycle and
  artifact boundaries. Silent discard, a partial artifact presented as complete,
  a degraded result that reads as success, and an unclassifiable hanging state
  are never permitted. **Scope note:** this clause constrains the behavior of
  the run, not the completion status of any individual agent or stage. Whether a
  particular agent-level outcome is defined at a given interruption point is
  exactly what REQ-M10-9 requires to be classified. These remain tested safety
  requirements: a valid counterexample fails the affected guarantee and blocks
  M10 assurance acceptance under REQ-M10-5. Completing an audit report does not
  waive them, and a pre-recorded agent-level contract gap does not waive a
  defined run-level safety boundary.

- **REQ-M10-9 — Undefined, unexecuted, and contradicted are three different
  results.**

  | Situation | Required classification |
  | --- | --- |
  | Existing contracts do not define the behavior at this point | `undetermined`, decided **before execution** from the contract text, not after seeing the result |
  | The case was skipped, unexecuted, version-mismatched, or the mechanism failed | not verified; never `consistent`; invalid evidence cannot refute the declaration either |
  | A valid experiment contradicts a declaration | `violated`; routed to the ledger as `refuted`; never converted to `undetermined` |

  `undetermined` must be listed explicitly and must not be merged into
  `consistent`.

- **REQ-M10-10 — Verification adds no new side-effect surface.** Failpoints and
  audit fields must not contain prompts, requirement text, content read from an
  analyzed target repository, absolute paths, credentials, raw provider bodies,
  or unbounded cache keys. No new network service, daemon, background thread, or
  remote telemetry.

- **REQ-M10-11 — Keep single-process guarantees honest.** Every M10 conclusion
  is valid only in a single process. Cross-process, multi-process, and
  restart-time orchestration recovery are **out of M10's required scope** and
  must be reported as explicitly unverified. They may not be approximated by a
  substitute experiment or described as verified on the strength of one.

### Execution order

- **REQ-M10-12 — Execute in the frozen order.** Each task requires its own
  audit, targeted tests, full quality gates, completion report, focused commit,
  and stop point before the next task begins.

  | Order | Task | Dependency gate | Gate evidence required |
  | --- | --- | --- | --- |
  | 1 | T-077 — Guarantee Boundary Ledger and Declaration Registry | Independently approved M10 spec freeze; readable declaration sources; T-070 through T-075 implementation closed | Freeze decision and commit; source path/clause/commit; readable completion report and implementation commit for each dependency below |
  | 2 | T-078 — Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed | T-077 completion report path and its commit hash |
  | 3 | T-080 — Evidence and Artifact Integrity Contract Audit | T-078 closed | T-078 completion report path and its commit hash |
  | 4 | T-079 — Run-Local and Project-Level Assurance Reporting | T-078 and T-080 closed | Both completion report paths and commit hashes |
  | 5 | Milestone assurance review | T-077, T-078, T-080, T-079 closed | The four completion reports plus the ledger at its final state |

  A gate is satisfied only by readable evidence at a named commit, not by an
  assertion in a chat transcript or by the task ID appearing in this table.

  The required M9 implementations follow from the current declaration set and
  its existing sequential dependencies, not from every task belonging to M9:

  | Required implementation | Declaration/dependency basis | Completion evidence at START_HEAD |
  | --- | --- | --- |
  | T-070 | REQ-M9-4 duplicate ownership; REQ-070-4/-5/-8; predecessor of T-071 | Not satisfied: readable completion report and implementation commit not available |
  | T-071 | REQ-M9-4 open circuits; REQ-071-2/-5/-7; predecessor of T-072 | Not satisfied: readable completion report and implementation commit not available |
  | T-072 | REQ-M9-4 saturation/no silent discard; REQ-072-3/-4/-6; predecessor of T-073 | Not satisfied: readable completion report and implementation commit not available |
  | T-073 | REQ-M9-5 safe observability; REQ-073-5/-7; predecessor of T-074 | Not satisfied: readable completion report and implementation commit not available |
  | T-074 | REQ-M9-4 invalid cache entries; REQ-074-3/-5/-7; predecessor of T-075 | Not satisfied: readable completion report and implementation commit not available |
  | T-075 | REQ-075-9 failure mapping, directly cited by REQ-M10-1 | Not satisfied: readable completion report and implementation commit not available |

  The corresponding `docs/tasks/T-070-*` through `T-075-*` specifications are
  readable on this branch at the M9 declaration-source commit. That establishes
  source readability only. Each implementation requires its own readable
  completion report and implementation commit, with evidence applicable to the
  tested-code version/configuration. T-076 Java/Maven is not a dependency of this
  verification scope. If a required dependency or its evidence cannot be
  determined, name the unresolved item and keep the entry blocked.

  Source readability, M9 implementation completion, M10 document freeze, and
  permission to begin M10 implementation are four separate facts. Revision 4 may
  be revised and submitted for review now; its independent freeze approval is
  pending and the required M9 implementation evidence is not satisfied, so M10
  implementation remains blocked.

- **REQ-M10-13 — Preserve existing contracts.** The six-agent topology, stage
  dependencies, deterministic orchestration, handoff schemas, bounded revision,
  evidence grounding, DLP rules, safe artifacts, fail-closed required-agent
  behavior, and the documented legacy CLI, mock-only Run API, and 12-case
  benchmark contracts remain invariants throughout M10. No historical benchmark
  result may be relabeled as newly observed evidence.

## Boundaries

The following are explicit milestone non-goals:

- No M9 task is implemented, reopened, or redesigned.
- No new agent, no new stage, no topology change, no dynamic agent, no
  peer-to-peer agent chat, no general-purpose DAG scheduler.
- **No multi-process observation, multi-process coordination, distributed lock,
  shared rate limiting, durable job queue, background worker, or forced
  cancellation of running Python threads.** Process-level kill, signals, and
  real crashes are not assigned to any M10 task; no task claims them.
- No resume, continuation, compensation, reconciliation, or replay capability.
  M10 only verifies what already happens after interruption. If verification
  shows that a recovery capability is missing, that becomes a proposal **after**
  M10 and must not be implemented inside it.
- No live-provider validation, deployment, publication, production-readiness, or
  performance claim.
- No third-party chaos-engineering dependency, fault-injection proxy, container
  or network interference, Prometheus, OpenTelemetry, metrics database,
  dashboard, remote exporter, or telemetry network call.
- No ledger pass obtained by weakening a judgement, skipping a case, pre-filling
  evidence that was never produced, or re-labelling a contradiction.
- No Java, Gradle, Maven, Kotlin, or Android surface. The T-076 authorization
  does not extend into M10.
- No task may begin merely because its ID appears here. Its predecessor must be
  closed with readable evidence, and its own frozen specification must be read
  in the new session. In particular T-077 requires the complete REQ-M10-12 gate;
  readable M9 specifications alone do not authorize any M10 implementation.

## Acceptance

- **AC-M10-1:** This document and each task carry the structure used by M9 and
  T-070 through T-076: status line, goal, requirement IDs, boundaries,
  acceptance, expected implementation surface, and stop point. T-077 and T-078
  are fully specified in this revision. T-079 and T-080 are specified in this
  revision at the level of scope, entry points, and judgement criteria, with
  field-level detail deferred to their own freeze after their predecessor
  closes, as permitted by REQ-M10-12.
- **AC-M10-2:** Every verified guarantee traces to a declaration a reviewer can read on
  this branch, per REQ-M10-6.
- **AC-M10-3:** The ledger distinguishes `verified`, `declared`, `refuted`, and
  `not_applicable`. Audit delivery may complete under REQ-M10-5; M10 assurance
  acceptance cannot pass with a refuted or unverified required guarantee.
- **AC-M10-4:** Fault-injection mechanism checks pass deterministically in CI
  with no clock waits, no network I/O, and no provider calls. Claim verdicts and
  assurance acceptance are reported separately per REQ-M10-4/-5/-8; a passing
  mechanism test that records a counterexample is not a passed guarantee.
- **AC-M10-5:** Every interrupt-matrix case records the interruption point, the
  injected fault type, the real entry point exercised, the expected and observed
  classification, the declaration it targets, the boundary proved, and the
  boundary left unproved. Expected and actual failpoint IDs, actual hit count
  against the case preset, and actual injected fault must satisfy REQ-078-12;
  invalid injection evidence produces mechanism failure, not claim evidence.
- **AC-M10-6:** Each implementation task requires targeted tests followed by
  `uv run pytest -v`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`, plus a `docs/reports/T-0XX-completion-report.md` and one
  focused commit.
- **AC-M10-7:** The specification-freeze diff contains documentation only and
  confirms that no runtime implementation, benchmark fixture, dependency, or
  generated artifact was added.
- **AC-M10-8:** The specification-freeze report records files, architecture
  decisions, task dependencies, unresolved risks, validation evidence, and the
  no-runtime-implementation confirmation. It and T-077 Status apply the same
  REQ-M10-12 gate: approved freeze plus readable sources plus a readable
  completion report and implementation commit for each of T-070 through T-075.
  Missing evidence remains explicitly not satisfied. Source versions,
  tested-code versions/configurations, and START_HEAD are recorded separately.

## Appendix A — Cited M9 clauses (reproduced for traceability)

Source: `docs/tasks/M9-runtime-resilience-efficiency.md`, milestone specification
frozen in commit `02c1d3fe9bcd8c95d6bb7cf3959328844598e473`, now present on this
branch and published on branch `docs/m9-runtime-resilience-specs` (remote
`02c1d3f`). These clauses are reproduced here as a reading copy of the original
source, so the dependency can be read and diffed without leaving the pull
request. Verbatim text:

> **REQ-M9-4 — Use explicit failure semantics.** Duplicate ownership, open
> circuits, saturated lanes, invalid cache entries, and preflight failures must
> become safe, classified, auditable outcomes. Accepted work must never be
> silently discarded, and no rejected operation may be reported as provider or
> workflow success.

> **REQ-M9-5 — Keep observability safe.** Metrics and audit fields may contain
> bounded identifiers, hashes, categories, counts, lanes, roles, states, and
> durations. They must not contain prompts, requirements, repository contents,
> absolute local paths, credentials, raw provider bodies, or unbounded cache
> keys.

> **REQ-M9-6 — Keep guarantees local.** T-070 through T-075 provide only
> single-process guarantees. They must not claim multi-process coordination,
> distributed locks, shared rate limiting, durable job execution, background
> workers, or forced cancellation of running Python threads.

Interpretation recorded for M10: REQ-M9-4's "accepted work must never be silently
discarded" constrains the run's behavior, not the completion status of an
individual agent. M10 verifies the run-level clause and classifies agent-level
behavior as `undetermined` where the contract does not define it.

## Open questions — resolved by review

The five questions raised in revision 1 of `REVIEW-REQUEST.md` were answered by
the PR #6 review and are recorded here as decisions:

| Question | Decision |
| --- | --- |
| Is M10 the right container for the interrupt matrix? | **Yes.** The ledger plus the interrupt matrix is the core: decide what to verify, then collect supporting or contradicting evidence. |
| Does T-081 belong in M10? | **No.** Removed from M10's required scope. The single-process limitation is stated instead. |
| Is Batch 1 (four interruption points) the correct first increment? | **Yes, keep all four** as the complete Batch 1 range. The artifact-write case may be implemented first to open the evidence chain, but it does not substitute for the other three. |
| May `undetermined` be used when the contract is undefined? | **Allowed only when the absence of a definition is established before execution.** A contradiction must remain `violated` and must not become `undetermined`. |
| How should the T-080 hash observation be handled? | **Narrowed to a contract audit.** Separate `evidence_hash` semantics, artifact file hashing, and freshness; audit the declared contract against the implementation. Revision 4 confirms that any runtime repair needs separate authorization outside T-080. |
