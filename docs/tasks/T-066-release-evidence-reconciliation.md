# T-066 — Release Evidence Reconciliation

**Goal:** reconcile current-facing v1.1.0 candidate materials with the
post-T-065 `main` baseline, without changing package behavior or publishing a
release.

**Allowed scope:** `README.md`; `AGENTS.md`; the current handoff, demo, and
resume-evidence documents; this task record; and its completion report.

**Forbidden scope:** production code, tests, package version, tags, GitHub
Release publication, provider execution, benchmark contracts, or alteration of
historical reports and dated evidence.

## Facts frozen for this reconciliation

- Published release: `v1.0.1` at `a4fc16c`.
- Current candidate baseline: `main` / `origin/main` at `40db000`.
- Local verification on 2026-08-06: `757 passed, 3 skipped, 3 warnings`;
  Ruff, formatting, tracked-file secret scan, and `git diff --check` passed.
- T-062 through T-065 are included in this candidate; they do not establish a
  new live-provider validation or a published release.

## Acceptance

1. README, handoff, credential-free demo, and resume evidence all identify the
   same v1.0.1 published-release / v1.1.0 untagged-candidate distinction.
2. Current materials cite the post-T-065 local baseline and explain its scope;
   historical evidence remains unchanged.
3. The handoff names final local release gates and explicit user authorization
   as prerequisites for a tag or GitHub Release.
4. Full quality gates, package build, installed-wheel smoke, benchmark baseline,
   and `git diff --check` have recorded outcomes before the focused commit and
   remote-CI verification.

## Verification

`uv run pytest -v`, `uv run ruff check .`, `uv run ruff format --check`,
`python scripts/check_secrets.py`, `uv build`,
`python scripts/smoke_installed_wheel.py`, the committed mock benchmark command,
and `git diff --check`.
