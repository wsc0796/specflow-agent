# T-002 — Project and run data models

## Goal

Establish the deterministic persistence foundation for a tracked local project.

## In scope

- SQLite persistence through SQLAlchemy;
- `projects`, `project_scans`, and `workflow_runs` tables;
- a repository/service boundary for Project operations;
- `POST /api/v1/projects` and `GET /api/v1/projects/{project_id}`;
- explicit HTTP errors for invalid input, duplicate repository paths, and missing
  projects;
- automated tests using an isolated SQLite database.

## Out of scope

- Any file-system scan, repository-path validation, traversal protection, or
  symbolic-link handling (T-003);
- technology recognition and context generation (T-004/T-005);
- Requirement persistence, Workflow transitions/resume/cancel, LLMs, prompts,
  workers, traces, and background execution.

## Data contract

`Project` stores id, name, repository_path, latest_scan_id, context_version,
status, created_at, and updated_at. `ProjectScan` stores its project relationship
plus the frozen scan-result fields. `WorkflowRun` stores its project relationship
and nullable `requirement_id` until the Requirement model exists in a later task.

`POST /api/v1/projects` accepts a non-empty `name` and a non-empty
`repository_path`; repository paths are unique as submitted. It returns 201.
`GET /api/v1/projects/{project_id}` returns 200 or 404. The API must not claim
that a supplied repository path exists or is safe; that belongs to T-003.

## Planned files

- `pyproject.toml`, `uv.lock`, `AGENTS.md`, `README.md`;
- `src/specflow/db/`, `src/specflow/projects/`, and `src/specflow/api/`;
- `src/specflow/main.py`;
- project API/repository tests and this completion report.

## Acceptance criteria

1. Schema creation produces only the three T-002 tables.
2. A valid project can be created and retrieved through the HTTP API.
3. Blank input returns 422; a duplicate repository path returns 409; an unknown
   project returns 404.
4. `ProjectScan` and `WorkflowRun` are persistable and linked to a Project, but
   no scanning or workflow behavior exists.
5. The complete pytest suite, Ruff check, and Ruff format check pass.

## Risks and test plan

- Use per-test SQLite files to verify a real database boundary, not in-memory
  connection quirks.
- Verify the uniqueness constraint both at the service layer and database layer.
- Verify deleting a Project is not exposed, so foreign-key lifecycle policy stays
  deferred to a later task.

