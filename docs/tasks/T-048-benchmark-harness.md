# T-048 — Reproducible Portfolio Benchmark Harness

```yaml
task_id: T-048
title: Reproducible portfolio benchmark harness
stage_state: closed
goal: Add a deterministic mock benchmark command that executes the existing fixed multi-agent pipeline against a versioned 12-case fixture suite and writes inspectable aggregate evidence.
allowed_scope:
  files:
    - src/specflow/cli.py
    - src/specflow/evaluation/
    - benchmarks/cases/
    - benchmarks/fixtures/portfolio-python/
    - benchmarks/results/mock-baseline.json
    - tests/test_benchmark.py
    - docs/reports/T-048-completion-report.md
    - README.md
    - AGENTS.md
    - docs/records/M8-production-hardening.md
    - docs/handoffs/CURRENT-STATE-2026-07-13.md
    - docs/roadmap/2026-07-13-portfolio-release-plan.md
  modules:
    - existing multi-agent runner and metrics artifact contract
    - evaluation report serialization
  commands:
    - uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/benchmark-t048 --baseline benchmarks/results/mock-baseline.json
    - uv run pytest -v
    - uv run ruff check .
    - uv run ruff format --check .
    - git diff --check
forbidden_scope:
  - Do not change the legacy runner, multi-agent execution semantics, policy defaults, or provider behavior.
  - Do not add model judges, external services, dependencies, persistence, API endpoints, Docker, or deployment work.
  - Do not execute a live provider, require credentials, or claim model-quality improvement from mock results.
  - Do not modify any target repository outside the committed benchmark fixture.
inputs:
  - docs/roadmap/2026-07-13-portfolio-release-plan.md
  - src/specflow/runner_multi.py
  - src/specflow/evaluation/metrics.py
  - src/specflow/evaluation/runner.py
  - tests/test_evaluation.py
acceptance:
  - The CLI exposes a benchmark subcommand whose only execution mode is deterministic mock multi-agent execution.
  - The committed suite contains exactly 12 safe case definitions: 4 repository-understanding, 4 change-planning, and 4 review-risk cases.
  - Every case is checked against a committed read-only fixture before execution and produces a separate artifact directory.
  - The aggregate JSON reports case/category pass counts, schema pass rate, success/degraded/fallback rates, token totals, latency summary, and error-code counts when present.
  - A committed normalized mock baseline records stable result fields without absolute paths, timestamps, credentials, or raw prompts.
  - Tests cover case loading, aggregate metric calculation, missing-fixture failure, and CLI execution.
verification:
  - command: uv run pytest tests/test_benchmark.py -v
    proves: Benchmark contracts and CLI behavior.
  - command: uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/benchmark-t048 --baseline benchmarks/results/mock-baseline.json
    proves: All 12 mock cases produce aggregate evidence and artifacts.
  - command: uv run pytest -v
    proves: Full regression suite.
  - command: uv run ruff check .
    proves: Lint quality gate.
  - command: uv run ruff format --check .
    proves: Formatting quality gate.
  - command: git diff --check
    proves: Diff has no whitespace errors.
outputs:
  - Benchmark CLI and evaluation implementation.
  - 12 cases, one self-contained fixture repository, normalized baseline JSON, tests, README instructions, and completion report.
risks:
  - Wall-clock latency is inherently variable; it is emitted only in per-run output and excluded from the committed normalized baseline.
  - Mock output proves contract reproducibility, not semantic quality or live-provider performance.
  - Generated run artifacts must stay in the ignored output path and never be committed.
next_state: planning (T-049 only when its live-validation inputs are available; otherwise T-050)
```

## L2 system model

| Dimension | T-048 decision |
| --- | --- |
| Object | `BenchmarkCase`, per-case multi-agent artifact directory, aggregate benchmark report, normalized baseline. |
| Truth source | Committed case JSON and fixture repository; runner-produced `manifest.json`/`metrics.json` provide run facts. |
| Lifecycle | Load cases → validate fixture references → run mock multi-agent pipeline → validate artifacts/metrics → aggregate → write report → normalize baseline. |
| Invariants | Exactly 12 uniquely identified cases; mock-only; fixture-relative paths only; no raw prompts, credentials, timestamps, or absolute paths in the committed baseline. |
| Contracts | `specflow benchmark` requires `--suite`, `--repo`, and `--output`; report is JSON and each run carries status plus metrics-derived evidence. |
| Impact | CLI dispatch and evaluation module gain a new bounded command; existing `run` command and both runners remain unchanged. |

## Adversarial review before execution

- A green mock suite cannot establish LLM semantic quality; the report labels its
  mode as `mock_contract` and T-049 is the only route to a live claim.
- Re-running into the same output directory must not reuse an earlier artifact;
  each benchmark invocation requires a new or empty output root.
- The committed baseline must not include elapsed time because it is not stable
  across machines; runtime reports still include latency for operational review.
