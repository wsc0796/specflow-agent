# M10 specification freeze report

**Status:** DRAFT FOR FREEZE — REVISION 3, awaiting re-review.
**Branch:** `docs/m10-runtime-assurance-spec`
**Base:** `1b44127` (`origin/main`, `security: harden repository and prompt trust boundaries`)
**Predecessor milestone:** M9 — Runtime Resilience & Efficiency, specification frozen in `02c1d3f` on branch `docs/m9-runtime-resilience-specs` (published to the remote at revision 3) and merged into this branch

## 1. Files added

| File | Purpose |
| --- | --- |
| `docs/tasks/M10-runtime-assurance-verification.md` | Milestone specification: REQ-M10-1 through REQ-M10-13, boundaries, milestone acceptance, Appendix A, resolved open questions |
| `docs/tasks/T-077-guarantee-boundary-ledger.md` | Full task specification for T-077 |
| `docs/tasks/T-078-deterministic-failpoints.md` | Full task specification for T-078, including the verified baseline facts it must respect |
| `docs/tasks/T-080-evidence-and-artifact-integrity-audit.md` | Full task specification for T-080 |
| `docs/tasks/T-079-run-local-and-project-assurance-reporting.md` | Full task specification for T-079 |
| `docs/reports/M10-specification-freeze-report.md` | This report |
| `REVIEW-REQUEST.md` | Review instructions, the full finding disposition table, and the open decisions |

This branch additionally carries the M9 specification set (nine files under
`docs/`) via a merge of `docs/m9-runtime-resilience-specs`, so the clauses M10
cites are readable without leaving the pull request.

## 2. Architecture decisions

- **AD-M10-1 — M10 is the complement of M9, not an extension.** M9 governs
  admission and execution-time control. M10 governs ex-post acceptance and
  guarantee verification. No M9 behavior is modified.
- **AD-M10-2 — Verification has four conditions, not one.** Applying
  REQ-M10-2: the source must exist and be the one being verified; evidence must
  actually have been produced; it must match the code version and configuration;
  and its assertions must map to the declaration clause. "A test with this name
  exists" satisfies none of the four by itself.
- **AD-M10-3 — Four ledger states, and `refuted` is preserved.** `verified`,
  `declared`, `refuted`, `not_applicable`. A contradiction may not be relabelled,
  merged, or absorbed into a generic issue bucket.
- **AD-M10-4 — Three verdicts, never one.** Mechanism correctness, claim
  correctness, and closure permission are reported separately. A mechanism that
  correctly reports a contradiction is a working mechanism and a failed
  declaration — not an assurance pass.
- **AD-M10-5 — `undetermined` is decided before execution.** It is assigned from
  reading the contract, never after observing an unexpected result. A
  contradiction is always `violated`.
- **AD-M10-6 — `_COMPLETE` is an integrity indicator, not a success indicator.**
  `_finalize_run_directory` runs on both the success path (`runner_multi.py:517`,
  followed by `return 0`) and the failed path (`runner_multi.py:945`, after
  writing partial agent outputs). The interruption assertion is therefore about
  the marker's **absence** before it is written.
- **AD-M10-7 — Coverage follows the entry point.** A CLI case cannot verify the
  Run API lifecycle contract; `recover_interrupted_runs` is reached from the API
  startup path (`main.py:13`, `main.py:34`, implemented at `runs.py:267`).
- **AD-M10-8 — Citations must be readable from the pull request.** The cited M9
  clauses are present on this branch and published on
  `docs/m9-runtime-resilience-specs`. Appendix A remains the within-document copy
  of record so the dependency can be read and diffed without leaving the review
  surface.
- **AD-M10-9 — Excerpt allowance is an allowlist, not an interpretation.** Only
  this repository's own `docs/`, reports, README, and CHANGELOG may be excerpted,
  subject to a length bound and existing sanitization.
- **AD-M10-10 — No recovery, and no multi-process work.** M10 verifies what
  already happens. Resume, compensation, reconciliation, multi-process
  coordination, and process-level crash probing are out of scope; the
  single-process limitation is stated rather than approximated.

## 3. Task dependencies

| Order | Task | Depends on | Gate evidence required |
| --- | --- | --- | --- |
| 1 | T-077 Guarantee Boundary Ledger and Declaration Registry | M10 spec freeze; M9 clause sources readable per REQ-M10-6 | Freeze commit hash; `docs/tasks/M9-runtime-resilience-efficiency.md` present on this branch |
| 2 | T-078 Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed | T-077 completion report path and commit hash |
| 3 | T-080 Evidence and Artifact Integrity Contract Audit | T-078 closed | T-078 completion report path and commit hash |
| 4 | T-079 Run-Local and Project-Level Assurance Reporting | T-078 and T-080 closed | Both completion report paths and commit hashes |
| 5 | Milestone assurance review | T-077, T-078, T-080, T-079 closed | The four completion reports plus the final ledger state |

Ordering change from revision 1: T-080 moved before T-079, because the audit
constrains what T-079 may report. T-081 was removed. Revision 3 changed no
ordering; it made the row-1 gate evidence concrete and readable.

## 4. Unresolved risks

- **R-M10-1 — M9 is published but not implemented.** T-070 through T-076 are
  frozen specifications; none is implemented. M10 must not begin before the tasks
  whose clauses it verifies are closed, and nothing in M10 detects a premature
  start automatically. The citation-readability half of this risk was closed at
  revision 3.
- **R-M10-2 — Baseline observations were read, not executed.** T-078 and T-080
  depend on source-code observations about `_calculate_hash`,
  `_finalize_run_directory`, and `ArtifactStore.write_run`. Both tasks require
  each observation to be confirmed by an executed test or explicitly withdrawn
  (REQ-078-4, REQ-080-3, AC-080-3).
- **R-M10-3 — `undetermined` may still dominate.** If existing contracts do not
  define behavior at most Batch 1 interruption points, T-078 will return mostly
  `undetermined`. That is the intended honest outcome, but it may produce a
  milestone that proves little. The milestone assurance review exists to make that
  visible.
- **R-M10-4 — Ledger maintenance burden.** T-077 requires declaration source
  references that resolve mechanically. Renaming a section or moving a report can
  rot a reference into `declared` without any change in real evidence. The ledger
  design must make that failure mode visible rather than silent.
- **R-M10-5 — Batch 1 may mostly restate known limits.** Four interruption points
  may produce four `undetermined` results if the contracts genuinely do not
  define them. That outcome is acceptable and must not be engineered away.
- **R-M10-6 — Interruption points may not be distinguishable in persisted
  artifacts (author finding A3).** The failed path writes the same
  `manifest.json` / `traces.json` / `agent-outputs.json` set and calls
  `_finalize_run_directory` regardless of which point was interrupted, so
  post-hoc artifact inspection is weak evidence for identifying the interruption
  point. Discrimination may rest on the pre-declared expectation plus the absence
  of `_COMPLETE`. Adding an interruption-point identifier would be a product
  change outside M10. Recorded rather than solved; a reviewer verdict is
  requested in `REVIEW-REQUEST.md` §4.6.
- **R-M10-7 — This branch now carries two specifications.** Merging the M9 set
  into the M10 branch means this pull request shows the M9 and M10 documents
  together. The M9 documents are frozen and are not open for review here; the
  merge exists solely to make M10's cited clauses readable. A reviewer who treats
  the M9 files as proposed changes would be reviewing the wrong artifact.

## 5. Validation evidence for this branch

Required checks, all of which pass at revision 3:

```powershell
git diff --name-only origin/main...docs/m10-runtime-assurance-spec   # docs/ plus REVIEW-REQUEST.md only
git log --oneline origin/main..docs/m10-runtime-assurance-spec        # 4 commits plus the merge, none touching src/ or tests/
git show --stat 5df7462                                              # M9 merge: 9 files, all under docs/
```

No runtime implementation, test, benchmark fixture, dependency, or generated
artifact is present.

## 6. No-runtime-implementation confirmation

This branch contains documentation only. No file under `src/`, `tests/`,
`benchmarks/`, `scripts/`, `prompts/`, or `evaluation/` is added or modified, and
no dependency manifest is changed. The M9 merge commit `5df7462` adds nine
documents under `docs/` and nothing else.

## 7. Revision history

| Revision | Commit | Change |
| --- | --- | --- |
| 1 | `0ee6046` | Initial draft: milestone plus T-077 and T-078 full specs, boundary-only T-079 through T-081 |
| 2 | `010b024` | Addresses the PR #6 review: four-condition verification semantics, four ledger states with `refuted` preserved, three separate verdicts, pre-execution `undetermined`, evidence-backed dependency gates, Appendix A citation reproduction, excerpt allowlist, boundary-separated read-only rule, normalized determinism, corrected `_COMPLETE` semantics, entry-point coverage table, closed fault set, failpoint registration isolation, T-079 dimension separation, T-080 narrowing and reordering, T-081 removal |
| 3 | `5df7462` plus this report's commit | Completes the B1 fix: `docs/m9-runtime-resilience-specs` published to the remote, the M9 specifications merged into this branch, REQ-M10-6 rewritten to require a reviewer-readable citation, Appendix A re-labelled as the within-document copy of record, and row-1 gate evidence made concrete |

Revision provenance is by blob: revision 1's report blob is
`14925fd8440d3b9bdff60ebf943f3feb448c2919`. A reader can confirm which revision
they hold with `git hash-object docs/reports/M10-specification-freeze-report.md`.
