# M5 Real Repository Evaluation

## Scope

T-023 evaluates the existing `sky-takeout-python` repository with deterministic
Mock contract checks and prepares a separate Live Artifact import path. Mock
output does not demonstrate Live Provider quality.

## Grounded cases

- `dish_cache_consistency`: grounded in Dish route/service/model; Redis remains
  proposed because the target README explicitly defers it.
- `category_dish_cache_invalidation`: grounded in Category and Dish service
  boundaries.
- `login_failure_rate_limit`: grounded in Employee login/service/JWT modules;
  rate limiting is proposed, not existing behavior.

## Mock contract results

See `evaluation/results/mock/summary.json`. It proves only pipeline contracts:
ten artifacts, Worker traces, hash lineage, read-only tool calls, source-path
containment, and secret scanning.

Current result: all three Mock contract runs passed. This is not a Live Provider
quality score and does not satisfy the M5 closeout gate.

## Live validation status

`blocked_live_validation`. T-023 phase A did not make a Provider request or
read an environment variable or `.env` file.

## Manual rubric (0 / 1 / 2)

| Dimension | Score | Human evidence |
|---|---:|---|
| repository_grounding | | |
| affected_component_relevance | | |
| requirement_coverage | | |
| risk_coverage | | |
| implementation_feasibility | | |
| test_completeness | | |
| review_usefulness | | |
| evidence_integrity | | |
| artifact_completeness | | |
| security | | |

## User-run Live command

Run only in an independent PowerShell. Do not put a key in this repo or this
Codex session:

```powershell
Set-Location "D:\Documents\暑假计划\specflow-agent"
$env:SPECFLOW_LLM_BASE_URL = "<openai-compatible-base-url>"
$env:SPECFLOW_LLM_API_KEY = Read-Host "API key"
$env:SPECFLOW_LLM_MODEL = "<model>"
uv run specflow run --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为订单增加超时自动取消功能" --provider openai-compatible --max-files 8 --output ".\artifacts-live"
Remove-Item Env:SPECFLOW_LLM_API_KEY
```

Then provide only the existing `artifacts-live/<run_id>` directory for import.
The importer will not call the provider or read your environment.
