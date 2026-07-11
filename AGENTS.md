# SpecFlow Agent Development Rules

## Current phase

The project is in Milestone 0, task T-001. The only implemented behavior is the
FastAPI health endpoint. Future task IDs are not permission to implement future
features.

## Mandatory workflow

1. Read `docs/00-SPEC-BASELINE.md`, this file, and the active task spec before editing.
2. Implement one task at a time; keep changes small and testable.
3. Do not add dependencies unless the active task needs them.
4. Before completion, run `uv run pytest -v`, `uv run ruff check .`, and
   `uv run ruff format --check .`.
5. Write a completion report in `docs/reports/` and make one focused Git commit.

## Architecture constraints

- Use the `src/` layout.
- Do not add database models, repositories, scanners, prompts, workers, LLM calls,
  workflow orchestration, Redis, LangGraph, vector stores, MCP, Java support, or
  automatic code changes before their explicitly assigned task.
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

