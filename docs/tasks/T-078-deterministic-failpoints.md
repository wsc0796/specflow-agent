# T-078 — Deterministic Failpoint Interface and Interrupt Matrix (Batch 1)

**Status:** DRAFT FOR FREEZE. Implementation requires T-077 closed plus a new
focused session.

## Goal

Provide an explicit, default-inert, test-only failpoint interface, and use it to
verify that interrupting the single-process multi-agent runtime at fixed
interruption points always lands the run inside the existing classified outcome
set, with no silent discard, no partial artifact presented as complete, and no
unclassifiable hanging state.

## Requirements

- **REQ-078-1 — Failpoints are inert by default.** A failpoint is an explicit
  injection point in code that has no effect on any production path. It must not
  be activatable by environment variable, configuration file, HTTP input,
  requirement text, or repository content. Only explicit in-process registration
  inside a test may activate it, and that registration is unreachable from
  outside the process.

- **REQ-078-2 — The Batch 1 interruption set is fixed and limited.** Batch 1
  covers only the following interruption points and must not be extended during
  this task:

  1. after an agent completes, before workflow state advances
  2. after handoff validation succeeds, before the handoff is committed
  3. after the revision counter increments, before the next round begins
  4. after artifact writing begins, before the completion marker is written

- **REQ-078-3 — Every case declares its expectation before execution.** Each case
  declares, before running, the expected classified outcome and the guarantee
  that should hold at that point. When observed behavior differs, the case fails
  and records the difference. The expectation must not be adjusted to match the
  observation.

- **REQ-078-4 — Distinguish agreement from violation from undecidability.** The
  verification output distinguishes exactly three conclusions: `consistent`
  (observed behavior matches the declared guarantee), `violated` (observed
  behavior contradicts it), and `undetermined` (the existing contract does not
  define the behavior at that point). `undetermined` must be listed explicitly
  and routed to the T-077 ledger as `unverified`. It must not be merged into
  `consistent`.

- **REQ-078-5 — Use existing entry points.** Cases execute through the existing
  mock multi-agent CLI path and the existing lifecycle and artifact boundaries.
  No dedicated test back door may bypass orchestration.

- **REQ-078-6 — Deterministic and fast.** No live provider call, no `sleep`, no
  real timer, and no dependence on machine speed. Repeated runs against the same
  checkout state reach identical conclusions.

- **REQ-078-7 — No recovery, no behavior change.** After interruption the system
  may terminate or fail exactly as it currently does. M10 does not implement
  resume, retry, or compensation. If the observation shows that a recovery
  capability is missing, that is recorded in the report and in the unresolved
  list only.

- **REQ-078-8 — Audit records are bounded and safe.** Each case records the
  interruption-point ID, the expected classification, the observed
  classification, the conclusion, and bounded evidence references. It must not
  contain prompts, requirement text, repository contents, absolute paths,
  credentials, or provider data.

- **REQ-078-9 — Expected implementation surface.** Expected production files are
  a focused `src/specflow/assurance/failpoints.py` plus the minimum injection
  points inside the existing `coordinator/`, `executor/`, `artifacts/`, and
  `runner_multi.py`. Expected tests are `tests/test_failpoint_matrix.py`,
  `tests/test_assurance_failpoints.py`, and the affected existing orchestration
  and artifact tests. If an injection point would require rewriting orchestration
  control flow or introducing new state, stop and amend the specification with
  evidence before editing.

## Boundaries

The following are explicit non-goals for T-078:

- Do not cover process-level kill, signals, power loss, real crashes, or
  forced termination of in-flight threads. That is the separate, non-claiming
  probe in T-081.
- Do not implement any recovery, continuation, compensation, reconciliation,
  replay, or idempotency capability.
- Do not add a vertex, stage, or state; do not change the revision bound; do not
  touch handoff schemas or DLP.
- Do not introduce a chaos-engineering library, fault-injection proxy, container
  interference, or network-layer interference.
- Do not verify multi-process or multi-instance assumptions.
- Do not substitute "the observed result looks reasonable" for comparison
  against the declaration, and do not fold `undetermined` into `consistent`.

## Acceptance

- **AC-078-1:** Tests prove failpoints have no effect without explicit
  registration, and cannot be activated by environment variable, configuration,
  or input.
- **AC-078-2:** Each of the four Batch 1 interruption points has a case, and each
  case declares its expected classified outcome before execution.
- **AC-078-3:** Tests prove that after any interruption the outcome falls inside
  the existing classified outcome set, and that no silent discard, no partial
  artifact reported as complete, and no unclassifiable hanging state occurs.
- **AC-078-4:** Output distinguishes `consistent`, `violated`, and `undetermined`
  explicitly, and `undetermined` entries are listed separately and are
  consumable by the T-077 ledger.
- **AC-078-5:** All cases perform no network I/O, use no `sleep`, call no live
  provider, and reach identical conclusions on repeated runs.
- **AC-078-6:** Existing orchestration, artifact-integrity, DLP, CLI/mock, and
  benchmark tests remain green.
- **AC-078-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-078-8:** `docs/reports/T-078-completion-report.md` records the
  interruption-point list, the expected and observed outcome for each, the
  conclusion distribution, every `undetermined` entry with its reason, and an
  explicit statement that M10 implements no recovery. One focused commit is
  created, then work stops before T-079.
