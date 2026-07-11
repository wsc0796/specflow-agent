# T-001 — Initialize repository

## Goal

Create a runnable, testable FastAPI foundation for SpecFlow Agent.

## In scope

- `src/` Python package and FastAPI application;
- `GET /health` returning `{ "status": "ok" }`;
- pytest and Ruff configuration;
- setup, scope, and development-rule documentation.

## Out of scope

No persistence, project APIs, scanner, technology detection, context generation,
prompts, LLMs, workers, or workflow logic.

## Expected files

`pyproject.toml`, `src/specflow/main.py`, `tests/test_health.py`, `README.md`,
`AGENTS.md`, `docs/00-SPEC-BASELINE.md`, and this task's completion report.

## Acceptance criteria

1. `uv run uvicorn specflow.main:app --reload` can serve the application.
2. `GET /health` returns HTTP 200 and exactly `{ "status": "ok" }`.
3. `uv run pytest -v`, `uv run ruff check .`, and `uv run ruff format --check .` pass.
4. The README explains setup, verification, and the T-001 boundary.

## Risks and tests

The main risk is importing a `src/` package incorrectly during tests. The health
endpoint test must import the application as installed/configured by `pyproject.toml`.

