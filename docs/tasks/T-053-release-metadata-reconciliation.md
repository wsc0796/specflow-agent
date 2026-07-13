# T-053 — v1.0.1 Release Metadata Reconciliation

**Goal:** reconcile published release metadata with `main` and add remote CI gates.

**Allowed scope:** package version, current-facing release documents, changelog,
GitHub Actions quality gate, local secret scan, and focused regression tests.

**Forbidden scope:** Agent runtime behavior, providers, policies, tools, API
contracts, benchmark semantics, automatic code modification, and deployment.

**Acceptance:** version `1.0.1` is consistent across package and current release
documents; GitHub Actions runs tests, Ruff and secret scan; release records state
that `v1.0.0` is merged and that `v1.0.1` is a metadata/CI release.
