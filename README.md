# SpecFlow Agent

SpecFlow Agent is a spec-driven development assistant for local Python/FastAPI
projects. Its MVP will safely scan a repository, build evidence-backed project
context, structure requirements, generate artifacts, review diffs, and enforce a
deterministic quality gate.

## Current milestone

T-001 is complete in scope: it supplies only a FastAPI liveness endpoint and the
engineering workflow. Database models, repository scanning, LLM integrations, and
workers are deliberately deferred to their task specifications.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup and run

```powershell
uv sync --all-groups
uv run uvicorn specflow.main:app --reload
```

Open `http://127.0.0.1:8000/health`. Expected response:

```json
{"status":"ok"}
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Verification

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

## Development process

Read `AGENTS.md`, the frozen baseline, and one active task document before making a
change. Each task must have tests, a completion report, and one focused Git commit.

