# T-064 Completion Report — Secure-Default HTTP Boundary

## Result

**PASS.** The HTTP service now fails closed when no usable API key is configured,
and `/health` is the only unauthenticated route.

## Delivered

- API lifespan startup validates `SPECFLOW_API_KEY` before database schema setup
  and rejects missing, blank, padded, or non-ASCII values with a safe
  configuration error.
- Project and Run routers retain explicit authentication dependencies. A global
  deny-by-default middleware also covers generated `/docs`, `/redoc`, and
  `/openapi.json` routes and prevents future unprotected HTTP routes.
- Both `X-API-Key` and `Authorization: Bearer` remain supported with constant-time
  ASCII comparison. The OpenAPI document declares both security schemes and
  marks `/health` public explicitly.
- Tests now inject credentials explicitly rather than relying on the previous
  fail-open default. Regression coverage verifies startup refusal, public
  health, protected documentation, clean 401 responses, and both accepted
  credential transports.
- README, `.env.example`, changelog, current development status, API request
  examples, and installed-wheel smoke reflect the required-key contract.

## Validation

| Gate | Result |
| --- | --- |
| Focused HTTP/API tests | 42 passed, 1 skipped, 1 warning |
| `uv run pytest -v` | 756 passed, 3 skipped, 3 warnings |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed |
| `python scripts/check_secrets.py` | passed |
| `uv build` | passed; sdist and wheel produced |
| `python scripts/smoke_installed_wheel.py` | PASS in clean venv |
| `git diff --check` | passed |

## Known Limits

- A single shared API key authenticates the client but does not identify a user
  or authorize access to individual resources. Reviewer labels remain
  self-declared metadata.
- Documentation routes are protected HTTP resources. Opening Swagger UI in a
  normal browser requires a client or trusted proxy capable of attaching the
  API-key or bearer header to the documentation and OpenAPI requests.
- The service remains single-process with process-local quotas. Shared limiting,
  multi-user ownership, TLS termination, and proxy policy remain deployment
  concerns outside this task.
