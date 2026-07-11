# SpecFlow Agent

SpecFlow Agent is a spec-driven development assistant for local Python/FastAPI
projects. Its MVP will safely scan a repository, build evidence-backed project
context, structure requirements, generate artifacts, review diffs, and enforce a
deterministic quality gate.

## Current milestone

Milestone 2 is complete — the system can safely scan a repository, identify its
Python/FastAPI technology stack with concrete evidence, and generate a
deterministic, sanitized `PROJECT_CONTEXT.md` artifact.

M3 is in progress. T-006 adds a file-based Prompt Registry with versioned prompt
metadata, strict Jinja2 rendering, template-variable validation, and stable
prompt hashes. T-007 adds deterministic context assembly that combines sanitized
project context, prompt definitions, and user requirements into a `BuiltContext`
without calling an LLM. T-008 adds deterministic token budget control with
policy-based trimming and removed-section tracking. Next: T-009 — LLM Client.

## T-001 foundation boundary

T-001 included only the FastAPI application package, `GET /health`, pytest, Ruff,
and setup/development-rule documentation. It deliberately excluded persistence,
project APIs, scanning, technology detection, project-context generation, prompts,
LLMs, workers, and workflow logic; later tasks added those capabilities incrementally.

## Prompt Registry

Prompt assets live under `prompts/` and are managed by Git so behavior changes
can be reviewed as ordinary diffs. The current registry supports loading a
prompt by name and version, validating YAML metadata, checking template variables
against declared `required_variables`, rendering with Jinja2 `StrictUndefined`,
and producing a stable `prompt_hash`.

## Context Builder

The Context Builder combines a sanitized `ProjectContext`, a versioned
`PromptDefinition`, and a user requirement into a deterministic `BuiltContext`.
It tracks sources, carries prompt and project hashes, estimates token count, and
rejects empty or secret-like inputs. It does not scan repositories, call LLMs,
write databases, or modify workflow state.

## Token Budget

The Token Budget Manager accepts a `BuiltContext`, applies a `BudgetPolicy`,
estimates input size deterministically, trims low-priority sections when needed,
records `removed_sections`, and returns a stable `BudgetResult`. It does not
call LLMs, summarize content, use embeddings/RAG, or modify workflow state.

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
