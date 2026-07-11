# T-004 — Technology stack detector

## Goal

Identify the supported Python/FastAPI stack from repository metadata using only
deterministic rules and record concrete evidence for every conclusion.

## Scope

- Parse `pyproject.toml` and `requirements.txt` when present.
- Detect Python, FastAPI, Pydantic, SQLAlchemy, pytest, Ruff, SQLite, and candidate
  application entry files.
- Return typed structured data and evidence entries containing file and match text.

## Out of scope

No LLM, semantic inference, package installation, scanning API, database write, or
`PROJECT_CONTEXT.md` generation. Unknown facts remain unknown.

## Acceptance tests

1. A fixture `pyproject.toml` with supported dependencies yields evidence-backed
   Python/FastAPI/Pydantic/SQLAlchemy/pytest/Ruff results.
2. `requirements.txt` is recognized as a dependency source.
3. SQLite and application entry candidates are detected from explicit file content.
4. Missing files return an unknown/minimal result rather than guessed technology.

