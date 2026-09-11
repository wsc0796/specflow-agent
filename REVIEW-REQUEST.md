# Review record — M10 Runtime Assurance Verification (specification frozen, revision 4)

**Revision 4 specification freeze is registered.** The user-transferred ChatGPT
AI-assisted static re-review passed the fixed REVIEWED_HEAD below and recommended
freeze approval; the user authorized this registration. R1/R2/R3, C1, and
S1/S2/S3 are closed as specification findings on that basis. The executor records
the decision and does not claim a new independent review. See the
[freeze report §8](docs/reports/M10-specification-freeze-report.md#8-revision-4-freeze-registration)
for the quoted source, freeze scope, and current quality checks.

T-077/T-078 specifications are frozen. T-079/T-080 scope, entry points, and
judgement criteria are frozen; field-level refinement and their own freeze after
predecessor closure remain required by AC-M10-1 / REQ-M10-12. M10 implementation
remains blocked; neither M9/M10 implementation completion nor M10 assurance
acceptance is declared. This is not GitHub APPROVE, a merge, or renewed approval
of the M9 documents carried by this PR. Historical review records remain below.

**This branch contains documentation only.** It adds no runtime implementation,
no test, no benchmark fixture, no dependency, and no generated artifact. Verify
with §6.

**Branch:** `docs/m10-runtime-assurance-spec`
**START_HEAD / REVIEWED_HEAD:** `826d3a7257ad903bc09b0d2d6635a3449576a3ce`
**PR_BASE:** `1b44127747a7f7b8bfd9118eb56006d867986b39` (`main`)
**Historical revision 4 preparation START_HEAD:** `9adcddb46f2977ea122966c1167e48fe2592d8be`.
In the historical §2 disposition table, START_HEAD and the pending statuses refer
to that preparation and its submission, before the current freeze registration.
**Declaration-source version:** M9 `02c1d3fe9bcd8c95d6bb7cf3959328844598e473`;
other declarations retain their own path/clause/source-commit bindings.
**Tested-code version:** future M10 evidence must identify its actual code commit
and effective configuration; neither START_HEAD nor a declaration-source commit
substitutes for that binding. This round's existing quality checks are reported
in the freeze report, not as M10 runtime verification.

---

## 1. What changed in revision 2 (historical summary)

| Area | Revision 1 | Revision 2 |
| --- | --- | --- |
| Verification semantics | "Reference resolves" was treated as sufficient for `verified` | REQ-M10-2 defines four separate conditions, each checkable; no substitute exists for any of them |
| Ledger states | `verified` / `unverified` / `not_applicable` | `verified` / `declared` / `refuted` / `not_applicable`, with `refuted` preserved through every rollup |
| Verdicts | Tool success and claim success were one thing | REQ-M10-4 separates mechanism verdict, claim verdict, and closure verdict |
| `undetermined` | Assignable after observing an unexpected result | REQ-M10-9: decided **before** execution from contract text; a contradiction is always `violated`, never `undetermined` |
| Dependency gates | T-077's own status line said "freeze + new session" only | REQ-M10-12 requires gate evidence (completion report path + commit hash) and T-077 repeats it in its own status line |
| Citation traceability | Cited M9 clauses by commit ID that reviewers cannot read | REQ-M10-6 plus Appendix A reproduce the cited clauses verbatim in the milestone document |
| Excerpt allowance | REQ-077-1 required excerpts while AC-077-4 forbade content — an unresolved literal conflict | REQ-077-3 defines an explicit allowlist, a length bound, and a sanitization rule |
| Read-only rule | Stated as "no write permission" | REQ-077-7 separates target repository, validation computation, and ledger output directory |
| Determinism | "Byte-identical ledger artifact" conflicted with the wall-clock completion marker | REQ-077-8 defines determinism over normalized ledger content |
| `_COMPLETE` semantics | Implicitly treated as a partial-artifact discriminator | Revision 2 recognized from source that both paths finalize; revision 4 further scopes the absence assertion and separates marker publication from current integrity |
| Entry points | CLI-only, with implicit coverage of the lifecycle contract | REQ-078-5 binds each declaration to an entry point that can actually observe it; the API lifecycle is explicitly not covered by CLI cases |
| Failpoint lifecycle | Not specified | REQ-078-9 requires scoped registration, release on every exit path including `SystemExit` / `KeyboardInterrupt`, and isolation under concurrent tests |
| Fault type | Not fixed | REQ-078-3 closes the injected-fault set and forbids treating `Exception`, `SystemExit`, and `KeyboardInterrupt` as interchangeable |
| T-079 | One combined health conclusion | Two dimensions reported separately; business outcomes are not unresolved items by default |
| T-080 | Broad integrity-plus-freshness claim, chained after T-079 | Narrowed to a contract audit of three separate objects, moved **before** T-079, freshness removed |
| T-081 | Multi-process probe inside M10 | Removed from M10's required scope; process kill and signals explicitly unassigned |
| AC-M10-1 | Demanded full specs for all five tasks while the earlier specification permitted placeholders | Current AC-M10-1 names all four tasks and defers T-079/T-080 field-level detail to their own freeze under REQ-M10-12 |

## 2. Disposition of every review finding

### Historical revision 4 executor dispositions at submission

| Item | Decision this round | Changed files / sections | Self-check basis | Current status |
| --- | --- | --- | --- | --- |
| R1 | Require approved M10 freeze, readable sources, and completion report plus implementation commit for each of T-070..T-075; exclude T-076; separate source/code/revision versions | M10 REQ-M10-1/-2/-12, Boundaries, AC-M10-8; T-077 Status, REQ-077-1/-4; freeze report §3, R-M10-1 | M9 REQ-M9-4/-5/-6, T-070..T-075 source clauses and sequential dependencies; no corresponding completion reports at START_HEAD | Specification corrected; dependency gate not satisfied; future implementation blocked |
| R2 | Invalid injection/execution cannot support or refute a claim; valid counterexamples remain `violated`/`refuted`; audit delivery does not waive required safety acceptance | M10 REQ-M10-4/-5/-8/-9, AC-M10-3/-4; T-078 REQ-078-6/-7, AC-078-6/-7; freeze report AD-M10-4/-5 | Side-by-side check of mechanism, claim, and closure rules against the unchanged run-safety obligations | Specification corrected; mechanism/claim/assurance behavior awaits future experiments and independent review |
| R3 | Require actual test-side hit ID/count/fault/entry evidence and post-injection observables; no prefilled actual hits or production fields | T-078 REQ-078-1/-6/-12, AC-078-3/-7/-12; M10 AC-M10-5; freeze report R-M10-6; A3 below | Seven-row case table and actual-hit record are checked against the preset; no-hit/wrong-location/wrong-count fails the mechanism | Specification corrected; future test mechanism not implemented or verified |
| C1 | Scope missing `_COMPLETE` to an isolated initially unfinished publication with no later finalize; distinguish final targets, old targets, temporary files, and runtime state | T-078 baseline observations, REQ-078-4, AC-078-4/-5; T-080 baseline observations; freeze report AD-M10-6 | `runner_multi.py:815-876`, `:924-945` at START_HEAD: replacement, marker publication, and failed-path finalize | Specification corrected; source observations only; future fault cases still required |
| S1 | Move T-078 project gaps out of Dimension A; require an actual run and explicit unmet delivery/use obligation for run-local items; keep dimensions separate | T-079 Goal, Dimensions A/B, REQ-079-1/-2, decisions, Boundaries, AC-079-1/-2 | No project `declared`/`refuted`/`undetermined` automatically changes run health; optional opinions, business REJECT and permitted degradation do not qualify by default | Specification corrected; future reporting tests required |
| S2 | T-080 audits only; decisions grant no permission to change hashing, artifact formats, or persistence; three production files are read-only | T-080 Goal, REQ-080-4/-6/-7, Boundaries, AC-080-4/-5; freeze report AD-M10-10 | Every former conditional runtime-change permission replaced by separate authorization outside this audit | Specification corrected; future audit diff and experiments must enforce it |
| S3 | Apply resolved decisions; retain original M9 sources plus reading copy; preserve current hash projection; track legacy atomicity; state top-level exclusions; correct ten files, seven rows, revisions and cross-references | §1/§2/§3/§4 here; T-078/T-080 observations and decisions; M10 traceability; freeze report history/risks | `evidence/models.py:181-190`, `artifacts/store.py:36-87`, `runner_multi.py:855-869`; table row count and named REQ/AC targets | Specification corrected; static atomicity refutation candidate awaits valid execution; independent re-review pending |

These are executor self-check dispositions, not independent approval. B2/B4,
entry-point separation, the four ledger states, fault-type distinctions, and
registration cleanup/isolation are retained. No new task or runtime capability
is introduced; T-081 remains outside M10's required scope.

### Blocking findings

| ID | Finding | Disposition | Where |
| --- | --- | --- | --- |
| B1 | M9 sources not traceable on the remote; T-077's gate inconsistent with the order table | **Source visibility resolved in revision 3; implementation gate corrected in revision 4 (R1).** Original M9 sources are already published and merged; Appendix A is a reading copy. T-077 also requires approved M10 freeze and a readable completion report plus implementation commit for each of T-070..T-075. Those implementation dependencies remain not satisfied. | REQ-M10-6/-12, T-077 Status, Appendix A, freeze report §3/R-M10-1 |
| B2 | "Reference resolves" is insufficient for `verified` | **Accepted.** REQ-M10-2 lists four conditions; REQ-077-4 gives a row-by-row table where a resolvable-but-unexecuted reference, a version mismatch, and a skipped test each yield `declared`. AC-077-2 tests each row. `refuted` was added as a distinct state. | REQ-M10-2, REQ-M10-3, REQ-077-4, AC-077-2 |
| B3 | "May close unverified" conflicts with "every interruption must be proven safe" | **Completed at the specification level by R2.** Audit delivery may record counterexamples; an invalid mechanism cannot decide a claim, and a valid counterexample to required safety fails M10 assurance acceptance. Run-safety requirements remain in force. | REQ-M10-4/-5/-8, REQ-078-6/-7, AC-078-6/-7 |
| B4 | Source excerpt requirement conflicts literally with the content prohibition | **Accepted.** REQ-077-3 defines an explicit allowlist (this repository's own `docs/`, reports, README, CHANGELOG), a configured length bound, and mandatory sanitization; excerpts from analyzed target repositories, `EvidenceBundle` content, tool output, prompts, and provider responses are forbidden. AC-077-4 tests both directions. | REQ-077-3, AC-077-4 |
| B5 | CLI path cannot cover Run API lifecycle recovery; interruption cases lack fault semantics and observables | **Entry-point separation retained.** REQ-078-5 remains normative and the report must name uncovered declarations. The case table has seven rows, the fault set remains closed, and R3/C1 require actual-hit evidence and correctly scoped marker assertions. Baseline findings are source observations, not executed fault results. | REQ-078-1/-3/-4/-5/-12, AC-078-3/-5/-8 |

### Non-blocking findings

| ID | Finding | Disposition | Where |
| --- | --- | --- | --- |
| 1 | T-080 should shrink to a narrow evidence-contract audit | **Accepted.** T-080 is now a contract audit of three separate objects, freshness removed, and it moved **before** T-079 because it constrains what T-079 may report. | `T-080-evidence-and-artifact-integrity-audit.md`, REQ-M10-12 |
| 2 | T-079 must not merge run-local unresolved items with project-level unverified declarations | **Accepted.** Two dimensions reported separately; business `REJECT` and permitted degradation are not unresolved items by default (REQ-079-1). | `T-079-run-local-and-project-assurance-reporting.md`, REQ-079-1, REQ-079-2 |
| 3 | T-081 should leave M10's required scope; T-078's reference to it was inconsistent | **Accepted.** T-081 is removed. Process kill, signals, and real crashes are explicitly unassigned to any M10 task. | M10 Boundaries, REQ-M10-11, T-078 Boundaries |
| 4a | Historical full-spec versus placeholder inconsistency | **Accepted.** AC-M10-1 names specified tasks and the field-level freeze gate; the current order reference is REQ-M10-12, not the unrelated REQ-M10-10. | AC-M10-1, REQ-M10-12 |
| 4b | T-077 read-only requirement vs artifact write | **Accepted.** REQ-077-7 separates the three boundaries in a table. | REQ-077-7, AC-077-6 |
| 4c | AC-077-3 byte-identical requirement conflicts with the completion marker's wall clock | **Accepted.** REQ-077-8 defines determinism over normalized ledger content. | REQ-077-8, AC-077-5 |
| 4d | Failpoint registration cleanup, scope, and parallel isolation | **Accepted.** REQ-078-9 requires release on every exit path including `SystemExit` and `KeyboardInterrupt`, plus isolation under concurrent execution, with tests. | REQ-078-9, AC-078-2 |

### Additional findings the author contributed while addressing the review

These were not in the review. Each is a source-code observation, not an executed
result.

| ID | Finding | Where it landed |
| --- | --- | --- |
| A1 | `ArtifactStore.write_run` declares "atomically" but its success path writes ten files with `path.write_text` and uses `except Exception` cleanup. The declaration is tracked; this static observation is a refutation candidate pending an executed audit case. It is neither repaired nor weakened here. | T-080 baseline observations, decision 2, REQ-080-4, AC-080-4 |
| A2 | The legacy and multi-agent pipelines do not provide the same artifact integrity guarantee, so a single "artifact integrity" ledger declaration would be wrong. T-077 requires two separate declarations. | REQ-077-11 |
| A3 | Different interruptions may produce similar persisted artifacts. Revision 4 requires actual test-side hit ID/count/fault/entry evidence generated when the execution reaches the injection point. Neither expected hits nor missing `_COMPLETE` proves injection. No production manifest/log/business-state fields are added; the future test mechanism must reject missing or mismatched hits. | T-078 REQ-078-6/-12, AC-078-3; freeze report R-M10-6 |

## 3. Historical revision 4 re-review checklist

The following checklist was submitted for revision 4 re-review, with findings
requested as `blocking` / `should-fix` / `observation`, each with a file and
section. Its specification review is now settled by the quoted review in the
freeze report §8; future runtime validation remains required.

1. **Is REQ-M10-2 airtight?** Given the four conditions, name a route by which a
   declaration could still reach `verified` without evidence that actually
   supports it.
2. **Can `refuted` disappear?** Identify any rollup, count, or summary described
   in T-077 or T-079 through which a `refuted` declaration could lose its state.
3. **Is the entry-point table in REQ-078-5 correct?** Name a declaration in the
   Batch 1 set that no listed entry point can actually observe.
4. **Are injection and marker evidence separate?** Check actual-hit ID/count/
   fault/entry validation and mechanism-failure rules. Check REQ-078-4's initial
   state and no-later-finalize preconditions, old targets, final versus temporary
   files, and separate file-set/hash/runtime-state assertions.
5. **Is the excerpt allowlist in REQ-077-3 sufficient?** Name any content class
   that could still enter through the allowed sources.
6. **Are the gates identical?** Compare REQ-M10-12, T-077 Status, and freeze
   report §3/R-M10-1: approved M10 freeze, readable sources, and completion
   report plus implementation commit for each T-070..T-075; T-076 is excluded.
7. **Is T-080's narrowing complete?** Does any clause still permit changing a
   runtime hash/format/persistence contract after merely recording a decision?
8. **Is T-079's separation enforceable?** Name a realistic case where a run-local
   item and a project-level declaration would be reported in a way that still
   misleads.
9. **Can audit completion still masquerade as assurance acceptance?** Check
   REQ-M10-4/-5/-8 and AC-078-6/-7, including invalid mechanisms and valid
   counterexamples. Check that source/code/revision versions are separate.

## 4. Decisions applied in revision 4

The owner supplied the following dispositions for this round. Review their
consistent application; they are no longer open implementation choices.

1. Use the readable original M9 specifications at `02c1d3f` as sources and
   Appendix A as a reading copy; do not publish the already readable branch again.
2. Keep `tool_call_records` outside `evidence_hash`; identical hashed projections
   have identical values, not a SHA-256 collision (T-080 decision 1).
3. Track legacy "atomically" as a declaration. The static finding is a refutation
   candidate; future valid execution decides the verdict (T-080 decision 2).
4. Describe actual top-level hash coverage and exclusions; claim no recursive
   coverage and add none (T-080 decision 3).
5. A pending human decision is run-local only when the existing contract requires
   it to complete or use that run's deliverable (T-079 decision 3).
6. Require test-side actual-hit evidence for A3. Add no production artifact,
   log, or business-state interruption field (T-078 REQ-078-12).

The remaining gates are concrete: T-070..T-075 implementation completion
evidence is not satisfied. Revision 4 specification freeze is now registered;
all newly specified failpoint/audit/reporting behavior awaits future authorized
implementation and validation under REQ-M10-12, including T-079/T-080's later
field-level freeze. None blocks this documentation-only registration.

## 5. Out of scope for this review

- Do not review or propose implementation code.
- Do not reopen the frozen M9 specifications (T-070 through T-076).
- Do not propose adding an agent, a topology change, or a recovery capability.
- Do not ask for severity thresholds, performance targets, or live-provider runs.
- Do not propose re-adding a multi-process probe to M10's required scope; the
  single-process limitation is stated instead.

## 6. Verifying the documentation-only claim

```powershell
git diff --stat 826d3a7257ad903bc09b0d2d6635a3449576a3ce HEAD
git diff --name-only 826d3a7257ad903bc09b0d2d6635a3449576a3ce HEAD
git diff --stat 1b44127747a7f7b8bfd9118eb56006d867986b39 HEAD
git diff --name-only 1b44127747a7f7b8bfd9118eb56006d867986b39 HEAD
```

The first pair is this freeze registration: the seven existing M10/review documents
listed in the freeze report §8. The second pair is the cumulative PR: those seven
plus nine previously merged M9 specification files. This round changes no M9
file. Every cumulative path is under `docs/` plus `REVIEW-REQUEST.md`. If any path under
`src/`, `tests/`, `benchmarks/`, `scripts/`, `prompts/`, or `evaluation/` appears,
the claim is false and that is a blocking finding.
