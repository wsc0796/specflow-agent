# M10 specification freeze report

**Status:** DRAFT FOR FREEZE — REVISION 4, awaiting independent re-review.
**Date:** 2026-09-11
**Branch:** `docs/m10-runtime-assurance-spec`
**START_HEAD:** `9adcddb46f2977ea122966c1167e48fe2592d8be`
**REVIEWED_HEAD:** `9adcddb46f2977ea122966c1167e48fe2592d8be`
**PR_BASE:** `1b44127747a7f7b8bfd9118eb56006d867986b39` (`main`)
**Predecessor milestone:** M9 — Runtime Resilience & Efficiency, specification frozen in `02c1d3f` on branch `docs/m9-runtime-resilience-specs` (published to the remote at revision 3) and merged into this branch

The revision starts at the actual PR head, equal to the reviewed reference.
M9 declaration-source version is `02c1d3fe9bcd8c95d6bb7cf3959328844598e473`;
other declarations retain their path/clause/source-commit bindings. Source-code
observations below were read at START_HEAD. Future M10 execution evidence must
separately name its actual tested-code commit and effective configuration after
the implementation dependencies are met. START_HEAD identifies this revision's
starting point, not a universal source or runtime-verification version.

## 1. Files modified in revision 4

| File | Purpose | Revision 4 + / - lines |
| --- | --- | --- |
| `docs/tasks/M10-runtime-assurance-verification.md` | Milestone specification: REQ-M10-1 through REQ-M10-13, boundaries, milestone acceptance, Appendix A, resolved open questions | +88 / -33 |
| `docs/tasks/T-077-guarantee-boundary-ledger.md` | Full task specification for T-077 | +17 / -9 |
| `docs/tasks/T-078-deterministic-failpoints.md` | Full task specification for T-078, with source observations, actual-hit evidence requirements, and scoped marker assertions | +87 / -35 |
| `docs/tasks/T-080-evidence-and-artifact-integrity-audit.md` | Full task specification for T-080 | +70 / -45 |
| `docs/tasks/T-079-run-local-and-project-assurance-reporting.md` | Full task specification for T-079 | +35 / -23 |
| `docs/reports/M10-specification-freeze-report.md` | This report | +145 / -50 |
| `REVIEW-REQUEST.md` | Review instructions, finding dispositions, applied decisions, and remaining gates | +83 / -51 |

This branch additionally carries the M9 specification set (nine files under
`docs/`) via a merge of `docs/m9-runtime-resilience-specs`, so the clauses M10
cites are readable without leaving the pull request.
Those nine files are cumulative PR changes, not files modified in this round.

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
  correctness, and closure permission are reported separately. Unexecuted cases,
  missing/wrong actual injection, and incomplete observations fail the mechanism
  and decide neither support nor refutation. A valid counterexample remains
  `violated` / `refuted`. Audit discovery/reporting may complete, but a
  counterexample to required safety (REQ-M10-8 / AC-078-6) fails M10 assurance
  acceptance; a required unverified guarantee cannot pass either. Repairs need
  separate authorization.
- **AD-M10-5 — `undetermined` is decided before execution.** It is assigned from
  reading the contract, never after observing an unexpected result. A
  valid contradiction is always `violated`. An undefined agent-level contract
  does not waive a defined run-safety requirement; skipped or version-mismatched
  evidence never becomes `verified`.
- **AD-M10-6 — `_COMPLETE` is an integrity indicator, not a success indicator.**
  `_finalize_run_directory` runs on both the success path (`runner_multi.py:517`,
  followed by `return 0`) and the failed path (`runner_multi.py:945`, after
  writing partial agent outputs). These are source observations. Marker absence
  at point 4 is required only in an isolated, initially unfinished publication
  interrupted before the marker, with no later completed finalize. Assertions
  concern final files, not temporary files; an old target may survive a fault
  before replacement. Marker presence is neither business success nor a
  substitute for expected-file-set/hash/state checks; marker absence is not
  actual-hit proof. The marker does not automatically detect later file changes
  or deletion (REQ-078-4).
- **AD-M10-7 — Coverage follows the entry point.** A CLI case cannot verify the
  Run API lifecycle contract; `recover_interrupted_runs` is reached from the API
  startup path (`main.py:13`, `main.py:34`, implemented at `runs.py:267`).
- **AD-M10-8 — Citations must be readable from the pull request.** The cited M9
  clauses are present on this branch and published on
  `docs/m9-runtime-resilience-specs`. The original specifications are the
  traceable sources; Appendix A is a reading copy. No repeat publication is
  needed. Readability, M9 implementation completion, M10 freeze, and M10
  implementation permission remain separate; §3 defines the common gate.
- **AD-M10-9 — Excerpt allowance is an allowlist, not an interpretation.** Only
  this repository's own `docs/`, reports, README, and CHANGELOG may be excerpted,
  subject to a length bound and existing sanitization.
- **AD-M10-10 — No recovery, and no multi-process work.** M10 verifies what
  already happens. Resume, compensation, reconciliation, multi-process
  coordination, and process-level crash probing are out of scope; the
  single-process limitation is stated rather than approximated.
  T-080 is limited to contract audit, experiments, ledger, and report. Its
  `models.py`, `store.py`, and `runner_multi.py` objects are read-only; a recorded
  audit decision cannot authorize hash, artifact-format, or persistence changes.
  `tool_call_records` stays outside the current hash projection; equal
  projections are not SHA-256 collisions. Legacy "atomically" is tracked as a
  declaration with a static refutation candidate awaiting valid execution.
  Multi-agent file hashing covers only top-level non-symlink files, excluding
  `_COMPLETE` and `artifact-integrity.json`, with no recursive coverage.

## 3. Task dependencies

| Order | Task | Depends on | Gate evidence required |
| --- | --- | --- | --- |
| 1 | T-077 Guarantee Boundary Ledger and Declaration Registry | Independently approved M10 spec freeze; readable declaration sources; T-070 through T-075 implementation closed | Freeze decision and commit; source path/clause/commit; readable completion report and implementation commit for each dependency below |
| 2 | T-078 Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed | T-077 completion report path and commit hash |
| 3 | T-080 Evidence and Artifact Integrity Contract Audit | T-078 closed | T-078 completion report path and commit hash |
| 4 | T-079 Run-Local and Project-Level Assurance Reporting | T-078 and T-080 closed | Both completion report paths and commit hashes |
| 5 | Milestone assurance review | T-077, T-078, T-080, T-079 closed | The four completion reports plus the final ledger state |

The required M9 dependencies are identical to REQ-M10-12 and T-077 Status:

| Required implementation | Declaration/dependency basis | Completion evidence at START_HEAD |
| --- | --- | --- |
| T-070 | REQ-M9-4 duplicate ownership; REQ-070-4/-5/-8; predecessor of T-071 | Not satisfied: readable completion report and implementation commit not available |
| T-071 | REQ-M9-4 open circuits; REQ-071-2/-5/-7; predecessor of T-072 | Not satisfied: readable completion report and implementation commit not available |
| T-072 | REQ-M9-4 saturation/no silent discard; REQ-072-3/-4/-6; predecessor of T-073 | Not satisfied: readable completion report and implementation commit not available |
| T-073 | REQ-M9-5 safe observability; REQ-073-5/-7; predecessor of T-074 | Not satisfied: readable completion report and implementation commit not available |
| T-074 | REQ-M9-4 invalid cache entries; REQ-074-3/-5/-7; predecessor of T-075 | Not satisfied: readable completion report and implementation commit not available |
| T-075 | REQ-075-9 failure mapping, directly cited by REQ-M10-1 | Not satisfied: readable completion report and implementation commit not available |

Only their specifications and the M9 specification-freeze report are present;
the required task completion reports and implementation commits are not
available on this PR baseline. No missing report path or SHA is fabricated.
Readability is satisfied; implementation completion is not satisfied; revision 4
independent freeze approval is pending; M10 implementation is therefore blocked.
Unknown or missing dependency evidence must remain explicitly blocked. T-076
Java/Maven is unrelated to this verification scope and is not a gate.

The order remains T-077 → T-078 → T-080 → T-079 → milestone assurance review.
T-080 moved before T-079 in revision 2 and T-081 remains excluded. The current
docs-only revision and review submission may proceed despite the missing future
implementation prerequisites; no T-077 or M9 implementation starts here.

## 4. Unresolved risks

- **R-M10-1 — Required M9 implementation evidence is not satisfied.** The
  sources are readable, but each of T-070 through T-075 still needs a readable
  completion report and implementation commit under §3 / REQ-M10-12. T-077
  also requires independently approved M10 freeze. Neither readable source
  files nor this report meets the implementation gate; T-076 is not required.
  Revision 4 corrects the gate text and may be submitted for review now. It does
  not implement automatic enforcement or authorize an implementation start.
- **R-M10-2 — Baseline observations were read, not executed.** T-078 and T-080
  depend on source-code observations about `_calculate_hash`,
  `_finalize_run_directory`, and `ArtifactStore.write_run`. Both tasks require
  each observation to be confirmed by an executed test or explicitly withdrawn
  (T-078 AC-078-4/-5, T-080 REQ-080-3 / AC-080-3). Legacy success-path file
  count is ten at `artifacts/store.py:43-58`; the case table has seven rows.
  Those counts were checked statically here, not by a new runtime experiment.
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
  define them. Recording those gaps is acceptable audit delivery, not proof of
  required guarantees or permission to mark M10 assurance acceptance passed.
- **R-M10-6 — Interruption points may not be distinguishable in persisted
  artifacts (author finding A3).** The failed path writes the same
  `manifest.json` / `traces.json` / `agent-outputs.json` set and calls
  `_finalize_run_directory` regardless of which point was interrupted, so
  post-hoc artifact inspection is insufficient to identify the injection point.
  Revision 4 requires test-side actual-hit ID/count/fault/entry evidence,
  generated when the real execution reaches injection, and comparison with the
  preset (REQ-078-12). No hit, wrong point, or wrong count fails the mechanism
  and cannot support or refute the claim. No production manifest/log/business
  field is added. The specification gap is corrected; the mechanism and its
  acceptance tests remain future work, not verified capability.
- **R-M10-7 — This branch now carries two specifications.** Merging the M9 set
  into the M10 branch means this pull request shows the M9 and M10 documents
  together. The M9 documents are frozen and are not open for review here; the
  merge exists solely to make M10's cited clauses readable. A reviewer who treats
  the M9 files as proposed changes would be reviewing the wrong artifact.

## 5. Validation evidence for this branch

Revision 4 local checks are run in an isolated checkout at START_HEAD plus only
the seven document edits. Python 3.12 and the existing `uv.lock` are used with
`UV_FROZEN=true`; no dependency update or live-provider run is requested.

| Command / scope | Actual result | Exit code |
| --- | --- | --- |
| Baseline `uv run pytest -v` at START_HEAD before edits | 771 passed, 3 skipped, 3 warnings in 27.57s | 0 |
| Revision 4 `uv run pytest -v` | 771 passed, 3 skipped, 3 warnings in 10.86s | 0 |
| Revision 4 `uv run ruff check .` | All checks passed; existing invalid `# noqa` warning at `tests/test_coordinator.py:113` | 0 |
| Revision 4 `uv run ruff format --check .` | 208 files already formatted | 0 |
| Revision 4 `git diff --check` | No whitespace errors; repeated after this report's final edit | 0 |
| Revision 4 scope/reference static check | Exactly seven existing allowlisted files; no additions/deletions/renames or untracked files; REQ/AC IDs resolve; seven case rows and ten legacy writes | 0 |

The three pytest skips concern Windows symlink privileges
(`test_repository_tools.py:238`, `test_runs.py:204`, `test_scanner.py:148`). The
three warnings are collection warnings for `TestStrategyAgent` and
`TestStrategyOutput`, plus the Starlette/httpx deprecation warning. Baseline and
revision 4 runs report the same skip/warning categories. None was hidden or
changed to obtain a passing gate.

Final diff: START_HEAD to revision 4 is **7 files, 525 insertions,
246 deletions**; PR_BASE to revision 4 is **16 files, 2505 insertions,
0 deletions**. File-level changes are listed in §1. The deleted lines are scoped
text replacements; no file is deleted. All seven changed paths are allowlisted;
the nine M9 files and all runtime, test, dependency, CI, benchmark, script,
prompt, and evaluation paths are unchanged in this round. No pre-existing user
work was included. The isolated original repository's untracked report remains
outside this checkout and commit.

Raw local command logs (`baseline-pytest.log`, `pytest.log`, `ruff-check.log`,
`ruff-format.log`, `diff-check.log`, and `scope-check.log`) and command exit codes
are retained outside the checkout in `C:/Users/50469/temp/specflow-pr6-m10-20260911`.

The cumulative baseline PR contains 16 files / 2226 insertions / 0 deletions:
seven M10/review documents plus nine previously merged M9 documents. The nine
M9 files are not modified in this round. Earlier revision results are historical
provenance only and are not reused as revision 4 execution evidence.

These existing quality checks do not verify the future M10 failpoints, audits,
or assurance reporting. Remote CI for the resulting commit is checked after
push and reported in the PR; no pre-commit remote result is asserted here.

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
| 3 | `5df7462`, `ab14b9a`, `9adcddb` | Made M9 sources readable: the branch was published, the M9 specifications merged, and REQ-M10-6 / row-1 citation evidence revised. The separate implementation gate still required the revision 4 correction |
| 4 | One focused revision commit after START_HEAD; exact SHA in the PR body and disposition comment | Align implementation gates and source/code/revision bindings; distinguish audit delivery from assurance acceptance; require actual test-side hits; scope marker assertions; separate reporting dimensions; close audit runtime-change permissions; apply resolved decisions and factual corrections |

Revision 3 comprised merge `5df7462`, text revision `ab14b9a`, and provenance
update `9adcddb` (this round's START_HEAD). Revision 4 makes Appendix A a reading
copy and separately requires implementation completion; it does not rewrite a
historical review verdict. The new revision commit's own SHA is
recorded after commit in the PR, without an extra provenance-only commit.
