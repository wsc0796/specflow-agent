# T-058 — Current Documentation, Handoff, and Resume Evidence Reconciliation

**Goal:** make current-facing documentation distinguish the published v1.0.1
tag from the later `main` development baseline, while preserving older evidence
as explicitly labelled historical snapshots.

**Allowed scope:** `README.md`; current handoff, demo, resume, and roadmap
documents; this task record and its completion report.

**Forbidden scope:** production code, test behavior, versions, tags, release
publication, runner refactors, live-provider work, or deletion/rewrite of
historical milestone evidence.

**Facts frozen for this reconciliation:**

- Published release: `v1.0.1` at `a4fc16c`.
- Current code baseline before this documentation-only task: `07b38c5`
  (`fix(runs): recover interrupted lifecycle records`).
- Local and remote CI evidence for that baseline: `669 passed, 2 skipped,
  3 warnings`; GitHub Actions run `29227064939` passed.

**Acceptance:**

1. Current README, handoff, credential-free demo and current resume evidence
   state the same release/development-baseline distinction.
2. Materials that retain 593/607/660/661 figures are visibly marked as
   historical snapshots rather than current evidence.
3. No historical test result is rewritten as if it happened later.
4. Full project quality gates pass, and a focused documentation commit is
   pushed with remote CI evidence.

**Verification:** `uv run pytest -v`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv build`, `python scripts/check_secrets.py`,
and `git diff --check`.
