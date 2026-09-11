# T-079 — Run-Local and Project-Level Assurance Reporting

**Status:** DRAFT FOR FREEZE — REVISION 2. Implementation requires T-078 and
T-080 closed with readable completion reports at named commits, plus a new
focused session.

**Revision note:** revision 1 aggregated run-local unresolved items and
project-level unverified declarations into one health conclusion. Those are
different subjects: *this run left work needing attention* and *this project has
not verified a behavior* are not the same statement, and a healthy run must not
be reported as unhealthy merely because the project carries an unverified
declaration.

## Goal

Report two separate dimensions — what a finished run leaves unresolved, and which
declarations the project has not verified or has refuted — and combine them only
through an explicit, reviewable rule rather than an implicit one.

## Two dimensions, reported separately

- **Dimension A — Run-local unresolved items.** Work this run left behind. Sourced
  from what the runtime already records or can derive deterministically:
  degraded outcomes, `fallback_used`, exhausted revision budget, failed or
  unvalidated schema checks, pending human review decisions, cache `invalid` or
  `write_failed` states, and the `undetermined` conclusions from T-078.

- **Dimension B — Project-level declaration states.** The ledger state of each
  declaration: `verified`, `declared`, `refuted`, `not_applicable`. Applying
  REQ-077-6, every `refuted` entry is reported individually and is never merged
  into a count or bucket that hides it.

The two dimensions are reported side by side. No summary field may combine them
without a stated rule.

## Requirements

- **REQ-079-1 — Business outcomes are not unresolved items by default.** A
  business `REJECT`, a business-rule-permitted degradation, or a documented
  fallback does not become a Dimension A item unless an explicit rule in this
  specification defines it as one. The rule set is enumerated in the
  specification and covered by tests; "flag anything that is not a clean
  success" is not an acceptable rule.

- **REQ-079-2 — Dimension B must not leak into Dimension A.** A run that leaves
  no unresolved work is reported as having no unresolved work, even when the
  project carries `declared` or `refuted` declarations. A combined summary is
  permitted only through an explicit rule that names both inputs.

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

## Open decisions for the reviewer

1. Is there any legitimate case where a Dimension A item and a Dimension B state
   should be combined into one number, and if so what rule?
2. Should a `refuted` declaration appear in a run-level report at all, or only in
   the project-level section?
3. Is a pending human review decision always a Dimension A item, or only when the
   decision is required before the run's work can be considered usable?

## Boundaries

The following are explicit non-goals for T-079:

- No health endpoint, monitoring backend, exporter, alert, dashboard,
  Prometheus, OpenTelemetry, or telemetry network call.
- No thresholds that change run behavior; no admission, preflight, or gating use.
- Do not redefine any existing counter's meaning, and do not relabel historical
  results.
- Do not add recovery, reconciliation, or compensation capability.
- Do not convert a `refuted` state into a generic issue count.
- Do not combine the two dimensions without a stated rule.

## Acceptance

- **AC-079-1:** Tests prove the two dimensions are reported separately and that a
  run with no unresolved work is not reported as unhealthy solely because the
  project carries `declared` or `refuted` declarations.
- **AC-079-2:** Tests prove each enumerated REQ-079-1 rule, and prove that an
  undefined business outcome does not silently become a Dimension A item.
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
  the two-dimension report shape, the decisions taken on the three open decisions
  above, and known limits. One focused commit is created, then work stops for the
  milestone assurance review.
