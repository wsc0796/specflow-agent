# T-064 — Secure-Default HTTP Boundary

## Goal

Replace the opt-in API-key model with a fail-closed HTTP boundary suitable for
the service's documented local and network deployment modes.

## Allowed scope

- Require a non-empty ASCII `SPECFLOW_API_KEY` before the API lifespan starts.
- Authenticate every HTTP route except the liveness-only `/health` route,
  including generated documentation and OpenAPI routes.
- Declare both supported credential forms in the OpenAPI security scheme.
- Update focused HTTP tests, installed-wheel smoke, `.env.example`, and README.

## Non-goals

- User identity, authorization, reviewer attribution, or multi-tenant access.
- Reverse-proxy trust, distributed rate limiting, workers, queues, or deployment
  automation.
- Any change to CLI execution or the agent workflow.

## Acceptance

1. Starting the API without a non-empty ASCII key fails before database setup.
2. Valid `X-API-Key` and `Authorization: Bearer` credentials grant access to
   API and documentation routes; invalid or absent credentials receive 401.
3. `/health` stays available without credentials and is the only public route.
4. OpenAPI exposes the supported API-key and bearer security mechanisms.
5. Focused tests, full pytest, Ruff, secret scan, build, installed-wheel smoke,
   `git diff --check`, and a completion report record their results.
