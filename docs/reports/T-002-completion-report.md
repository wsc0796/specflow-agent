# T-002 completion report — Project and run data models

## Result

Implemented SQLite persistence for `Project`, `ProjectScan`, and `WorkflowRun`.
The Project API supports registration and lookup; scan and workflow behavior remain
intentionally absent.

## Modified files

- `src/specflow/db.py`: SQLAlchemy base, all three T-002 models, SQLite lifecycle.
- `src/specflow/projects.py`: Project repository, service, API schemas, and routes.
- `src/specflow/main.py`: app factory and schema initialization.
- `tests/test_projects.py`: HTTP contracts and direct persistence coverage.
- `pyproject.toml` / `uv.lock`: SQLAlchemy dependency and reproducible lockfile.
- `AGENTS.md` / `README.md`: current-stage boundaries and API usage.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Three-table schema | Test verifies exactly `projects`, `project_scans`, `workflow_runs`. |
| Project CRUD surface | `POST /api/v1/projects` returns 201; `GET /api/v1/projects/{id}` returns 200. |
| Invalid cases | Tests verify blank input 422, duplicate path 409, missing id 404. |
| Model links | Test persists a scan and workflow run linked to a project. |
| Quality checks | pytest: 4 passed; Ruff lint and format: passed. |

## Scope control and limitations

Repository paths are stored exactly as submitted. They are not checked for existence,
whitelisted roots, traversal, or symlink escapes until T-003. `ProjectScan` and
`WorkflowRun` are data-only records; no scan or workflow endpoints were introduced.

