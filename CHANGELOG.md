# Changelog

## v1.1.0 (Unreleased)

- Added a release-truth gate: package metadata now drives the OpenAPI version
  and `specflow --version` CLI output.
- Added deterministic tests and CI smoke coverage that keep package, runtime,
  CLI and current release documentation aligned.

## v1.0.1, 2026-07-13

- Reconciled package and release metadata after the `v1.0.0` portfolio release.
- Added GitHub Actions checks for pytest, Ruff and tracked-file credential scan.
- Updated current-facing release documentation to reflect that `main` contains
  the released portfolio candidate.

## v1.0.0, 2026-07-13

- Released the controlled multi-agent workflow portfolio candidate.
- Included strict schema contracts, RuntimeGuard limits, auditable artifacts and
  a 12-case mock contract benchmark.
