# SpecFlow Agent

SpecFlow Agent is a spec-driven development assistant for local Python/FastAPI
projects. Its MVP will safely scan a repository, build evidence-backed project
context, structure requirements, generate artifacts, review diffs, and enforce a
deterministic quality gate.

## Current milestone

Milestone 2 is complete — the system can safely scan a repository, identify its
Python/FastAPI technology stack with concrete evidence, and generate a
deterministic, sanitized `PROJECT_CONTEXT.md` artifact. Current verification:
`74 passed, 1 skipped` (`uv run pytest -v`); rerun the command after changes.

Next: M3 — Agent Infrastructure (Prompt Registry, Context Builder, LLM Client).

## T-001 foundation boundary

T-001 included only the FastAPI application package, `GET /health`, pytest, Ruff,
and setup/development-rule documentation. It deliberately excluded persistence,
project APIs, scanning, technology detection, project-context generation, prompts,
LLMs, workers, and workflow logic; later tasks added those capabilities incrementally.

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

To register a project record (this does not scan or validate the path yet):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/projects `
  -ContentType 'application/json' `
  -Body '{"name":"Example API","repository_path":"C:\\projects\\example-api"}'
```

## Verification

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

## Development process

Read `AGENTS.md`, the frozen baseline, and one active task document before making a
change. Each task must have tests, a completion report, and one focused Git commit.
