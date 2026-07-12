# M8 Pre-Flight Report

**Date:** 2026-07-12
**Branch:** feat/m8-production-hardening
**Base commit:** ab25b1f (M7 closeout)

## Baseline

| Check | Result |
|-------|--------|
| Tests | 607 passed, 2 skipped |
| Ruff check | All checks passed |
| Git status | Clean |
| Legacy Pipeline | Intact |
| Multi-Agent Pipeline | Intact |
| Live Provider | Case 2 validated (Redis cache, 2.75x speedup) |

## Current architecture

- `src/specflow/agents/` — Agent protocol, registry, 6 implementations, AgentRunner adapter
- `src/specflow/plan/` — Planner, Compiler, Enricher, Validator, Hash utils
- `src/specflow/coordinator/` — Coordinator, Scheduler, Revision, StateMachine
- `src/specflow/handoff/` — Handoff models, HandoffValidator
- `src/specflow/schema/` — SchemaRegistry, factory
- `src/specflow/fallback/` — FallbackManager (Retry, JSON Repair, Rule Baseline)
- `src/specflow/token_budget/` — TokenBudgetManager (char/4 estimation)
- `src/specflow/evaluation/` — RunMetrics, AgentMetrics, rubric
- `src/specflow/security/` — NOT YET EXIST (redaction in context.py only)
- `src/specflow/policy/` — NOT YET EXIST

## Existing engineering capabilities

- SchemaRegistry with freeze semantics
- Fallback with 3 levels
- Token budget with partition-based trimming
- AgentTraceSpan with stage timing
- FAILED manifest persistence
- Canonical JSON hash (structure + semantic + effective)
- HandoffValidator with payload hash checks
- Parallel execution with ThreadPoolExecutor
- RunMetrics + AgentMetrics collection

## Current gaps (T-040 to T-044)

| # | Gap | Impact |
|---|-----|--------|
| T-040 | No unified ExecutionPolicy; limits scattered across code | Run budget not enforceable |
| T-040 | Error classification uses raw exception class names | Provider 429 vs 401 not distinguished |
| T-041 | Schema validation failure → raw JSON pass-through | LLM output not contract-enforced |
| T-041 | AgentRunner returns success=true with schema_validated=false | Downstream agents receive unvalidated data |
| T-042 | FallbackManager not integrated with AgentRunner | Retry/repair not applied to multi-agent path |
| T-042 | No retry classification — all exceptions retried | Security errors retried, wasting budget |
| T-043 | Token estimation is char/4 only | Inaccurate for Chinese/code |
| T-043 | selected_file_count and referenced_file_count hardcoded to 0 | Metrics incomplete |
| T-044 | Redaction in context.py only; not full-pipeline | Errors, traces, handoffs not sanitized |
| T-044 | Repository evidence not marked as untrusted | Prompt injection surface |

## Files to modify (planned)

- `src/specflow/agents/adapter.py` — AgentRunner (T-041, T-042)
- `src/specflow/runner_multi.py` — Policy integration (T-040)
- `src/specflow/runner.py` — Policy integration (T-040)
- `src/specflow/handoff/validator.py` — Schema enforcement (T-041)

## Files NOT to modify

- `src/specflow/workflow/` — Legacy pipeline (unchanged)
- `src/specflow/workers/` — Legacy workers (unchanged)
- `src/specflow/executor/` — Legacy executor (unchanged)
- Target repository sky-takeout-python (read-only)

## Blocking issues

None. Baseline passes.
