# M10 specification freeze report

**Status:** DRAFT — awaiting freeze decision and independent review.
**Branch:** `docs/m10-runtime-assurance-spec`
**Base commit:** `1b44127` (`origin/main`, `security: harden repository and prompt trust boundaries`)
**Predecessor milestone:** M9 — Runtime Resilience & Efficiency (frozen in `02c1d3f`, branch `docs/m9-runtime-resilience-specs`)

## 1. Files added

| File | Purpose |
| --- | --- |
| `docs/tasks/M10-runtime-assurance-verification.md` | Milestone specification: goal, REQ-M10-1 through REQ-M10-10, boundaries, milestone acceptance, open questions |
| `docs/tasks/T-077-guarantee-boundary-ledger.md` | Full task specification for T-077 |
| `docs/tasks/T-078-deterministic-failpoints.md` | Full task specification for T-078 |
| `docs/tasks/M10-remaining-task-boundaries.md` | Boundary and dependency definitions for T-079, T-080, T-081 |
| `docs/reports/M10-specification-freeze-report.md` | This report |
| `REVIEW-REQUEST.md` | Review instructions and open questions for an independent reviewer |

## 2. Architecture decisions

- **AD-M10-1 — M10 is the complement of M9, not an extension.** M9 governs
  admission and execution-time control. M10 governs ex-post acceptance and
  guarantee verification. No M9 behavior is modified.
- **AD-M10-2 — Verification targets existing declarations only.** REQ-M10-1
  requires every assurance target to trace to an existing declaration (M9
  REQ-M9-4/-5/-6, the T-075 failure mapping, the T-057 interruption recovery
  contract, the T-071 circuit state machine, the artifact integrity contract, or
  documented fail-closed behavior). M10 invents no guarantee.
- **AD-M10-3 — `unverified` is a legitimate terminal state.** REQ-M10-7 and
  AC-M10-3 permit a task to close with declarations still unverified, and forbid
  relaxing a judgement to make the ledger pass.
- **AD-M10-4 — Fault injection is in-process, explicit, and inert by default.**
  REQ-078-1 forbids activation by environment variable, configuration, HTTP
  input, requirement text, or repository content.
- **AD-M10-5 — M10 implements no recovery.** REQ-M10-8, REQ-078-7, and the
  milestone boundaries forbid resume, continuation, compensation,
  reconciliation, and replay. If verification shows a recovery capability is
  missing, it becomes a proposal after M10.
- **AD-M10-6 — Single-process limits are stated, not approximated.**
  REQ-M10-6 requires multi-process and restart-time orchestration recovery to be
  reported as explicitly unverified, and T-081 is labelled non-claiming.
- **AD-M10-7 — Later specifications follow observed evidence.** REQ-M10-10 and
  `M10-remaining-task-boundaries.md` deliberately leave T-079, T-080, and T-081
  unspecified at module and field level, because T-079's fields depend on
  T-078's `undetermined` output and T-081's method depends on the assurance
  review.

## 3. Task dependencies

| Order | Task | Depends on | Output |
| --- | --- | --- | --- |
| 1 | T-077 Guarantee Boundary Ledger and Declaration Registry | M10 spec freeze | Ledger of declarations with judgement state and resolvable evidence references |
| 2 | T-078 Deterministic Failpoint Interface and Interrupt Matrix (Batch 1) | T-077 closed | Failpoint interface plus four interrupt cases with `consistent` / `violated` / `undetermined` conclusions |
| 3 | T-079 Unresolved-Item Aggregation and Assurance Status | T-078 closed | Bounded unresolved-item aggregate, observing only, never gating |
| 4 | T-080 Evidence Freshness and Snapshot Integrity Bound | T-079 closed | Explicit evidence-hash coverage decision plus a tested freshness bound |
| 5 | Milestone assurance review | T-077 through T-080 closed | Gate before T-081 |
| 6 | T-081 Multi-Process Boundary Probe (non-claiming) | Assurance review approved | Observation and documentation of the single-process limit; no fix authorized |

## 4. Unresolved risks

- **R-M10-1 — M9 is not closed.** T-070 through T-076 are frozen but
  unimplemented. M10 cites M9 boundary clauses (REQ-M9-4, REQ-M9-5, REQ-M9-6) and
  must not begin before the tasks it cites are closed. Nothing in M10 detects a
  premature start automatically.
- **R-M10-2 — The evidence-hash observation is unexecuted.** The T-080
  motivation states that `EvidenceBundle._calculate_hash()` hashes
  `matched_files`, `selected_files`, `searched_terms`, excerpts, and `truncated`,
  and does not hash `source_hashes`, `tool_call_records`, `warnings`,
  `project_summary`, or `technology_stack`. This was read from source and has not
  been demonstrated by experiment. It is carried as an unverified observation,
  and T-080 requires it to be confirmed or withdrawn.
- **R-M10-3 — `undetermined` may dominate.** If existing contracts do not define
  behavior at most Batch 1 interruption points, T-078 will return mostly
  `undetermined`. That is the intended honest outcome, but it may produce a
  milestone that proves little. The assurance review exists to make that visible
  before T-081.
- **R-M10-4 — Scope pressure from T-081.** A multi-process probe is close to
  authorization for multi-process work. The non-claiming label and the explicit
  prohibition on implementing a fix are the only guards; reviewers should
  confirm they are sufficient.
- **R-M10-5 — Ledger maintenance burden.** T-077 requires declaration source
  references that resolve mechanically. If the repository renames sections or
  moves reports, references can rot into `unverified` without a real change in
  evidence. The ledger design must make that failure mode visible rather than
  silent.

## 5. Validation evidence for this branch

To be completed when the freeze decision is made. Required checks:

```powershell
git diff --stat origin/main...docs/m10-runtime-assurance-spec
git diff --name-only origin/main...docs/m10-runtime-assurance-spec
```

Required outcome: every changed path is either under `docs/` or is
`REVIEW-REQUEST.md`, and no runtime implementation, test, benchmark fixture,
dependency, or generated artifact is present.

## 6. No-runtime-implementation confirmation

To be completed at freeze. This branch is intended to contain documentation only.
No file under `src/`, `tests/`, `benchmarks/`, `scripts/`, `prompts/`, or
`evaluation/` is added or modified, and no dependency manifest is changed.
