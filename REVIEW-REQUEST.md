# Review request — M10 Runtime Assurance Verification (specification draft, revision 2)

**Revision 3 addresses the review of revision 1 and completes the dependency-visibility fix.**
**Revision 2 addressed the review of revision 1.** The disposition of every
finding is in §2. A finding the author declined to accept is listed as such with
its reason; nothing was silently dropped.

**This branch contains documentation only.** It adds no runtime implementation,
no test, no benchmark fixture, no dependency, and no generated artifact. Verify
with §6.

**Branch:** `docs/m10-runtime-assurance-spec`
**Revision 2 base:** `0ee6046` (revision 1) on top of `1b44127` (`origin/main`)

---

## 1. What changed in revision 2

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
| `_COMPLETE` semantics | Implicitly treated as a partial-artifact discriminator | REQ-078-4 states the verified fact: both paths finalize, so `_COMPLETE` is an integrity indicator, not a success indicator; the assertion is now about its **absence** |
| Entry points | CLI-only, with implicit coverage of the lifecycle contract | REQ-078-5 binds each declaration to an entry point that can actually observe it; the API lifecycle is explicitly not covered by CLI cases |
| Failpoint lifecycle | Not specified | REQ-078-9 requires scoped registration, release on every exit path including `SystemExit` / `KeyboardInterrupt`, and isolation under concurrent tests |
| Fault type | Not fixed | REQ-078-3 closes the injected-fault set and forbids treating `Exception`, `SystemExit`, and `KeyboardInterrupt` as interchangeable |
| T-079 | One combined health conclusion | Two dimensions reported separately; business outcomes are not unresolved items by default |
| T-080 | Broad integrity-plus-freshness claim, chained after T-079 | Narrowed to a contract audit of three separate objects, moved **before** T-079, freshness removed |
| T-081 | Multi-process probe inside M10 | Removed from M10's required scope; process kill and signals explicitly unassigned |
| AC-M10-1 | Demanded full specs for all five tasks while REQ-M10-10 permitted placeholders | Consistent: full specs for T-077, T-078, T-080, T-079; field-level detail deferred to each task's own freeze |

## 2. Disposition of every review finding

### Blocking findings

| ID | Finding | Disposition | Where |
| --- | --- | --- | --- |
| B1 | M9 sources not traceable on the remote; T-077's gate inconsistent with the order table | **Accepted, with a scope judgment.** Gates now require readable gate evidence. Appendix A reproduces the cited M9 clauses verbatim so a reviewer without branch history can read them. **Resolved in full at revision 3.** The implied fix — make the M9 sources readable — was a repository-visibility decision, and the owner took it: branch `docs/m9-runtime-resilience-specs` is published (remote `02c1d3f`) and the M9 specifications are merged into this branch, so a reviewer can read the cited clauses from the pull request itself. Appendix A remains the within-document copy of record. R-M10-1 now records only that T-070 through T-076 remain unimplemented, not an unreadable citation. | REQ-M10-6, REQ-M10-12, Appendix A, freeze report R-M10-1 |
| B2 | "Reference resolves" is insufficient for `verified` | **Accepted.** REQ-M10-2 lists four conditions; REQ-077-4 gives a row-by-row table where a resolvable-but-unexecuted reference, a version mismatch, and a skipped test each yield `declared`. AC-077-2 tests each row. `refuted` was added as a distinct state. | REQ-M10-2, REQ-M10-3, REQ-077-4, AC-077-2 |
| B3 | "May close unverified" conflicts with "every interruption must be proven safe" | **Accepted.** REQ-M10-4 separates the three verdicts; REQ-M10-5 defines what closure with `refuted` requires; REQ-M10-8 narrows the run-level clause and states that agent-level completion status is what REQ-M10-9 classifies. | REQ-M10-4, REQ-M10-5, REQ-M10-8, REQ-078-6, REQ-078-7 |
| B4 | Source excerpt requirement conflicts literally with the content prohibition | **Accepted.** REQ-077-3 defines an explicit allowlist (this repository's own `docs/`, reports, README, CHANGELOG), a configured length bound, and mandatory sanitization; excerpts from analyzed target repositories, `EvidenceBundle` content, tool output, prompts, and provider responses are forbidden. AC-077-4 tests both directions. | REQ-077-3, AC-077-4 |
| B5 | CLI path cannot cover Run API lifecycle recovery; interruption cases lack fault semantics and observables | **Accepted, and extended with verified facts.** REQ-078-5 is a normative entry-point table; the completion report must state which declarations Batch 1 did not cover. REQ-078-1 requires six declared rows per case before execution. REQ-078-3 closes the fault set. REQ-078-4 records the verified `_COMPLETE` fact and changes the assertion. | REQ-078-1, REQ-078-3, REQ-078-4, REQ-078-5, AC-078-3, AC-078-5, AC-078-8 |

### Non-blocking findings

| ID | Finding | Disposition | Where |
| --- | --- | --- | --- |
| 1 | T-080 should shrink to a narrow evidence-contract audit | **Accepted.** T-080 is now a contract audit of three separate objects, freshness removed, and it moved **before** T-079 because it constrains what T-079 may report. | `T-080-evidence-and-artifact-integrity-audit.md`, REQ-M10-12 |
| 2 | T-079 must not merge run-local unresolved items with project-level unverified declarations | **Accepted.** Two dimensions reported separately; business `REJECT` and permitted degradation are not unresolved items by default (REQ-079-1). | `T-079-run-local-and-project-assurance-reporting.md`, REQ-079-1, REQ-079-2 |
| 3 | T-081 should leave M10's required scope; T-078's reference to it was inconsistent | **Accepted.** T-081 is removed. Process kill, signals, and real crashes are explicitly unassigned to any M10 task. | M10 Boundaries, REQ-M10-11, T-078 Boundaries |
| 4a | AC-M10-1 vs REQ-M10-10 inconsistency | **Accepted.** AC-M10-1 now names which tasks are fully specified and which defer field-level detail to their own freeze. | AC-M10-1 |
| 4b | T-077 read-only requirement vs artifact write | **Accepted.** REQ-077-7 separates the three boundaries in a table. | REQ-077-7, AC-077-6 |
| 4c | AC-077-3 byte-identical requirement conflicts with the completion marker's wall clock | **Accepted.** REQ-077-8 defines determinism over normalized ledger content. | REQ-077-8, AC-077-5 |
| 4d | Failpoint registration cleanup, scope, and parallel isolation | **Accepted.** REQ-078-9 requires release on every exit path including `SystemExit` and `KeyboardInterrupt`, plus isolation under concurrent execution, with tests. | REQ-078-9, AC-078-2 |

### Additional findings the author contributed while addressing the review

These were not in the review. Each is a source-code observation, not an executed
result.

| ID | Finding | Where it landed |
| --- | --- | --- |
| A1 | `ArtifactStore.write_run`'s docstring claims the run directory is written "atomically", but the implementation writes nine files with `path.write_text` and relies on an `except` block to remove the directory. Exception cleanup and process termination are different paths. This is a declared-versus-implemented question in its own right. | T-080 baseline facts, T-080 open decision 2, AC-080-4 |
| A2 | The legacy and multi-agent pipelines do not provide the same artifact integrity guarantee, so a single "artifact integrity" ledger declaration would be wrong. T-077 requires two separate declarations. | REQ-077-11 |
| A3 | Interruption points 1, 2, 3, and 4 may not be distinguishable in the persisted artifact set: the failed path writes the same `manifest.json` / `traces.json` / `agent-outputs.json` set and finalizes, so post-hoc artifact inspection is weak evidence for which point was interrupted. Discrimination may have to rest on the pre-declared expectation plus the absence of `_COMPLETE`, and adding an interruption-point identifier to the audit record would be a product change outside M10. Flagged rather than solved. | Freeze report R-M10-6, and this section |

## 3. What to check in revision 2

Please report findings as `blocking` / `should-fix` / `observation`, each with a
file and section. A finding without a location is not actionable.

1. **Is REQ-M10-2 airtight?** Given the four conditions, name a route by which a
   declaration could still reach `verified` without evidence that actually
   supports it.
2. **Can `refuted` disappear?** Identify any rollup, count, or summary described
   in T-077 or T-079 through which a `refuted` declaration could lose its state.
3. **Is the entry-point table in REQ-078-5 correct?** Name a declaration in the
   Batch 1 set that no listed entry point can actually observe.
4. **Is REQ-078-4's assertion correct?** Given `_safe_write` (`temp` + `fsync` +
   `os.replace`) and `_COMPLETE` written last, identify any way `_COMPLETE` could
   be observably present while the directory is incomplete, or absent while the
   directory is complete.
5. **Is the excerpt allowlist in REQ-077-3 sufficient?** Name any content class
   that could still enter through the allowed sources.
6. **Are the gates real?** Can any task start under REQ-M10-12 without the gate
   evidence it requires?
7. **Is T-080's narrowing complete?** Does anything remain in T-080 that asserts a
   guarantee beyond the audited mechanisms?
8. **Is T-079's separation enforceable?** Name a realistic case where a run-local
   item and a project-level declaration would be reported in a way that still
   misleads.
9. **Is Appendix A sufficient?** Does reproducing the M9 clauses remove the
   reviewability blocker, or is the missing branch still blocking?

## 4. Open decisions requested

A verdict on each is preferred over a range of options.

1. **Ownership decision, for the repository owner — not the spec:** should the M9
   specification branch (`docs/m9-runtime-resilience-specs`, commit `02c1d3f`) be
   pushed so that M9 dependencies are readable from the remote, instead of being
   reproduced in Appendix A?
2. Should the hashed evidence payload include `tool_call_records`, given that two
   runs with identical excerpts but different audited tool activity currently
   collide? (T-080 open decision 1)
3. Is the `ArtifactStore.write_run` "atomically" docstring a tracked declaration,
   and if so is its correct state `refuted`? (T-080 open decision 2)
4. Does the multi-agent integrity contract cover only top-level files, or does it
   intend to cover subdirectories? (T-080 open decision 3)
5. Is a pending human review decision always a run-local unresolved item, or only
   when it blocks the run's work from being usable? (T-079 open decision 3)
6. Should A3 be solved inside M10 by adding an interruption-point identifier, or
   recorded as a known evidence limitation? The author's position is: record it —
   adding the identifier is a product change.

## 5. Out of scope for this review

- Do not review or propose implementation code.
- Do not reopen the frozen M9 specifications (T-070 through T-076).
- Do not propose adding an agent, a topology change, or a recovery capability.
- Do not ask for severity thresholds, performance targets, or live-provider runs.
- Do not propose re-adding a multi-process probe to M10's required scope; the
  single-process limitation is stated instead.

## 6. Verifying the documentation-only claim

```powershell
git fetch origin
git diff --stat origin/main...origin/docs/m10-runtime-assurance-spec
git diff --name-only origin/main...origin/docs/m10-runtime-assurance-spec
```

Every path should be under `docs/` plus `REVIEW-REQUEST.md`. If any path under
`src/`, `tests/`, `benchmarks/`, `scripts/`, `prompts/`, or `evaluation/` appears,
the claim is false and that is a blocking finding.
