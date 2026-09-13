# T-079 — Run-Local and Project-Level Assurance Reporting

**Status:** SCOPE, ENTRY POINTS, AND JUDGEMENT CRITERIA FROZEN — REVISION 4;
see the [freeze report §8](../reports/M10-specification-freeze-report.md#8-revision-4-freeze-registration).
Field-level detail remains deferred to this task's own refinement and freeze
after its predecessors close, as required by AC-M10-1 / REQ-M10-12. Implementation
requires T-078 and T-080 closed with readable completion reports at named commits,
that field-level specification freeze, and a new focused session. This
registration does not declare all details complete or authorize implementation.

**Revision note:** revision 1 aggregated run-local unresolved items and
project-level unverified declarations into one health conclusion. Those are
different subjects: *this run left work needing attention* and *this project has
not verified a behavior* are not the same statement, and a healthy run must not
be reported as unhealthy merely because the project carries an unverified
declaration.

## Goal

Report two separate dimensions — what a finished run leaves unresolved, and which
declarations the project has not verified or has refuted — using explicit,
reviewable rules within each dimension, without a combined score.

## Two dimensions, reported separately

- **Dimension A — Run-local unresolved items.** Work this run left behind. Sourced
  from facts bound to an actual run that the runtime already records or can
  derive deterministically. Potential inputs, subject to REQ-079-1, include
  degraded outcomes, `fallback_used`, exhausted revision budget, failed or
  unvalidated schema checks, pending human review decisions, cache `invalid` or
  `write_failed` states. None is an unresolved item merely by appearing in this
  list; an explicit rule must bind it to unfinished delivery/use obligations
  for that run.

- **Dimension B — Project-level declaration states.** The ledger state of each
  declaration: `verified`, `declared`, `refuted`, `not_applicable`. Applying
  REQ-077-6, every `refuted` entry is reported individually and is never merged
  into a count or bucket that hides it. T-078's undefined contracts and project
  verification gaps belong here; `undetermined` is a recorded gap, not a fifth
  ledger state or a generic Dimension A source.

The two dimensions are reported side by side. No combined score or health
summary merges their subjects.

## Requirements

- **REQ-079-1 — Business outcomes are not unresolved items by default.** A
  business `REJECT`, a business-rule-permitted degradation, or a documented
  fallback, or missing optional review opinion does not become a Dimension A
  item by default. A pending human decision is an item only when the existing
  contract requires that decision before this run's deliverable can be completed
  or used. The rule must name the actual run, business fact, required decision,
  and unmet obligation; a project-level gap alone is insufficient. The rule set
  is enumerated in the
  specification and covered by tests; "flag anything that is not a clean
  success" is not an acceptable rule.

- **REQ-079-2 — Dimension B must not leak into Dimension A.** A run that leaves
  no unresolved work is reported as having no unresolved work, even when the
  project carries `declared` or `refuted` declarations or T-078 contract gaps.
  Project states remain visible in Dimension B and never automatically change a
  normal run's Dimension A result. No combined score is introduced.

- **REQ-079-3 — Reporting observes; it does not gate.** The report changes no run
  outcome, does not block, fail, retry, admit, or reject anything, and is not an
  input to preflight or admission. It is a report and an observation.

- **REQ-079-4 — `refuted` survives aggregation.** Applying REQ-077-6, no rollup,
  count, percentage, or "known issues" bucket may absorb a `refuted` entry into a
  non-`refuted` category. Every `refuted` declaration is listed by ID.

- **REQ-079-5 — Deterministic, bounded, and DLP-safe.** The report contains only
  bounded identifiers, categories, counts, states, hashes, and durations. It must
  not contain requirement text, prompts, content read from an analyzed target
  repository, absolute paths, credentials, provider bodies, or unbounded cache
  keys.

- **REQ-079-6 — Expected implementation surface.** Expected production files are
  a focused `src/specflow/assurance/reporting.py` plus the minimum integration
  with `src/specflow/evaluation/metrics.py` and the T-077 ledger. Expected tests
  are `tests/test_assurance_reporting.py`, `tests/test_evaluation_multi_agent.py`,
  and the affected existing metrics tests. If the report would require a new
  metrics backend, endpoint, exporter, or dependency, stop and amend the
  specification.

## Decisions applied in revision 4

1. Keep the dimensions separate; do not introduce a combined number or score.
2. Report project `refuted` declarations individually in Dimension B, without
   converting them into run-local unresolved items.
3. Include an unfinished human decision in Dimension A only under the existing
   delivery/use obligation rule in REQ-079-1. Optional opinions do not qualify.

## Boundaries

The following are explicit non-goals for T-079:

- No health endpoint, monitoring backend, exporter, alert, dashboard,
  Prometheus, OpenTelemetry, or telemetry network call.
- No thresholds that change run behavior; no admission, preflight, or gating use.
- Do not redefine any existing counter's meaning, and do not relabel historical
  results.
- Do not add recovery, reconciliation, or compensation capability.
- Do not convert a `refuted` state into a generic issue count.
- Do not combine the two dimensions or add a composite score.

## Acceptance

- **AC-079-1:** Tests prove the two dimensions are reported separately and that a
  run with no unresolved work is not reported as unhealthy solely because the
  project carries `declared` or `refuted` declarations.
- **AC-079-2:** Tests prove each enumerated REQ-079-1 rule, and prove that an
  undefined business outcome or T-078 project gap does not silently become a
  Dimension A item. Business `REJECT`, permitted degradation, and missing
  optional opinions do not qualify by default; a contract-required pending
  human decision does qualify when tied to the actual run and unmet obligation.
- **AC-079-3:** Tests prove a `refuted` declaration is listed by ID and cannot be
  absorbed into any aggregate category.
- **AC-079-4:** Tests prove the report changes no run outcome and is not consumed
  by admission or preflight.
- **AC-079-5:** Tests prove report fields contain no requirement text, prompt,
  target-repository content, absolute path, credential, or provider data.
- **AC-079-6:** Existing metrics, evaluation, CLI/mock, and benchmark tests remain
  green.
- **AC-079-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-079-8:** `docs/reports/T-079-completion-report.md` records the rule set,
  the two-dimension report shape, the three decisions applied above, and known
  limits. One focused commit is created, then work stops for the
  milestone assurance review.
