# T-023 Completion Report — Real Repository Cases and Evaluation

## Status

**COMPLETED.** Phase A (Mock contract), Phase B (Live Provider run), and Phase C (Live validation + human rubric + M5 closeout) are all done.

## Phase A — Mock Contract Evaluation

- 3 repository-grounded case definitions in `evaluation/cases/`
- Mock contract runner validates 10-artifact completeness, hash lineage, Worker traces, tool calls, source containment, and secret absence
- All 3 Mock cases passed
- Tests: 10 evaluation tests pass

## Phase B — Live Provider Run

**Executed by user in an independent PowerShell session. No API key was read by SpecFlow tooling.**

| Field | Value |
|-------|-------|
| Provider | openai-compatible (DeepSeek API) |
| Model | deepseek-v4-flash |
| Repository | sky-takeout-python |
| Requirement | 为订单增加超时自动取消功能 |
| Run ID | run-e5b97497dfd5 |
| Exit code | 4 (degraded) |
| 10 artifacts | All generated |
| 3 Worker traces | All executed |

## Phase C — Live Artifact Validation

### Artifact completeness

All 10 required artifacts present and valid JSON (where applicable):

| Artifact | Size | Status |
|----------|------|--------|
| manifest.json | 972 B | Valid, lineage complete |
| analysis.json | 629 B | Valid (degraded) |
| generation.json | 1694 B | Valid (degraded) |
| review.json | 2458 B | Valid, REJECT |
| sources.json | 1635 B | Valid, 43 files discovered |
| tool-calls.json | 926 B | Valid, 3 read-only tools |
| trace.json | 1954 B | Valid, 3 Worker traces |
| technical-spec.md | 614 B | Present |
| test-plan.md | 668 B | Present |
| run-summary.md | 813 B | Present |

### Exit code 4 root cause analysis

```
AnalyzeWorker → ValueError ("AnalysisOutput sequence fields must not be empty")
              → fallback_level: rule_baseline
              → degraded analysis output
              ↓
GenerateWorker → consumed degraded analysis
              → produced degraded (but structurally useful) generation
              ↓
ReviewWorker  → correctly identified MISSING_CONTEXT
              → issued REJECT with requires_revision=true
              → exit code 4 (degraded + requires_review)
```

**Primary cause:** The CLI runner builds a minimal `ProjectContext` (empty frameworks/ORM/database) rather than using the full scanner + technology detector. Combined with Chinese keyword-to-code matching yielding 0 excerpts, the ContextBuilder produced an under-specified prompt. This is a pipeline integration gap (scanner not wired into runner), not an AI/Provider failure.

**The Review Worker was correct:** it identified that without project technology stack and database schema information, the generated plan cannot be validated.

### Worker trace summary

| Worker | Duration | Tokens (in/out) | Status | Fallback |
|--------|----------|-----------------|--------|----------|
| analyze | 7686ms | 292/568 | degraded | rule_baseline |
| generate | 9380ms | 484/901 | degraded | none |
| review | 10359ms | 918/914 | degraded | none |

**Total:** ~27.4s wall clock, ~4,077 tokens

### Tool call verification

3 read-only tool calls, all successful:

1. `list_files` — 43 files discovered in sky-takeout-python
2. `search_code` — searched Python files for Chinese keywords (0 matches — expected for CN→EN code search)
3. `search_code` — second keyword fragment

All calls are read-only (`list_files`, `search_code`). No writes, shells, or Git operations.

### Source path verification

- 43 files discovered; 0 matched (Chinese keywords on English code)
- All paths are repository-relative
- No external paths, traversals, or sensitive filenames
- All referenced paths exist in sky-takeout-python

### Security scan

- **No API keys, Bearer tokens, Authorization headers, access tokens, or credentials found in any artifact.**
- No environment variables were read by the SpecFlow tooling.
- sky-takeout-python workspace: clean (`git status --short` returns nothing).
- specflow-agent workspace: clean.

### Old error artifact

`artifacts-live\run-e5b97497dfd5-error.json` (timestamp 10:46:59) is from a prior failed attempt with an empty API key. It does not belong to the successful run at 10:59:31. Same-input `run_id` reuse can cause audit ambiguity — logged as a known limitation in the M5 record.

## Human rubric scores

**Case:** 为订单增加超时自动取消功能 on sky-takeout-python (Live Provider, degraded analysis)

| # | Dimension | Score | Evidence |
|---|-----------|-------|----------|
| 1 | repository_grounding | **1** | `list_files` found 43 files, but 0 matches → no file-level evidence in analysis. Generation proposes plausible components ("定时任务模块", "订单模块") without referencing actual files. |
| 2 | affected_component_relevance | **1** | Generation identifies order module and scheduler module — relevant domains — but cannot verify against actual repository structure. |
| 3 | requirement_coverage | **1** | Requirement is partially covered: timeout mechanism proposed, cancellation logic described. Missing: payment integration, user notification, retry on failure. |
| 4 | risk_coverage | **2** | Risks correctly identified: multi-instance duplication, DB scan performance, timing precision. Review surfaces additional risks: distributed locking, pagination. |
| 5 | implementation_feasibility | **0** | Generation proposes APScheduler/cron with ORDER_TIMEOUT_MINUTES config, but Review correctly flags that project tech stack is unknown → feasibility cannot be assessed. |
| 6 | test_completeness | **1** | Test plan covers unit, boundary, config, and integration tests. Missing: concurrency test, degraded/fallback test, large-dataset performance test. |
| 7 | review_usefulness | **2** | Review correctly identifies MISSING_CONTEXT, UNSUPPORTED_DEPENDENCY, MISSING_DATABASE_SCHEMA. Provides actionable suggestions (provide tech stack, check existing scheduler, share schema). |
| 8 | evidence_integrity | **1** | No file-level evidence to support claims (degraded analysis). Generation identifies "cron context" but cannot cite actual files. |
| 9 | artifact_completeness | **2** | All 10 artifacts present, valid, and properly linked via hash lineage. |
| 10 | security | **2** | Zero secrets in any artifact. Repository unmodified. Read-only tools only. |

**Total: 13/20** (automated checks: 3 dimensions scored 2; human review: explanatory notes above)

This score reflects the pipeline integration gap, not AI capability. When the scanner is wired into the runner, scores in dimensions 1, 2, 5, 8 will improve substantially.

## Quality gates

```text
uv run pytest -v:             404 passed, 2 skipped
uv run ruff check .:          All checks passed
uv run ruff format --check .: 110 files already formatted
git diff --check:             clean
git status --short:           clean
```

## M5 closeout

**APPROVED.** See `docs/records/M5-product-vertical-slice.md` for full details.

## Known limitations carried forward

- CLI runner uses minimal ProjectContext (scanner integration → M6)
- Chinese keyword extraction on English code repos yields 0 matches
- `model` reports "unknown" in manifest when `--model` not explicitly passed
- Same-input `run_id` reuse leaves stale error artifacts
