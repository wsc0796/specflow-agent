# Review request — M10 Runtime Assurance Verification (specification draft)

**This branch contains documentation only.** It adds no runtime implementation,
no test, no benchmark fixture, no dependency, and no generated artifact. Please
verify that claim before reviewing content.

**Branch:** `docs/m10-runtime-assurance-spec`
**Based on:** `1b44127` (`origin/main`)
**Repository:** `wsc0796/specflow-agent`
**Reviewer:** any agent or human asked to audit specification quality

---

## 1. What is being proposed

A new milestone, **M10 — Runtime Assurance Verification**, that verifies runtime
guarantees the system **already declares** but has never demonstrated. It is the
complement of M9, not an extension of it:

| Milestone | Question | Phase |
| --- | --- | --- |
| M9 (T-070..T-076, frozen) | Nothing that should not begin may begin; overload stays bounded | Ex-ante validation and execution-time control |
| M10 (T-077..T-081, this draft) | Do the declared boundaries actually hold? | Ex-post acceptance and guarantee verification |

Five proposed tasks:

| Order | Task | Dependency gate |
| --- | --- | --- |
| 1 | T-077 Guarantee Boundary Ledger and Declaration Registry | M10 spec freeze |
| 2 | T-078 Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed |
| 3 | T-079 Unresolved-Item Aggregation and Assurance Status | T-078 closed |
| 4 | T-080 Evidence Freshness and Snapshot Integrity Bound | T-079 closed |
| 5 | Milestone assurance review | T-077..T-080 closed |
| 6 | T-081 Multi-Process Boundary Probe (explicitly non-claiming) | assurance review approved |

## 2. Files in this branch

| File | Content |
| --- | --- |
| `docs/tasks/M10-runtime-assurance-verification.md` | Milestone spec: goal, REQ-M10-1..10, boundaries, milestone acceptance, open questions |
| `docs/tasks/T-077-guarantee-boundary-ledger.md` | Full task spec for T-077 |
| `docs/tasks/T-078-deterministic-failpoints.md` | Full task spec for T-078 |
| `docs/tasks/M10-remaining-task-boundaries.md` | Boundary-only definitions for T-079, T-080, T-081 |
| `docs/reports/M10-specification-freeze-report.md` | Freeze report in the M9 report format |
| `REVIEW-REQUEST.md` | This file |

The intended shape and review discipline mirror the closed M9 freeze, which
reviewers can compare against directly: `docs/tasks/M9-runtime-resilience-efficiency.md`
and `docs/reports/M9-specification-freeze-report.md`, frozen in commit `02c1d3f`
on branch `docs/m9-runtime-resilience-specs`.

## 3. What to check

Please report findings as `blocking`, `should-fix`, or `observation`, each with
the file and section it refers to. A finding without a location is not
actionable.

1. **Non-claim inflation.** Does any requirement in M10 imply a guarantee that is
   broader than its own stated evidence? In particular, does anything in T-080 or
   T-081 read as a resilience, coordination, or correctness claim?
2. **Traceability.** Is each verification target in REQ-M10-1 actually traceable
   to a declaration that exists in the repository today? Name any target that is
   not.
3. **Cheatable acceptance.** Is any acceptance criterion satisfiable without
   running the verification — for example by editing a document, widening an
   expectation, or marking a result `verified` with no resolvable evidence? Cite
   the criterion.
4. **Scope creep.** Are the non-goals in `M10-runtime-assurance-verification.md`
   and in each task sufficient to prevent recovery, resume, multi-process
   coordination, or topology work from entering through an implementation
   session? Identify the weakest non-goal.
5. **Test purity.** Can the failpoint interface in T-078 be activated outside a
   test process by any route the requirements do not explicitly forbid? List any
   route not covered by REQ-078-1 and AC-078-1.
6. **Phase leakage.** M10 depends on M9 tasks that are not closed
   (T-070 through T-076). Does the milestone document make that dependency
   unmissable, or could an implementer start T-077 while M9 is still open?
7. **Decomposition validity.** Is the dependency order in REQ-M10-8 correct? Name
   any task whose stated output cannot be produced before its predecessor's
   output exists.
8. **Boundary-only placeholders.** `M10-remaining-task-boundaries.md`
   deliberately leaves T-079 through T-081 unspecified at field level. Is that
   consistent with the repository's task discipline, or does it violate it?
9. **Language and format debt.** Does anything deviate from the structure used by
   M9 and T-070 through T-076 (status line, requirement IDs, boundaries,
   acceptance, expected implementation surface, stop point)?

## 4. Questions the author has not resolved

These are recorded in the milestone document and are intentionally open. A verdict
on each is requested; the author prefers a decision over a range of options.

1. Is M10 the right container for the interrupt matrix, or should the matrix be
   its own milestone with T-080 and T-081 split out?
2. Does the non-claiming T-081 belong inside M10 at all?
3. Is Batch 1 of the interrupt matrix (four interruption points) the correct first
   increment, or is the artifact-write point alone enough to prove that no partial
   artifact is presented as complete?
4. When existing contracts do not define behavior at an interruption point, should
   the case block the milestone close, or be recorded as `undetermined` and routed
   to the ledger as `unverified`? T-078 currently specifies the latter.
5. T-080 asserts a source-code observation about `EvidenceBundle._calculate_hash()`
   field coverage. It has not been executed. Does it belong in M10, or in a
   narrower correctness task?

## 5. What is explicitly out of scope for this review

- Do not review or propose implementation code for any M10 task.
- Do not reopen the frozen M9 specifications (T-070 through T-076).
- Do not propose adding an agent, a topology change, or a recovery capability.
- Do not ask for severity thresholds, performance targets, or live-provider runs;
  those require a separately authorized gate.

## 6. Verifying the documentation-only claim

```powershell
git fetch origin
git diff --stat origin/main...origin/docs/m10-runtime-assurance-spec
git diff --name-only origin/main...origin/docs/m10-runtime-assurance-spec
```

Every path should be under `docs/` plus `REVIEW-REQUEST.md`. If any path under
`src/`, `tests/`, `benchmarks/`, `scripts/`, `prompts/`, or `evaluation/` appears,
the claim is false and that is a blocking finding.
