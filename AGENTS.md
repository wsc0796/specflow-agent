# SpecFlow Agent Development Rules

## Current phase

The project has completed all milestones through M7. M8 independent-review
remediation is complete and has passed local mock acceptance:
- M3: Agent Runtime Foundation
- M4: Agent Workflow
- M5: Tool Use & Repository Intelligence
- M6: Multi-Agent Orchestration (Live Provider validated)
- M7: Evaluation, Demo & Resume (portfolio-ready)

636 passing tests, 2 skipped. M8 production hardening remains limited to the
implemented policy, schema, fallback, evidence, and artifact boundaries; it
does not claim the deferred API-service or deployment work listed in M7.

All tasks T-001 through T-032 are completed. Implemented:
health endpoint, Project persistence API, safe scanning, deterministic technology
identification with evidence, sanitized PROJECT_CONTEXT.md generation, Prompt
Registry, Context Builder, Token Budget Manager, LLM Client abstraction, Trace
System, Fallback System, deterministic workflow state transitions,
deterministic Agent Executor step advancement, Worker Framework contracts,
Analyze/Generate/Review Workers with structured outputs and honest degraded
fallbacks, Tool Framework, Registry, and Executor contracts,
repository-root-bound read-only tools, OpenAI-compatible Provider,
bounded evidence collection pipeline, `specflow run` CLI with 10 structured
artifacts, deterministic real-repository evaluation layer with safe Live
Artifact import validation and 10-dimension human rubric,
**SchemaRegistry with freeze semantics, 6-agent fixed topology with parallel
execution, Coordinator with Planner→Compiler→Validator→Enricher pipeline,
deterministic structural plan + LLM semantic enrichment (M6-ADR-001),
structured AgentHandoff with schema validation, bounded Revision (max 1 round),
AgentTraceSpan with stage timing, and A/B evaluation framework (10 dimensions).**

The legacy `--mode legacy` pipeline (Analyze→Generate→Review) is preserved
unchanged as the T-029 A/B baseline. Multi-agent mode is accessed via
`--mode multi-agent`.

The next milestone is the separately scoped M8 follow-up work, if authorized.
Future task IDs are not permission to implement future features.

## Mandatory workflow

1. Read `docs/00-SPEC-BASELINE.md`, this file, and the active task spec before editing.
2. Implement one task at a time; keep changes small and testable.
3. Do not add dependencies unless the active task needs them.
4. Before completion, run `uv run pytest -v`, `uv run ruff check .`, and
   `uv run ruff format --check .`.
5. Write a completion report in `docs/reports/` and make one focused Git commit.
6. After every completed task, update its completion report. After every completed
   milestone, add a dated milestone record under `docs/records/` covering delivered
   capabilities, validation evidence, commit IDs, known limits, and the next gate.
7. After the milestone quality gate passes, push its reviewed commits and milestone
   record to the configured GitHub `origin`. Never push without a configured remote
   or after a failed quality gate; report that configuration blocker instead.

## Architecture constraints

- Use the `src/` layout.
- M4 work must proceed one task spec at a time. Do not introduce Worker
  orchestration without an explicit active Worker/Executor task spec.
- Do not add prompts, workers, LLM calls, workflow orchestration, Redis,
  LangGraph, vector stores, MCP, Java support, or automatic code changes before
  their explicitly assigned task.
- Keep HTTP-boundary code separate from future business and persistence layers.
- Never weaken tests merely to make them pass.

## Commands

```powershell
uv sync --all-groups
uv run uvicorn specflow.main:app --reload
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```
