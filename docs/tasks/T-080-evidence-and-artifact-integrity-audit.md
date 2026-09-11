# T-080 — Evidence and Artifact Integrity Contract Audit

**Status:** DRAFT FOR FREEZE — REVISION 2. Implementation requires T-078 closed
with a readable completion report at a named commit, plus a new focused session.

**Ordering note:** this task now precedes T-079. Revision 1 chained it after
T-079, which was unnecessary; the audit constrains what T-079 may report and
therefore belongs earlier.

## Goal

Determine, record, and test what the two existing integrity mechanisms actually
guarantee: what the evidence hash identifies, what the per-file artifact hashes
and completion marker identify, and whether the declared coverage of each matches
its implementation. The deliverable is a decision plus tests, not a widened
guarantee.

## The three objects must not be conflated

Applying REQ-M10-2, this task keeps these separate and answers each on its own
terms. Revision 1 mixed them, which let a hash-coverage question read as a
freshness claim.

| Object | Question it answers | Source of truth |
| --- | --- | --- |
| `evidence_hash` | Which evidence **semantics** does this value identify? | `evidence/models.py` `EvidenceBundle._calculate_hash` and its contract |
| Artifact file hashes | Has a written artifact file changed since it was written? | `runner_multi.py` `_finalize_run_directory` / `artifact-integrity.json` |
| Freshness | Did the target repository change between evidence collection, use, and persistence? | **Not covered by this task.** See the non-goals |

## Verified baseline facts

Read from `origin/main` at the frozen base commit. Source-code observations, not
executed results.

| Fact | Location | Consequence |
| --- | --- | --- |
| `_calculate_hash` hashes `matched_files`, `selected_files`, `searched_terms`, the `(relative_path, line_number, excerpt)` triples, and `truncated` | `evidence/models.py` | `source_hashes`, `tool_call_records`, `warnings`, `project_summary`, and `technology_stack` are outside the hashed payload |
| `EvidenceBundle` carries `source_hashes` and `tool_call_records` as its own audited fields | `evidence/models.py` | Two runs with the same excerpt set but different audited tool activity can produce the same `evidence_hash` |
| `_finalize_run_directory` hashes each top-level file with SHA-256 and writes `artifact-integrity.json` | `runner_multi.py:855-869` | Artifact-file integrity is a **separate** mechanism from `evidence_hash` and was the missing half of revision 1's reasoning |
| `_finalize_run_directory` runs on both the success and the failed path | `runner_multi.py:517`, `:945` | The artifact-integrity declaration is about written-directory integrity, not business success |
| `ArtifactStore.write_run` writes nine files with `path.write_text`, removes the directory in an `except` block, and has no integrity file or completion marker | `artifacts/store.py:24-88` | The legacy pipeline's integrity guarantee differs from the multi-agent one and must be audited separately |
| `ArtifactStore.write_run`'s docstring says it writes the directory "atomically" | `artifacts/store.py:36` | A declared-versus-implemented question in its own right; see the open decisions |

## Requirements

- **REQ-080-1 — Establish the intended contract before judging the
  implementation.** For `evidence_hash`, decide and record what the value is
  *for*: identifying the evidence selection (files, excerpts, search terms,
  truncation), or identifying the full evidence bundle including audited tool
  activity and source content. The decision is recorded with its rationale. The
  task must not begin from the assumption that all fields belong in the hash.

- **REQ-080-2 — Audit both pipelines separately.** The multi-agent run directory
  and the legacy linear run directory do not provide the same integrity
  guarantee. Each is audited against its own implemented mechanism, and the
  resulting declarations differ. A single combined "artifact integrity" claim is
  not permitted.

- **REQ-080-3 — Verify by experiment, not by reading.** For each audited claim,
  at least one executed case demonstrates the actual behavior. Where a
  source-code observation from the table above is relied upon, it is confirmed by
  an executed test or explicitly withdrawn. Reading the function is not a
  confirmation.

- **REQ-080-4 — A contract/implementation mismatch is recorded as `refuted`, not
  silently fixed.** If the audit finds that a declared coverage does not match
  the implementation — including a docstring claim that the implementation does
  not support — the ledger entry is `refuted` with its evidence. Fixing it is out
  of scope for this task and becomes a separate proposal. Applying REQ-M10-5, the
  entry must not be closed by re-labelling it.

- **REQ-080-5 — No guarantee widens.** This task may conclude that the current
  contract is correct and no change is needed. It may not conclude that evidence
  is fresh, that concurrent repository modification is impossible, or that a
  partially written artifact cannot be observed. Those are separate concerns and
  are non-goals.

- **REQ-080-6 — Any contract change is its own decision.** If the audit
  determines that the hashed field set should change, that change requires a
  recorded decision, its own regression coverage, and — where the change alters a
  persisted baseline — explicit handling of the historical baseline rather than
  rewriting it as newly measured.

- **REQ-080-7 — Expected implementation surface.** Expected production files are
  `src/specflow/evidence/models.py` (only if a decision requires a change),
  `src/specflow/artifacts/store.py` and `src/specflow/runner_multi.py` (audit
  surface, not necessarily modified), plus the minimum ledger integration.
  Expected tests are `tests/test_evidence_contract_audit.py`,
  `tests/test_artifact_integrity_contract.py`, and the affected existing
  evidence/artifact tests. If the audit requires a new dependency or a change to
  the agent topology, stop and amend the specification.

## Open decisions for the reviewer

1. Should the hashed payload include `tool_call_records`, given that two runs
   with identical excerpts but different audited tool activity currently collide?
2. Is the `ArtifactStore.write_run` "atomically" docstring a declaration the
   ledger should track, and if so, is the correct state `refuted`?
3. Does the multi-agent path need to cover files in subdirectories, or is the
   top-level `iterdir()` scan the intended contract?

## Boundaries

The following are explicit non-goals for T-080:

- **No freshness guarantee.** Whether the target repository changed between
  collection, use, and persistence is out of scope. No repository watching, file
  locking, filesystem snapshots, or OS-level change detection.
- Do not add a cache, TTL, or refresh mechanism; T-074 owns caching.
- Do not change the evidence contract silently, and do not change any field
  coverage without a recorded decision under REQ-080-6.
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
  `ArtifactStore.write_run` atomicity docstring if the audit determines it is a
  tracked declaration — is recorded as `refuted` with evidence and is not fixed
  in this task.
- **AC-080-5:** No acceptance criterion in this task asserts freshness, exclusion
  of concurrent modification, or any guarantee beyond the audited mechanisms.
- **AC-080-6:** Existing evidence, artifact, DLP, CLI/mock, and benchmark tests
  remain green.
- **AC-080-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-080-8:** `docs/reports/T-080-completion-report.md` records the intended
  contract, the audit result per pipeline, every confirmed or withdrawn
  observation, every `refuted` finding, and the decisions taken on the three open
  decisions above. One focused commit is created, then work stops before T-079.
