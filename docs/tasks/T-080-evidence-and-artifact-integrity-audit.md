# T-080 — Evidence and Artifact Integrity Contract Audit

**Status:** SCOPE, ENTRY POINTS, AND JUDGEMENT CRITERIA FROZEN — REVISION 4;
see the [freeze report §8](../reports/M10-specification-freeze-report.md#8-revision-4-freeze-registration).
Field-level detail remains deferred to this task's own refinement and freeze
after its predecessor closes, as required by AC-M10-1 / REQ-M10-12. Execution
requires T-078 closed with a readable completion report at a named commit, that
field-level specification freeze, and a new focused session. This registration
does not declare all details complete or authorize execution.

**Ordering note:** this task now precedes T-079. Revision 1 chained it after
T-079, which was unnecessary; the audit constrains what T-079 may report and
therefore belongs earlier.

## Goal

Determine, record, and test what the two existing integrity mechanisms actually
guarantee: what the evidence hash identifies, what the per-file artifact hashes
and completion marker identify, and whether the declared coverage of each matches
its implementation. The deliverables are contract audit, executed experiments,
ledger entries, and a report. This task does not change runtime contracts,
hashing, artifact formats, or persistence behavior.

## The three objects must not be conflated

Applying REQ-M10-2, this task keeps these separate and answers each on its own
terms. Revision 1 mixed them, which let a hash-coverage question read as a
freshness claim.

| Object | Question it answers | Source of truth |
| --- | --- | --- |
| `evidence_hash` | Which evidence **semantics** does this value identify? | `evidence/models.py` `EvidenceBundle._calculate_hash` and its contract |
| Artifact file hashes | Do covered files match the bytes hashed at finalize when explicitly rechecked? | `runner_multi.py` `_finalize_run_directory` / `artifact-integrity.json`; coverage below |
| Freshness | Did the target repository change between evidence collection, use, and persistence? | **Not covered by this task.** See the non-goals |

## Source-code baseline observations

Read at `START_HEAD=9adcddb46f2977ea122966c1167e48fe2592d8be` (the cited code
is unchanged from PR_BASE `1b44127`). These are source-code observations, not
executed fault experiments. Future evidence names its declaration-source commit
and actual tested-code commit/configuration separately.

| Fact | Location | Consequence |
| --- | --- | --- |
| `_calculate_hash` hashes sorted `matched_files`, `selected_files`, `searched_terms`, sorted `(relative_path, line_number, excerpt)` triples, and `truncated`, using canonical JSON and SHA-256 | `evidence/models.py:181-190` | All other bundle fields are outside that projection, including `source_hashes`, `tool_call_records`, `warnings`, `project_summary`, `technology_stack`, run identity, requirement, repository root, discovered-file count, and excerpt match counts |
| `EvidenceBundle` carries `source_hashes` and `tool_call_records` as its own audited fields | `evidence/models.py:141-179` | Identical hashed projections yield the same `evidence_hash` even if non-hashed fields differ; this is not a SHA-256 collision |
| `_finalize_run_directory` hashes top-level files satisfying `is_file()` and `not is_symlink()`, excluding `_COMPLETE` and `artifact-integrity.json` | `runner_multi.py:855-869` | No recursive subdirectory coverage, no hash of either excluded file, and no automatic expected-file-set validation; artifact hashes are separate from `evidence_hash` |
| `_finalize_run_directory` runs on both the success and the failed path | `runner_multi.py:517`, `:945` | The artifact-integrity declaration is about written-directory integrity, not business success |
| `ArtifactStore.write_run` writes ten files on success using `path.write_text`, removes the directory in `except Exception`, and has no integrity file or completion marker | `artifacts/store.py:24-87` (ten writes at `:43-58`) | The legacy mechanism differs from the multi-agent one; exception cleanup does not establish a process-termination guarantee |
| `ArtifactStore.write_run`'s docstring says it writes the directory "atomically" | `artifacts/store.py:36` | A tracked declaration with a static refutation candidate; an executed case must establish the experimental verdict, without weakening the original declaration |

The ten legacy success-path files are `manifest.json`, `sources.json`,
`analysis.json`, `generation.json`, `review.json`, `tool-calls.json`, `trace.json`,
`technical-spec.md`, `test-plan.md`, and `run-summary.md`. In the multi-agent
pipeline `_COMPLETE` records marker publication on either success or failure;
it does not replace an expected-file-set, hash, and runtime-state check, and does
not automatically detect post-finalize modification or deletion. REQ-078-4
defines the narrower interruption assertion.

## Requirements

- **REQ-080-1 — Establish the intended contract before judging the
  implementation.** Record the current `evidence_hash` projection above as
  identifying evidence selection, not the full bundle or audited tool activity.
  Do not add `tool_call_records` to the hash in this task. Preserve and audit
  any traceable broader declaration against this actual coverage; do not weaken
  the declaration to fit the implementation. Equal projections producing equal
  hashes are expected equality, not a SHA-256 collision.

- **REQ-080-2 — Audit both pipelines separately.** The multi-agent run directory
  and the legacy linear run directory do not provide the same integrity
  guarantee. Each is audited against its own implemented mechanism, and the
  resulting findings differ. Preserve each original declaration, including
  legacy "atomically", while describing the actual mechanism separately. A
  single combined "artifact integrity" claim is not permitted.

- **REQ-080-3 — Verify by experiment, not by reading.** For each audited claim,
  at least one executed case demonstrates the actual behavior. Where a
  source-code observation from the table above is relied upon, it is confirmed by
  an executed test or explicitly withdrawn. Reading the function is not a
  confirmation.

- **REQ-080-4 — A contract/implementation mismatch is recorded as `refuted`, not
  silently fixed.** If the audit finds that a declared coverage does not match
  the implementation — including a docstring claim that the implementation does
  not support — a valid executed counterexample makes the ledger entry `refuted`
  with its evidence. Static observations remain refutation candidates until
  experiment establishes the verdict. Fixing it is out
  of scope for this task and becomes a separate proposal. Applying REQ-M10-5, the
  entry must not be closed by re-labelling it.

- **REQ-080-5 — No guarantee widens.** This task may conclude that the current
  contract is correct and no change is needed. It may not conclude that evidence
  is fresh, that concurrent repository modification is impossible, or that a
  partially written artifact cannot be observed. Those are separate concerns and
  are non-goals.

- **REQ-080-6 — Audit decisions do not authorize runtime changes.** This task
  does not change the `evidence_hash` algorithm or field set, artifact formats,
  or persistence behavior. Any proposed correction requires separate explicit
  authorization outside T-080, with its own scope and regression/baseline
  handling. Recording a decision in this audit does not grant that authority.

- **REQ-080-7 — Audit objects and delivery surface.**
  `src/specflow/evidence/models.py`, `src/specflow/artifacts/store.py`, and
  `src/specflow/runner_multi.py` are **read-only audit objects**, not production
  files this task may modify. Future task changes are limited to audit tests,
  the minimum T-077 ledger integration, and the report; no runtime-contract or
  persistence change is permitted by this surface description.
  Expected tests are `tests/test_evidence_contract_audit.py`,
  `tests/test_artifact_integrity_contract.py`, and the affected existing
  evidence/artifact tests. If the audit requires a new dependency or a change to
  the agent topology or runtime contract, record the gap and seek separate
  authorization; do not repair it as part of this audit.

## Decisions applied in revision 4

1. Keep the current `evidence_hash` field set, including the exclusion of
   `tool_call_records`; describe projection equality accurately.
2. Track `ArtifactStore.write_run`'s "atomically" declaration. The source
   observation is a refutation candidate; future executed cases determine its
   experimental verdict. Neither implementation repair nor weakening that
   declaration is part of this task.
3. Describe the actual top-level scan and its exclusions. Do not claim recursive
   coverage or add it during the audit; audit any broader declaration separately.

## Boundaries

The following are explicit non-goals for T-080:

- **No freshness guarantee.** Whether the target repository changed between
  collection, use, and persistence is out of scope. No repository watching, file
  locking, filesystem snapshots, or OS-level change detection.
- Do not add a cache, TTL, or refresh mechanism; T-074 owns caching.
- Do not change the `evidence_hash` algorithm or field set, artifact format, or
  persistence behavior, even after recording an audit decision. REQ-080-6
  requires separate authorization outside this task.
- Do not rewrite the historical benchmark baseline as newly measured evidence.
- Do not modify the agent topology, prompts, or provider path.
- Do not fix a discovered mismatch inside this task.

## Acceptance

- **AC-080-1:** The intended contract for `evidence_hash` is recorded with its
  rationale, and the implementation is audited against that recorded contract —
  not against an assumed one.
- **AC-080-2:** The multi-agent and legacy integrity mechanisms are audited and
  reported separately, each with an executed case.
- **AC-080-3:** Every source-code observation relied upon is either confirmed by
  an executed test or explicitly withdrawn in the report.
- **AC-080-4:** Any contract/implementation mismatch found — including the
  tracked `ArtifactStore.write_run` atomicity declaration — is recorded as
  `refuted` when supported by a valid executed counterexample; static candidates
  are identified separately. The original declaration and implementation are
  not edited to remove a mismatch. Audit delivery and assurance acceptance
  remain separate under REQ-M10-5.
- **AC-080-5:** No acceptance criterion in this task asserts freshness, exclusion
  of concurrent modification, or any guarantee beyond the audited mechanisms.
  The audit diff changes none of the three read-only production objects,
  `evidence_hash` algorithm/fields, artifact formats, or persistence behavior.
- **AC-080-6:** Existing evidence, artifact, DLP, CLI/mock, and benchmark tests
  remain green.
- **AC-080-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-080-8:** `docs/reports/T-080-completion-report.md` records the intended
  contract, the audit result per pipeline, every confirmed or withdrawn
  observation, every `refuted` finding, actual coverage/exclusions, and the three
  decisions applied above. One focused commit is created, then work stops before T-079.
