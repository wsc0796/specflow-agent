# Phase 6 Pilot — Protocol Report (mock smoke)

Status: **HARNESS_VALIDATED (mock smoke) / REAL_EXECUTION_BLOCKED**

## What was validated

- Dataset: 5 frozen pilot cases loaded from `evaluation/pilot/cases/*.json`
  (single-file, two-module, API+config+tests, security/reliability, vague
  requirement), all grounded in `benchmarks/fixtures/portfolio-python`.
- Harness: `specflow.evaluation.pilot.run_pilot_mock_smoke` executed
  **15 runs (5 cases x 3 pipelines)** in mock mode.
  - B1 single: deterministic mock single-agent (harness-only).
  - B2 legacy: legacy 3-worker mock pipeline (frozen A/B baseline).
  - B4 six-role: multi-agent runtime mock pipeline.
- All 15 runs completed with `run_success=True` and per-run artifacts.
- Rule scorer: deterministic (same input -> same scores; tested).
- Cost collector: reads Phase 3 `budget_snapshot`; mock runs correctly report
  0 provider attempts (mock is never a provider call).
- Blind pack generator: hides pipeline identity behind anonymous IDs (tested).

## Honest limitations of this smoke

- Mock outputs are generic and score low on evidence-based metrics; the smoke
  validates protocol stability, not quality.
- Legacy pipeline has no Phase 3 budget snapshot (frozen baseline); its cost
  fields are recorded as `missing`/empty.
- No provider call, no real tokens, no semantic scoring, no human review.

## HARD_BLOCKER for real pilot execution

Same cost-cap/approval condition as Phase 4: no explicit
`SPECFLOW_LIVE_MAX_COST_USD` / model / provider approval exists, so the 15
live-provider runs are blocked. Harness, dataset, scorer, and blind pack are
ready; unblocking requires the Phase 4B-style approval.
