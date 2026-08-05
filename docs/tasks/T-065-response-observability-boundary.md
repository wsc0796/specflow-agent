# T-065 — Response and Observability Boundary

## Goal

Remove local filesystem topology from the Project API response and make legacy
error-artifact write failures observable without changing the runner's safe exit
contracts.

## Allowed scope

- Replace the public `ProjectRead.repository_path` field with a non-sensitive
  `repository_alias` derived from the project name.
- Log `_write_error_artifact` failures with the run id and exception type while
  continuing to return the original runner exit code.
- Add focused tests and update current API documentation.

## Non-goals

- Changing the persisted repository path, path allowlist, or execution boundary.
- Exposing relative paths, filesystem metadata, stack traces, or provider errors
  in HTTP responses.
- Building centralized log shipping, audit identity, or distributed tracing.

## Acceptance

1. Project create/get responses contain no `repository_path` or absolute local
   path and expose a stable `repository_alias` instead.
2. Legacy error-artifact write failures emit an error log containing the safe
   run id and exception type, without raising a second exception.
3. Existing run and repository path boundary behavior remains unchanged.
4. Focused tests, full pytest, Ruff, secret scan, build, installed-wheel smoke,
   `git diff --check`, and a completion report record their results.
