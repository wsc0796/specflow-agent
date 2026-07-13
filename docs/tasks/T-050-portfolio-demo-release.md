# T-050 — Portfolio Demo Release

```yaml
task_id: T-050
title: Portfolio demo release
stage_state: closed
goal: Give a new reviewer an honest five-minute path from README to a reproducible mock benchmark, artifacts, architecture explanation, and interview-ready project narrative.
allowed_scope:
  files:
    - README.md
    - docs/demo/portfolio-release-demo.md
    - docs/interview/portfolio-talking-points.md
    - docs/tasks/T-050-portfolio-demo-release.md
    - docs/reports/T-050-completion-report.md
forbidden_scope:
  - Do not change runtime code, dependencies, provider configuration, API surface, or benchmark results.
  - Do not claim a new live-provider validation or semantic model-quality score.
  - Do not expose credentials, raw prompts, absolute paths, or generated artifacts.
inputs:
  - benchmarks/results/mock-baseline.json
  - docs/reports/T-048-completion-report.md
  - docs/reports/T-049-completion-report.md
  - docs/records/M8-production-hardening.md
acceptance:
  - README makes the project purpose, two execution modes, benchmark command, proof boundary, and key artifacts obvious.
  - A 3-5 minute mock-only demo can be followed without provider credentials.
  - Interview notes explain fixed topology, schema fail-close, RuntimeGuard, benchmark evidence, and known limits without stale claims.
verification:
  - command: uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/portfolio-demo-check
    proves: The documented demo command produces the promised artifact report.
  - command: uv run pytest -v
    proves: Full regression gate.
  - command: uv run ruff check .
    proves: Lint gate.
  - command: uv run ruff format --check .
    proves: Format gate.
  - command: git diff --check
    proves: Documentation diff quality.
outputs:
  - Updated README, demo guide, interview talking points, task contract, and completion report.
risks:
  - The mock benchmark validates runtime contracts only. It does not prove live-provider quality or cost.
  - Existing historical interview notes remain archival and must not override the new portfolio notes.
next_state: review (T-051 independent branch review)
```
