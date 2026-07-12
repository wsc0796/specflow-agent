# M7 Evaluation, Demo & Resume

**Date:** 2026-07-12
**Status:** CLOSED
**Previous milestone:** M6 Multi-Agent Orchestration

## Delivered capabilities

M7 transforms the M6 implementation into a portfolio-ready project with:

1. **Unified RunMetrics + AgentMetrics (T-033):** Multi-agent pipeline produces `metrics.json`
   with per-agent token usage, duration, schema validation status, fallback/degraded
   tracking, parallel speedup calculation, and 7-dimension aggregate statistics.
2. **15-Question Interview Bank (T-036):** Each question follows a 5-section format:
   30-second answer → project implementation → code location → test evidence → known limits.
   Covers architecture (4), stability (5), tools & security (3), and evaluation & cost (3).
3. **Resume Bullets + 4 STAR Stories (T-037):** Three resume versions (general, MiniMax-customized,
   复保科技-customized) plus four interview stories: Legacy→Multi-Agent upgrade, Chinese hash bug,
   bounded revision, and schema validation debugging.
4. **Demo Script (T-038):** 4-minute terminal demo covering architecture, live execution,
   artifact walkthrough, and A/B comparison. Includes checklist and pre-recorded fallback option.
5. **Live A/B Protocol (T-034):** 3-case experiment design (order timeout, Redis cache,
   idempotent order) with fair-comparison constraints, command templates, and data recording sheet.
6. **A/B Report Template (T-035):** Structured template with auto-metrics tables, human scoring
   rubrics, summary aggregation, and resume-claim extraction.

## Quality gates

```text
uv run pytest -v:             607 passed, 2 skipped
uv run ruff check .:          All checks passed
uv run ruff format --check .: All files formatted
git diff --check:             clean
```

## Commit IDs

- `17ab914` feat(metrics): add RunMetrics and AgentMetrics collection to multi-agent pipeline
- `7d85338` docs(interview): add 15-question project-specific interview bank
- `52ced18` docs(resume): add 3 resume versions and 4 STAR stories

## Known limits

- Live Provider A/B data for 3 cases pending (user holds API key; protocol ready)
- A/B report template has placeholder values — needs T-034 data to fill
- Demo script references live execution; pre-recorded fallback available
- Agent output schema validation still non-blocking (M8 fix)

## M7 closeout decision

**APPROVED.** All M7 documentation deliverables are complete. T-034 (Live A/B execution)
is delegated to the user who holds the API key. The project is now portfolio-ready
with comprehensive interview preparation materials.

The next milestone is M8 (Production Hardening): strict Schema validation,
unified fallback, token/cost governance, and full-pipeline redaction.

## M8 preview

| Task | Scope | Priority |
|------|-------|----------|
| T-040 | ExecutionPolicy, error classification, run state contracts | P0 |
| T-041 | Strict Role Payload Schema, remove raw pass-through | P0 |
| T-042 | Unified Fallback, backoff retry, role-level degradation | P0 |
| T-043 | Layered Token/Cost Budget, real usage, caching | P0 |
| T-044 | Full-pipeline redaction, Prompt Injection protection | P0 |
| T-045 | RunStore, idempotency, checkpoint, recovery | P1 |
| T-046 | API service, auth, rate limiting, Docker | P1 |
| T-047 | Golden dataset, regression eval, security tests | P1 |
