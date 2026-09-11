# T-078 — Deterministic Failpoint Interface and Interrupt Matrix (Batch 1)

**Status:** SPECIFICATION FROZEN — REVISION 4; see the user-transferred AI-assisted
static re-review registration in the
[freeze report §8](../reports/M10-specification-freeze-report.md#8-revision-4-freeze-registration).
Implementation remains subject to REQ-M10-12 and requires T-077 closed
with a readable completion report at a named commit, plus a new focused session.

## Goal

Provide an explicit, default-inert, test-only failpoint interface, and use it to
verify that interrupting the multi-agent runtime at four fixed interruption
points always lands the run inside the existing classified outcome set, with no
silent discard, no partial artifact presented as complete, and no unclassifiable
hanging state.

## Source-code baseline observations

These were read at `START_HEAD=9adcddb46f2977ea122966c1167e48fe2592d8be`
(the cited code is unchanged from PR_BASE `1b44127`). Each is a source-code
observation, not an executed fault experiment. Future cases must separately bind
their declaration-source version and actual tested-code commit/configuration.

| Fact | Location | Consequence for this task |
| --- | --- | --- |
| `_finalize_run_directory` writes `artifact-integrity.json` (per-file SHA-256) and then `_COMPLETE` last, via `_safe_write` (`temp` + `fsync` + `os.replace`) | `runner_multi.py:815-876` | Before replacement a new final target is absent, but an existing target may retain its old contents; temporary files are not final artifacts |
| `_finalize_run_directory` is called on the **success** path | `runner_multi.py:517`, followed by `return 0` | `_COMPLETE` present is consistent with a successful run |
| `_finalize_run_directory` is **also** called on the **failed** path after writing `manifest.json`, `traces.json`, and `agent-outputs.json` | `runner_multi.py:924-945` | **`_COMPLETE` present does not mean the run succeeded.** It records completion-marker publication, not current file-set completeness or business success |
| Legacy persistence is `ArtifactStore.write_run`, whose success path writes ten files with `path.write_text` and whose `except Exception` block removes the directory | `artifacts/store.py:24-87` (ten writes at `:43-58`) | Legacy has no per-file atomic replacement, integrity file, or completion marker. Its cleanup is an exception path, not a process-termination guarantee; atomicity remains an experimental audit target |
| `recover_interrupted_runs` lives in the Run API startup path | `main.py:13`, `main.py:34`, implemented at `runs.py:267` | The CLI does not exercise it. A CLI case cannot claim coverage of the API lifecycle contract |
| Policy/persistence failures return exit code `3`; the success path returns `0` | `runner_multi.py:497`, `:519`, `:520` | Exit code is part of the recordable observable |

## Requirements

### Case specification

- **REQ-078-1 — Every case is fully specified before it runs.** A case may not be
  authored by choosing an interruption point and observing what happens. Each
  case declares, in the test specification, all seven of the following. A case
  missing any row is not executable.

  | Row | Content |
  | --- | --- |
  | Interruption location | The expected failpoint ID, exact point it interrupts, and preset expected hit count |
  | Injected fault type | The mechanism used, chosen from the closed set in REQ-078-3 |
  | Real entry point | Which of the entry points in REQ-078-5 the case actually traverses |
  | Expected lifecycle classification | The expected workflow state or lifecycle record |
  | Expected exit code | The expected process exit code, and `n/a` with a reason where the entry point has none |
  | Expected artifact state | Initial directory/file state, expected final artifact names and contents/hashes, `_COMPLETE` and `artifact-integrity.json` state, and whether a later finalize is possible; REQ-078-4 governs |
  | Targeted declaration | The declaration ID this case produces evidence for, and the boundary this case does **not** cover |

- **REQ-078-2 — The Batch 1 interruption set is fixed and limited.** Batch 1
  covers only these four interruption points and must not be extended during this
  task:

  1. after an agent completes, before workflow state advances
  2. after handoff validation succeeds, before the handoff is committed
  3. after the revision counter increments, before the next round begins
  4. after artifact writing begins, before the completion marker is written

  Implementing the artifact-write case first to open the evidence chain is
  permitted. It does not substitute for the other three.

- **REQ-078-3 — The injected fault set is closed.** A case's injection mechanism
  is one of: a raised ordinary `Exception` subclass, `SystemExit`, or
  `KeyboardInterrupt`. These may not be treated as interchangeable: Python places
  `SystemExit` and `KeyboardInterrupt` outside `Exception`, and the runtime has
  more than one exception-handling layer. Where two mechanisms are expected to
  produce different classifications, that difference is itself the case's
  assertion, and the two may not be collapsed into one case.

- **REQ-078-4 — `_COMPLETE` is an integrity indicator, not a success
  indicator.** Both success and failure paths may call
  `_finalize_run_directory`. The missing-marker assertion for interruption
  point 4 applies only to an isolated test directory with no initially published
  completion marker, a fault before this publication, and no later completed
  finalize in the case:

  > Under these preconditions, `_COMPLETE` must be **absent**. Each formal
  > artifact target is complete or absent, never a partially replaced file.
  > This assertion concerns final artifact paths, not temporary files. If a
  > target already existed, interruption before replacement may leave the old
  > complete file; it does not imply that the target is absent.

  A case that asserts "`_COMPLETE` present therefore the run succeeded" is
  invalid and must be rejected in review. A finalized failed run remains failed
  according to its business/runtime state. Do not generalize point 4 to all
  failed or interrupted runs: a subsequent failure-path finalize may publish
  the marker. Marker absence is not evidence that a failpoint was hit; actual
  hit evidence is required by REQ-078-12. Marker presence does not replace
  checking the expected file set, per-file hashes, and run state, and the marker
  does not automatically detect later modification or deletion of files.

### Entry points and coverage honesty

- **REQ-078-5 — Each declaration is bound to the entry point that can actually
  observe it.** The following table is normative. A case must record which row it
  traverses, and may not claim coverage belonging to another row.

  | Entry point | What it can cover | What it cannot cover |
  | --- | --- | --- |
  | Mock multi-agent runner (`run_multi_agent`) | Interruption behavior of the orchestration and artifact write path | API lifecycle records |
  | Mock multi-agent CLI | Runner behavior plus CLI exit codes and error-artifact conventions | API lifecycle records, database state |
  | Run API lifecycle (mock-only) | SQLite lifecycle records, interruption recovery on startup | Live provider paths |
  | `recover_interrupted_runs()` directly | Classification of pre-existing `running` records | Anything that requires an actual interrupted process |

  A CLI-based interrupt case **must not** be reported as verifying the T-057 API
  lifecycle contract. If Batch 1 cases traverse only the runner and CLI, the API
  lifecycle declaration remains `declared`, and the completion report must say
  so.

- **REQ-078-6 — Mechanism verdict and claim verdict are reported separately.**
  Applying REQ-M10-4, each case reports three things independently: whether the
  mechanism behaved as designed, whether the targeted declaration held, and
  whether the task may close. A correct `violated` result is a working mechanism
  and a failed or contradicted declaration; it must not be presented as an
  assurance pass. A missing hit, wrong location, wrong hit count or fault type,
  unexecuted case, or incomplete record fails the mechanism and supports neither
  `consistent` nor `violated`. Actual hits must be checked against the preset
  using REQ-078-12, independently of artifact similarity. Audit discovery and
  reporting may complete with a valid counterexample recorded as `refuted`, but
  a violation of the required safety boundaries in AC-078-6 fails M10 assurance
  acceptance. Repair requires separate authorization.

- **REQ-078-7 — Expectations and contract gaps are fixed before execution.**
  Per REQ-M10-9, the claim verdict follows a valid experiment:

  | Conclusion | Meaning | When it may be assigned |
  | --- | --- | --- |
  | `consistent` | Valid observed behavior supports the guarantee within the case's coverage | After execution with matching versions and verified actual injection |
  | `violated` | Valid observed behavior contradicts a declaration | After execution with matching versions and verified actual injection; routed to the ledger as `refuted`; never reclassified |
  | `undetermined` | The existing contract does not define the behavior here | **Before execution**, from reading the contract; never assigned after seeing an unexpected result |

  A skipped, unexecuted, version-mismatched, or mechanism-failed case reports
  not-verified, never `consistent` or `verified`; it cannot refute the target
  declaration either. `undetermined` entries are listed explicitly as project
  contract gaps and consumed by the T-077 ledger, never as verified claims or
  automatic run-local unresolved items.

### Failpoint interface

- **REQ-078-8 — Failpoints are inert by default.** A failpoint is an explicit
  injection point that has no effect on any production path and must not be
  activatable by environment variable, configuration file, HTTP input,
  requirement text, or repository content. Only explicit in-process registration
  inside a test may activate one, and that registration is unreachable from
  outside the process. A name containing "test" is not evidence of safety.

- **REQ-078-9 — Registration is scoped, released, and isolated.** Registration
  is bounded to one case; it is released on success, on failure, and on
  exception, including `SystemExit` and `KeyboardInterrupt`. Tests must prove
  that a registration from one case cannot affect a subsequent case, and that
  registrations in concurrently executing cases do not interfere. This is an
  explicit design requirement, not an assumption.

### Constraints

- **REQ-078-10 — Deterministic and fast.** No live provider call, no `sleep`, no
  real timer, and no dependence on machine speed. Repeated runs against the same
  checkout state reach identical conclusions.

- **REQ-078-11 — No recovery, no behavior change.** After interruption the system
  terminates or fails exactly as it currently does. M10 does not implement
  resume, retry, or compensation. A missing recovery capability is recorded in
  the report and the unresolved list, and becomes a proposal after M10.

- **REQ-078-12 — Audit records include actual test-side hit evidence.** Each
  case saves and checks the preset failpoint ID and hit count against the ID
  actually reached on the real execution path, actual hit count, actual injected
  fault type, and real entry point. The actual-hit record is generated only when
  execution reaches the injection point; pre-filling actual hits with expected
  values before execution is forbidden. Test-side recording is allowed without
  adding production manifest, log, or business-state fields. Similar artifacts
  from different faults do not waive actual-hit verification.

  The bounded case record also includes post-injection exit code (`n/a` with
  reason where appropriate), state and artifacts, expected/observed
  classification, mechanism/claim/closure verdicts, targeted declaration, source
  commit, tested-code commit/configuration, and bounded evidence references.
  No hit, wrong point, or unexpected count is mechanism failure, not evidence
  supporting or refuting a declaration. Records must not contain prompts,
  requirement text, content read from an
  analyzed target repository, absolute paths, credentials, or provider data.

- **REQ-078-13 — Expected implementation surface.** Expected production files are
  a focused `src/specflow/assurance/failpoints.py` plus the minimum injection
  points inside the existing `coordinator/`, `executor/`, `artifacts/`, and
  `runner_multi.py`. Expected tests are `tests/test_failpoint_matrix.py`,
  `tests/test_assurance_failpoints.py`, and the affected existing orchestration
  and artifact tests. If an injection point would require rewriting orchestration
  control flow or introducing new state, stop and amend the specification with
  evidence before editing.

## Boundaries

The following are explicit non-goals for T-078:

- **Do not cover process-level kill, signals, real crashes, or forced
  termination of in-flight threads.** These are outside M10's required scope and
  are not assigned to any M10 task. Adding a case for them requires a separate
  authorized specification.
- Do not implement any recovery, continuation, compensation, reconciliation,
  replay, or idempotency capability.
- Do not add a vertex, stage, or state; do not change the revision bound; do not
  touch handoff schemas or DLP.
- Do not introduce a chaos-engineering library, fault-injection proxy, container
  interference, or network-layer interference.
- Do not verify multi-process or multi-instance assumptions.
- Do not substitute "the observed result looks reasonable" for comparison
  against the declaration, and do not fold `undetermined` or `violated` into
  `consistent`.
- Do not treat the completion marker as a success indicator; REQ-078-4 governs.
- Do not add production manifest, log, or business-state fields to identify an
  interruption. Actual-hit evidence belongs to the test mechanism. This revision
  specifies that future mechanism; it implements no failpoint or new test.

## Acceptance

- **AC-078-1:** Tests prove failpoints have no effect without explicit
  registration and cannot be activated by environment variable, configuration,
  or input.
- **AC-078-2:** Tests prove registration is released on success, on ordinary
  exception, on `SystemExit`, and on `KeyboardInterrupt`, and that one case's
  registration cannot affect another case, including under concurrent execution.
- **AC-078-3:** Each of the four Batch 1 interruption points has a case, and each
  case carries all seven REQ-078-1 rows before execution. Tests check actual
  hit ID, count, fault type, entry point, and post-injection observables per
  REQ-078-12. No-hit, wrong-location, and wrong-count cases fail the mechanism
  and cannot yield `consistent` or refute a declaration.
- **AC-078-4:** A test proves the missing-marker assertion only under the
  isolated-directory, initial-state, and no-later-finalize preconditions in
  REQ-078-4. Final artifact targets are complete or absent; a pre-existing target
  can retain its old complete contents before replacement. Temporary files are
  not treated as final artifacts, and marker absence is not hit evidence.
- **AC-078-5:** A test proves that `_COMPLETE` present is not treated as success:
  a failed-path run that reached `_finalize_run_directory` is classified as
  failed, not as completed. The expected file set, hashes, and run state are
  checked separately; marker presence is not an automatic post-finalize
  modification/deletion detector.
- **AC-078-6:** Tests prove that after any interruption the outcome falls inside
  the existing classified outcome set, with no silent discard, no partial
  artifact reported as complete, and no unclassifiable hanging state.
  These existing safety boundaries remain required for every valid Batch 1
  case; pre-recording an undefined agent-level outcome does not waive them.
  A valid counterexample is retained as `violated` / `refuted` and fails the
  affected guarantee and M10 assurance acceptance, even if its audit is complete.
- **AC-078-7:** Output distinguishes mechanism verdict, claim verdict, and
  closure verdict; distinguishes `consistent`, `violated`, and `undetermined`;
  and lists `undetermined` and `violated` entries separately in a form the T-077
  ledger consumes. Output cannot hide `refuted` in `declared`, generic issue
  counts, or a success summary. Tests distinguish completed audit delivery from
  failed assurance acceptance; invalid mechanism evidence decides neither claim
  support nor refutation.
- **AC-078-8:** Each case records its entry point per REQ-078-5, and the
  completion report states explicitly which declarations Batch 1 did **not**
  cover, including the API lifecycle declaration where CLI-only coverage applies.
- **AC-078-9:** All cases perform no network I/O, use no `sleep`, call no live
  provider, and reach identical conclusions on repeated runs.
- **AC-078-10:** Existing orchestration, artifact-integrity, DLP, CLI/mock, and
  benchmark tests remain green.
- **AC-078-11:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-078-12:** `docs/reports/T-078-completion-report.md` records the
  interruption-point list, the seven REQ-078-1 rows per case, actual-hit evidence
  per REQ-078-12, the expected and
  observed outcome for each, the mechanism/claim/closure verdicts, every
  `undetermined` and `violated` entry with its reason, an explicit statement of
  which entry points were and were not exercised, and an explicit statement that
  M10 implements no recovery. One focused commit is created, then work stops
  before T-080.
