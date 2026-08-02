# Phase 7 Formal Evaluation Limitations

- Dataset: 30 authored tasks over one small fixture repository; coverage of
  general software repositories is not claimed.
- Dry-run: harness validated on 6 mock runs (2 tasks x 3 pipelines).
- The 90 live-provider runs are HARD_BLOCKED: no explicit cost cap
  (`SPECFLOW_EVAL_MAX_COST_USD`) or provider/model approval exists.
- No human reviewers; no automated judge configured yet; no results exist and
  none will be fabricated.
- Any future report must bind claims to the frozen commit, dataset, model,
  budgets, and metrics.
