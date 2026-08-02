# Phase 6 Pilot — Protocol Report (mock smoke)

Status: **MOCK_HARNESS_VALIDATED / COMPARATIVE_PROTOCOL_NOT_FROZEN / REAL_EXECUTION_BLOCKED**

## What was validated

- Dataset: 5 authored pilot cases loaded from `evaluation/pilot/cases/*.json`
  (single-file, two-module, API+config+tests, security/reliability, vague
  requirement), all grounded in `benchmarks/fixtures/portfolio-python`.
- Harness: `specflow.evaluation.pilot.run_pilot_mock_smoke` executed
  **15 runs (5 cases x 3 pipelines)** in mock mode.
  - B1 single: deterministic mock single-agent (harness-only).
  - B2 legacy: legacy 3-worker mock pipeline (frozen A/B baseline).
  - B4 six-role: multi-agent runtime mock pipeline.
- A Final Sol rerun at `06b1cf2` completed all 15 mock paths. The single mock
  receives only case ID and requirement, and legacy candidates are derived from
  native generation/review/source artifacts rather than discarded.
- Rule scorer: deterministic (same input -> same scores; tested).
- Cost collector: reads Phase 3 `budget_snapshot`; mock runs correctly report
  0 provider attempts (mock is never a provider call).
- Blind pack generator: assigns IDs after shuffling and withholds the shuffle
  seed from the reviewer pack (tested).

## Honest limitations of this smoke

- The three mock pipelines do not have equal tools, evidence, budgets, or model
  behavior. The smoke validates harness mechanics, not comparative fairness,
  protocol stability, cost, or quality.
- Legacy and single mock runs have no Phase 3 budget snapshot; their manifests
  prove zero provider attempts, while token totals remain unavailable.
- `frozen-config.json` is still `DRAFT_PENDING_USER_APPROVAL` and is not an
  enforced execution protocol.
- No provider call, no real tokens, no semantic scoring, no human review.

## HARD_BLOCKER for real pilot execution

Same cost-cap/approval condition as Phase 4: no explicit
`SPECFLOW_LIVE_MAX_COST_USD` / model / provider approval exists, so the 15
live-provider runs are blocked. Harness, dataset, scorer, and blind pack are
ready; unblocking requires the Phase 4B-style approval.
