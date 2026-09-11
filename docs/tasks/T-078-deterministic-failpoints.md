# T-078 — Deterministic Failpoint Interface and Interrupt Matrix (Batch 1)

**Status:** DRAFT FOR FREEZE — REVISION 2. Implementation requires T-077 closed
with a readable completion report at a named commit, plus a new focused session.

## Goal

Provide an explicit, default-inert, test-only failpoint interface, and use it to
verify that interrupting the multi-agent runtime at four fixed interruption
points always lands the run inside the existing classified outcome set, with no
silent discard, no partial artifact presented as complete, and no unclassifiable
hanging state.

## Verified baseline facts

These were read from `origin/main` at the frozen base commit and constrain what
the cases may assert. Each is a source-code observation, not an executed result.

| Fact | Location | Consequence for this task |
| --- | --- | --- |
| `_finalize_run_directory` writes `artifact-integrity.json` (per-file SHA-256) and then `_COMPLETE` last, via `_safe_write` (`temp` + `fsync` + `os.replace`) | `runner_multi.py:848-876` | A write completed through `os.replace` is observable; a file that never got that far is absent, not partial |
| `_finalize_run_directory` is called on the **success** path | `runner_multi.py:517`, followed by `return 0` | `_COMPLETE` present is consistent with a successful run |
| `_finalize_run_directory` is **also** called on the **failed** path after writing `manifest.json`, `traces.json`, and `agent-outputs.json` | `runner_multi.py:924-945` | **`_COMPLETE` present does not mean the run succeeded.** It means the run directory finished being written. No case may treat `_COMPLETE` as a success indicator |
| Legacy persistence is `ArtifactStore.write_run`, which writes nine files with `path.write_text` and removes the directory in an `except` block | `artifacts/store.py:24-88` | Legacy persistence is not per-file atomic and has no integrity file or completion marker; its cleanup does not cover process termination. Removing the interruption matrix's reliance on "the pipeline is atomic" |
| `recover_interrupted_runs` lives in the Run API startup path | `main.py:13`, `main.py:34`, implemented at `runs.py:267` | The CLI does not exercise it. A CLI case cannot claim coverage of the API lifecycle contract |
| Policy/persistence failures return exit code `3`; the success path returns `0` | `runner_multi.py:497`, `:519`, `:520` | Exit code is part of the recordable observable |

## Requirements

### Case specification

- **REQ-078-1 — Every case is fully specified before it runs.** A case may not be
  authored by choosing an interruption point and observing what happens. Each
  case declares, in the test specification, all six of the following. A case
  missing any row is not executable.

  | Row | Content |
  | --- | --- |
  | Interruption location | The named failpoint and the exact point it interrupts |
  | Injected fault type | The mechanism used, chosen from the closed set in REQ-078-3 |
  | Real entry point | Which of the entry points in REQ-078-5 the case actually traverses |
  | Expected lifecycle classification | The expected workflow state or lifecycle record |
  | Expected exit code | The expected process exit code, and `n/a` with a reason where the entry point has none |
  | Expected artifact state | Which artifact files are expected present or absent, plus the expected `_COMPLETE` and `artifact-integrity.json` state |
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
  indicator.** Because both the success and the failed path call
  `_finalize_run_directory`, the assertion for interruption point 4 is:

  > After an interruption before the completion marker is written, `_COMPLETE`
  > must be **absent**, and any artifact present must be individually complete or
  > absent — never partially written under a name that reads as complete.

  A case that asserts "`_COMPLETE` present therefore the run succeeded" is
  invalid and must be rejected in review.

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
  assurance pass.

- **REQ-078-7 — Three-valued conclusions are decided before execution.** Per
  REQ-M10-9:

  | Conclusion | Meaning | When it may be assigned |
  | --- | --- | --- |
  | `consistent` | Observed behavior matches the declared guarantee | After execution |
  | `violated` | Observed behavior contradicts a declaration | After execution; routed to the ledger as `refuted`; never reclassified |
  | `undetermined` | The existing contract does not define the behavior here | **Before execution**, from reading the contract; never assigned after seeing an unexpected result |

  A case that could not be executed reports not-verified, never `consistent`.
  `undetermined` entries are listed explicitly and consumed by the T-077 ledger.

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

- **REQ-078-12 — Audit records are bounded and safe.** Each case records the
  interruption-point ID, injected fault type, entry point, expected and observed
  classification, conclusion, targeted declaration, and bounded evidence
  references. It must not contain prompts, requirement text, content read from an
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

## Acceptance

- **AC-078-1:** Tests prove failpoints have no effect without explicit
  registration and cannot be activated by environment variable, configuration,
  or input.
- **AC-078-2:** Tests prove registration is released on success, on ordinary
  exception, on `SystemExit`, and on `KeyboardInterrupt`, and that one case's
  registration cannot affect another case, including under concurrent execution.
- **AC-078-3:** Each of the four Batch 1 interruption points has a case, and each
  case carries all six REQ-078-1 rows before execution.
- **AC-078-4:** A test proves that after an interruption before the completion
  marker is written, `_COMPLETE` is absent and no artifact is present in a
  partially written form under a complete-sounding name.
- **AC-078-5:** A test proves that `_COMPLETE` present is not treated as success:
  a failed-path run that reached `_finalize_run_directory` is classified as
  failed, not as completed.
- **AC-078-6:** Tests prove that after any interruption the outcome falls inside
  the existing classified outcome set, with no silent discard, no partial
  artifact reported as complete, and no unclassifiable hanging state.
- **AC-078-7:** Output distinguishes mechanism verdict, claim verdict, and
  closure verdict; distinguishes `consistent`, `violated`, and `undetermined`;
  and lists `undetermined` and `violated` entries separately in a form the T-077
  ledger consumes.
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
  interruption-point list, the six REQ-078-1 rows per case, the expected and
  observed outcome for each, the mechanism/claim/closure verdicts, every
  `undetermined` and `violated` entry with its reason, an explicit statement of
  which entry points were and were not exercised, and an explicit statement that
  M10 implements no recovery. One focused commit is created, then work stops
  before T-080.
