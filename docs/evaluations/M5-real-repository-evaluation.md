# M5 Real Repository Evaluation

## Scope

T-023 evaluates the existing `sky-takeout-python` repository with deterministic
Mock contract checks and a validated Live Provider artifact import. Mock
output does not demonstrate Live Provider quality.

## Grounded cases

- `dish_cache_consistency`: grounded in Dish route/service/model; Redis remains
  proposed because the target README explicitly defers it.
- `category_dish_cache_invalidation`: grounded in Category and Dish service
  boundaries.
- `login_failure_rate_limit`: grounded in Employee login/service/JWT modules;
  rate limiting is proposed, not existing behavior.

## Mock contract results

See `evaluation/results/mock/summary.json`. All 3 Mock cases passed pipeline
contracts: 10 artifacts, Worker traces, hash lineage, read-only tool calls,
source-path containment, and secret scanning.

## Live Provider validation

**Status:** COMPLETED (2026-07-12)

| Field | Value |
|-------|-------|
| Provider | openai-compatible (DeepSeek API) |
| Model | deepseek-v4-flash |
| Run ID | run-e5b97497dfd5 |
| Requirement | 为订单增加超时自动取消功能 |
| CLI exit code | 4 (degraded — all Workers executed, Review REJECT) |
| 10 artifacts | All present and valid |
| 3 Worker traces | Analyze (7686ms), Generate (9380ms), Review (10359ms) |
| Tool calls | 3 (list_files + 2× search_code, 43 files discovered) |
| Total tokens | ~4,077 |
| Security | Clean — no keys, tokens, or external paths |
| Repository integrity | sky-takeout-python unmodified |

### Exit code 4 root cause

The CLI runner builds a minimal `ProjectContext` (empty frameworks/ORM/database)
rather than using the full scanner + technology detector. With 0 evidence
excerpts (Chinese keywords don't match English code), the Analyze Worker fell
back to `rule_baseline`. The degraded chain propagated through Generate → Review,
which correctly REJECTed with MISSING_CONTEXT.

This is a pipeline integration gap, not an AI/Provider failure. The Review
Worker's diagnosis was correct.

## Manual rubric (0 / 1 / 2)

**Case:** 为订单增加超时自动取消功能 on sky-takeout-python (Live, degraded)

| # | Dimension | Score | Key evidence |
|---|-----------|-------|-------------|
| 1 | repository_grounding | 1 | 43 files listed, 0 matched (CN keyword→EN code gap) |
| 2 | affected_component_relevance | 1 | Order + scheduler modules identified, unverified |
| 3 | requirement_coverage | 1 | Timeout mechanism proposed; payment/notification missing |
| 4 | risk_coverage | 2 | Multi-instance, performance, timing all covered |
| 5 | implementation_feasibility | 0 | Tech stack unknown → feasibility unassessable |
| 6 | test_completeness | 1 | Unit+boundary+config+integration; concurrency missing |
| 7 | review_usefulness | 2 | Correctly identified MISSING_CONTEXT and provided specific actions |
| 8 | evidence_integrity | 1 | No file citations (degraded analysis) |
| 9 | artifact_completeness | 2 | All 10 present, valid, hash lineage complete |
| 10 | security | 2 | Zero secrets, read-only tools, repo unmodified |
| **Total** | | **13/20** | Pipeline integration gap dominates; review quality is strong |

**Note:** Scores 1, 2, 5, 8 will improve substantially when the scanner is wired
into the CLI runner (M6).

## User-run Live command (reference)

```powershell
Set-Location "D:\Documents\暑假计划\specflow-agent"
$env:SPECFLOW_LLM_BASE_URL = "<openai-compatible-base-url>"
$env:SPECFLOW_LLM_API_KEY = Read-Host "API key"
$env:SPECFLOW_LLM_MODEL = "<model>"
uv run specflow run `
    --repo "C:\Users\50469\github-projects\sky-takeout-python" `
    --requirement "为订单增加超时自动取消功能" `
    --provider openai-compatible `
    --max-files 8 `
    --output ".\artifacts-live"
Remove-Item Env:SPECFLOW_LLM_API_KEY
```

## M5 closeout

**APPROVED (2026-07-12).** See `docs/records/M5-product-vertical-slice.md`.
