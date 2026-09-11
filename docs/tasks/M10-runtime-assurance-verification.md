# M10 — Runtime Assurance Verification

**Status:** DRAFT FOR FREEZE — REVISION 2 (addresses the review of PR #6).
Implementation is not authorized. Freezing this document is a separate,
documentation-only commit that must confirm no runtime implementation, benchmark
fixture, dependency, or generated artifact was added (AC-M10-7).

**Reader precondition:** this document cites M9 boundary clauses. Those clauses
are reproduced in Appendix A so that a reviewer or implementer without this
repository's branch history can read the dependencies. See REQ-M10-11 for the
traceability requirement this appendix exists to satisfy.

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
  repository at the frozen base commit: an M9 clause reproduced in Appendix A,
  the T-075 failure mapping, the T-057 interruption recovery contract, the T-071
  circuit state machine, the artifact write path in `runner_multi.py` and
  `artifacts/store.py`, or documented fail-closed behavior. M10 adds no product
  capability, no agent, and no topology change.

- **REQ-M10-2 — Verification semantics are part of the specification.** The
  following four conditions define verification. A status may not be derived
  without all four, and each is separately checkable:

  | Question | Required by | A valid substitute does not exist |
  | --- | --- | --- |
  | Does the declaration source exist and is it the one being verified? | Declared source reference at the frozen base commit | Merely finding a similarly named file |
  | Did the evidence actually get produced? | A recorded execution outcome | Merely finding a test node, command, or report name |
  | Does the evidence match the code version and configuration being verified? | A recorded version or commit binding | Assuming a historical report applies to current code |
  | Do the assertions cover the declared boundary? | A recorded mapping from assertion to declaration clause | Treating any passing test as proof of the whole declaration |

- **REQ-M10-3 — States are distinct; nothing collapses into `unverified`.** The
  ledger uses four distinct states and must not merge them:

  | State | Meaning |
  | --- | --- |
  | `verified` | All four REQ-M10-2 conditions are satisfied for this declaration |
  | `declared` | The declaration exists but no evidence has been produced that targets it |
  | `refuted` | A recorded observation contradicts the declaration |
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

  A mechanism that correctly reports `violated` is a working mechanism. It is
  **not** a passed assurance result, and the existence of a contradiction must
  not be presented as runtime assurance acceptance.

- **REQ-M10-5 — Closing with unverified or refuted declarations.** A task may
  close with declarations in state `declared`. A task may close with declarations
  in state `refuted` only if it records, for each one, the contradiction
  evidence, the affected declaration, and the impact on milestone closure. A
  `refuted` declaration must not be closed by relaxing an expectation, widening a
  tolerance, re-labelling the state, or reclassifying the case as
  `undetermined`. Fixing the contradiction is out of scope for M10 and becomes a
  separate proposal.

- **REQ-M10-6 — Traceable citation.** Every external declaration cited by M10 or
  by a task under it must be reproducible from the frozen base commit. Where the
  cited material is not present in the repository at that commit, the citation
  must be reproduced in Appendix A with its exact wording and its source
  identifier. Referencing material that a reviewer cannot read is a
  specification defect.

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
  exactly what REQ-M10-9 requires to be classified.

- **REQ-M10-9 — Undefined, unexecuted, and contradicted are three different
  results.**

  | Situation | Required classification |
  | --- | --- |
  | Existing contracts do not define the behavior at this point | `undetermined`, decided **before execution** from the contract text, not after seeing the result |
  | The case could not be executed | not verified; never `consistent` |
  | An observation contradicts a declaration | `violated`; routed to the ledger as `refuted`; never converted to `undetermined` |

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
  | 1 | T-077 — Guarantee Boundary Ledger and Declaration Registry | M10 spec freeze; M9 clause sources reproducible per REQ-M10-6 | Freeze commit hash; the Appendix A citations resolving at the frozen base commit |
  | 2 | T-078 — Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed | T-077 completion report path and its commit hash |
  | 3 | T-080 — Evidence and Artifact Integrity Contract Audit | T-078 closed | T-078 completion report path and its commit hash |
  | 4 | T-079 — Run-Local and Project-Level Assurance Reporting | T-078 and T-080 closed | Both completion report paths and commit hashes |
  | 5 | Milestone assurance review | T-077, T-078, T-080, T-079 closed | The four completion reports plus the ledger at its final state |

  A gate is satisfied only by readable evidence at a named commit, not by an
  assertion in a chat transcript or by the task ID appearing in this table.

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
  in the new session.

## Acceptance

- **AC-M10-1:** This document and each task carry the structure used by M9 and
  T-070 through T-076: status line, goal, requirement IDs, boundaries,
  acceptance, expected implementation surface, and stop point. T-077 and T-078
  are fully specified in this revision. T-079 and T-080 are specified in this
  revision at the level of scope, entry points, and judgement criteria, with
  field-level detail deferred to their own freeze after their predecessor
  closes, as permitted by REQ-M10-12.
- **AC-M10-2:** Every verified guarantee traces to a declaration that a reviewer
  can reproduce from the frozen base commit, per REQ-M10-6.
- **AC-M10-3:** The ledger distinguishes `verified`, `declared`, `refuted`, and
  `not_applicable`, and the milestone permits closing a task while declarations
  remain `declared` or `refuted` under REQ-M10-5.
- **AC-M10-4:** Fault-injection cases pass deterministically in CI with no clock
  waits, no network I/O, and no provider calls.
- **AC-M10-5:** Every interrupt-matrix case records the interruption point, the
  injected fault type, the real entry point exercised, the expected and observed
  classification, the declaration it targets, the boundary proved, and the
  boundary left unproved.
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

## Appendix A — Cited M9 clauses (reproduced for traceability)

Source: `docs/tasks/M9-runtime-resilience-efficiency.md`, milestone specification
frozen in commit `02c1d3fe9bcd8c95d6bb7cf3959328844598e473`. **That commit is not
reachable from `origin/main` at the M10 frozen base; these clauses are reproduced
here so the dependency is readable without branch history.** Verbatim text:

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
| How should the T-080 hash observation be handled? | **Narrowed to a contract audit.** Separate `evidence_hash` semantics, artifact file hashing, and freshness; confirm the contract and the implementation before deciding whether any change is needed; do not assume M10's guarantee widens. |
