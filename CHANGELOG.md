# Changelog

## v1.1.0 (Unreleased)

- Security audit remediation: fixed real-provider token accounting (usage is
  read from `LLMResponse.usage`), thread-safe LLM call budgets, bounded stage
  deadline detection with queued-future cancellation and synchronous worker
  draining, expanded DLP redaction (AWS/GitHub/GitLab/Slack/Google/Azure,
  PEM blocks, DSNs, sensitive-variable assignments) with a final pre-provider
  scan, sensitive path exclusions (`.aws/`, `.ssh/`, `.kube/`, `.docker/`,
  `credentials`, `kubeconfig`), atomic artifact writes with per-file SHA-256
  integrity hashes and a `_COMPLETE` marker, structured error codes for policy
  and scheduler failures, SQLite `busy_timeout`, engine disposal on shutdown,
  and opt-in HTTP hardening (API key, repository-root allowlist,
  reviewer-label allowlist, run quotas) documented in the README.
- Release-realism fixes: `specflow.artifacts` now ships in the wheel (the
  unanchored `artifacts/` gitignore pattern no longer excludes the source
  package), the duplicate `/health` registration is removed, non-ASCII API
  keys fail closed with a clean 401, and a repeatable installed-wheel smoke
  script (build → clean venv → boot → mock run → artifact check) guards the
  install path.
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
