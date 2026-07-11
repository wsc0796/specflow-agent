# SpecFlow Agent Development Rules

## Current phase

The project has completed Milestone 3 (Agent Runtime Foundation) and has started
Milestone 4 (Agent Workflow) with T-012 Workflow State Machine. Implemented:
health endpoint, Project persistence API, safe scanning, deterministic technology
identification with evidence, sanitized PROJECT_CONTEXT.md generation, Prompt
Registry, Context Builder, Token Budget Manager, LLM Client abstraction, Trace
System, Fallback System, and deterministic workflow state transitions.
The next task is T-013 Agent Executor.
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
