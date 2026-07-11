# T-001 completion report — Initialize repository

## Result

Completed the Milestone 0 runnable foundation. The application can start and
`GET /health` returns the required liveness response.

## Files created

- `pyproject.toml`: package metadata, Python 3.12 requirement, runtime/dev
  dependencies, pytest, and Ruff configuration.
- `src/specflow/__init__.py` and `src/specflow/main.py`: `src`-layout application
  package and the FastAPI `GET /health` endpoint.
- `tests/test_health.py`: endpoint contract test.
- `README.md`, `AGENTS.md`, `.env.example`, and `.gitignore`: setup and engineering
  rules without future-stage configuration.
- `docs/00-SPEC-BASELINE.md` and `docs/tasks/T-001-initialize-repository.md`:
  frozen-scope reference and task contract.
- `uv.lock`: reproducible resolved dependency set.

## Acceptance evidence

| Criterion | Evidence |
| --- | --- |
| Application starts | Started Uvicorn on `127.0.0.1:8765` and queried it successfully. |
| Health response | `{"status":"ok"}` |
| Test suite | `uv run pytest -v`: 1 passed |
| Lint | `uv run ruff check .`: passed |
| Formatting | `uv run ruff format --check .`: passed |

## Manual verification

The server was launched using the project virtual environment, queried with an
HTTP request, then stopped cleanly. This verifies a real ASGI/Uvicorn path rather
than only an in-process test client.

## Difference from plan

Ruff initially found import ordering and formatting differences. They were fixed
mechanically with Ruff before the final quality-gate run. No behavior or scope was
added beyond T-001.

## Known limitations

Pytest emits a third-party FastAPI/Starlette `TestClient` deprecation warning about
the installed HTTPX compatibility path. It does not affect the endpoint contract;
changing test transport is deferred because it is not needed for T-001.

## Next prerequisite

T-002 may add only the `Project`, `ProjectScan`, and `WorkflowRun` data path, with
SQLite, repository/service boundaries, CRUD API, tests, and a separate task spec.

