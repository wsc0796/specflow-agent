# T-065 Completion Report — Response and Observability Boundary

## Result

**PASS.** Project HTTP responses no longer disclose local repository paths, and
legacy error-artifact write failures are visible in structured application logs.

## Delivered

- Replaced `ProjectRead.repository_path` with `repository_alias`, derived from
  the project display name. The persisted path and execution-time allowlist
  validation remain unchanged.
- Added a single public response conversion helper so create/get paths cannot
  accidentally serialize the ORM's local path field.
- Changed legacy `_write_error_artifact` to log the safe run id and exception
  type when persistence fails, while preserving the original best-effort
  behavior and runner exit code.
- Added regression tests for response shaping and observable write failures.
  README and current project status now describe the response boundary.

## Validation

| Gate | Result |
| --- | --- |
| Focused project/runner tests | 30 passed, 1 skipped, 1 warning |
| `uv run pytest -v` | 757 passed, 3 skipped, 3 warnings |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed |
| `python scripts/check_secrets.py` | passed |
| `uv build` | passed; sdist and wheel produced |
| `python scripts/smoke_installed_wheel.py` | PASS in clean venv |
| `git diff --check` | passed |

## Known Limits

- The API still has no user identity or object-level authorization; an alias is
  display metadata, not an ownership boundary.
- Error logs remain process-local. Central log retention, alerting, and audit
  identity are outside this task.
