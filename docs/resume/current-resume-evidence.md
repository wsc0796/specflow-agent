# SpecFlow Agent — Current Resume Evidence

> Current evidence baseline: v1.1.0 unreleased main candidate, checked on
> 2026-08-06. The latest published release remains `v1.0.1` at `a4fc16c`.

## Verifiable facts

- Controlled six-agent repository-analysis workflow with deterministic topology,
  schema-validated handoffs, bounded revision, read-only evidence collection,
  RuntimeGuard limits, and auditable artifacts.
- Reproducible 12-case mock benchmark: 12/12 passed with a committed normalized
  artifact-contract baseline. This is contract evidence, not live-model quality
  or cost evidence.
- T-057 adds a mock-only FastAPI/SQLite Run API lifecycle slice and safely marks
  interrupted persisted runs as `failed_runtime` with `INTERRUPTED` on the next
  single-process startup. T-061 adds an append-only human review-decision record
  to completed Run packages. It is not a queue, retry, resume, or deployment claim.
- T-062 through T-065 additionally enforce persisted-path revalidation and
  scheduler draining, DLP parity, fail-closed API authentication, and
  path-safe Project API responses with local error-write observability.
- Quality evidence for the v1.1.0 candidate: 757 passed, 3 skipped, 3 known
  warnings (local verification on 2026-08-06); Ruff, package build, secret
  scan, benchmark baseline and CI are required release-truth gates.

## Current resume bullet

> Designed and implemented a controlled multi-agent repository-analysis system
> with deterministic orchestration, schema contracts, runtime guardrails,
> auditable artifacts, a reproducible 12-case benchmark, and a mock-only
> FastAPI/SQLite change-review lifecycle slice; hardened its DLP and HTTP
> boundaries; validated the current `main` baseline with 757 passing automated
> tests and release-quality gates.

The concise, application-ready version is
[specflow-resume-v0.md](specflow-resume-v0.md).

## Boundaries to preserve in interviews

- Do not claim production deployment, user traffic, semantic accuracy, or live
  provider quality from the mock benchmark.
- The documented M6 live-provider run is historical evidence; no later live run
  is claimed without authorized credentials and a separate validation record.
- A reviewer decision is unverified display metadata, not an authenticated
  approval or multi-user collaboration claim.
