# Changelog

## v1.1.0 (Unreleased)

- Hardening phases 1-3: strict role-scoped Task Briefs that observably change
  the target worker request; structured, stable-ID review findings that drive
  the real revision request (prior output, Task Brief, evidence and round
  included); bounded revision ending in `NEEDS_HUMAN_REVIEW`; unified
  `GuardedModelInvoker` covering enrichment, workers, reviewer, revision and
  re-review with per-attempt retry accounting, concurrency and wall-clock
  budgets, token usage read from the real provider response (missing usage is
  `unknown`, never 0), and budget snapshots in FAILED manifests.
- Calibrated the default provider-attempt budget to 24 (`max_llm_calls`
  remains a deprecated deterministic alias; 48 is allowed only as an explicit
  Live/Evaluation/experiment override).
- MCP: `tools/list` now reads the Tool-owned input schema as the single
  source; added a real subprocess stdio smoke test and an explicit CI MCP step;
  tool execution failures expose a machine-readable `error_type` via
  `structuredContent`.
- Added a release-truth gate: package metadata now drives the OpenAPI version
  and `specflow --version` CLI output.
- Added deterministic tests and CI smoke coverage that keep package, runtime,
  CLI and current release documentation aligned.
- Added a mock-only, human-in-the-loop change-review decision slice: completed
  Runs expose bounded review packages and retain append-only `accepted` or
  `needs_changes` decisions. Reviewer labels are unverified metadata; no
  authentication, asynchronous execution or repository-write capability is implied.

## v1.0.1, 2026-07-13

- Reconciled package and release metadata after the `v1.0.0` portfolio release.
- Added GitHub Actions checks for pytest, Ruff and tracked-file credential scan.
- Updated current-facing release documentation to reflect that `main` contains
  the released portfolio candidate.

## v1.0.0, 2026-07-13

- Released the controlled multi-agent workflow portfolio candidate.
- Included strict schema contracts, RuntimeGuard limits, auditable artifacts and
  a 12-case mock contract benchmark.
