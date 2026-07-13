# T-047 — Facts and Documentation Closure

```yaml
task_id: T-047
title: Facts and documentation closure
stage_state: closed
goal: Align current-facing project documentation with the checked-out branch, completed T-040/T-041 work, and verified test baseline.
allowed_scope:
  files:
    - AGENTS.md
    - README.md
    - docs/records/M8-production-hardening.md
    - docs/handoffs/CURRENT-STATE-2026-07-13.md
    - docs/roadmap/2026-07-13-portfolio-release-plan.md
    - docs/reports/T-047-completion-report.md
  modules: []
  commands:
    - uv run pytest -v
    - uv run ruff check .
    - uv run ruff format --check .
    - git diff --check
forbidden_scope:
  - Do not modify Python runtime code, tests, dependencies, CLI contracts, or artifacts.
  - Do not rewrite dated historical validation reports as if their original results were current.
  - Do not begin T-048 or any later task.
  - Do not merge to main or create a release tag.
inputs:
  - AGENTS.md
  - README.md
  - docs/records/M8-production-hardening.md
  - docs/reports/T-040-completion-report.md
  - docs/reports/T-041-completion-report.md
  - docs/handoffs/CURRENT-STATE-2026-07-13.md
acceptance:
  - Current-facing documents identify feature/m8-production-hardening as the active branch and e0bbcbb as the T-041 completion commit.
  - Current-facing documents state 656 passed, 2 skipped, and 3 known warnings from the verified local baseline.
  - T-040 and T-041 are described as complete without claiming a new live-provider validation.
  - A portfolio-release roadmap exists and keeps later tasks behind separate task specifications.
verification:
  - command: uv run pytest -v
    proves: The documented test baseline is reproducible.
  - command: uv run ruff check .
    proves: Repository lint gate remains clean.
  - command: uv run ruff format --check .
    proves: Repository formatting gate remains clean.
  - command: git diff --check
    proves: Documentation edits contain no whitespace errors.
outputs:
  - Corrected current documentation and handoff.
  - docs/roadmap/2026-07-13-portfolio-release-plan.md.
  - docs/reports/T-047-completion-report.md.
risks:
  - Historical reports contain their own dated test evidence; changing it would erase provenance. Preserve it and link current facts elsewhere.
  - New commits can change the test baseline after this task; future documents must verify again rather than reuse this count.
next_state: planning (T-048 only after its task specification is frozen)
```
