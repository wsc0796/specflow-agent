# SpecFlow Agent Portfolio Demo

> Current evidence baseline: `main` code commit `07b38c5` (T-057), 669 passed,
> 2 skipped, 3 known warnings, and GitHub Actions run `29227064939` passed.
> Published release: `v1.0.1` at `a4fc16c`. The benchmark remains mock-only.

This demo takes 3 to 5 minutes. It uses no provider credential and makes no
live-provider claim.

## 1. What to say first

SpecFlow is a controlled repository-analysis system. It keeps workflow authority
in deterministic code, while language models provide bounded semantic work. The
legacy pipeline is an A/B baseline. The multi-agent pipeline runs a fixed
six-agent topology with schema-validated handoffs, policy limits, traces, and
auditable artifacts.

## 2. Run the reproducible proof

```powershell
uv run specflow benchmark `
  --suite benchmarks/cases `
  --repo benchmarks/fixtures/portfolio-python `
  --output artifacts/portfolio-demo-check
```

Open `artifacts/portfolio-demo-check/benchmark-report.json`.

Explain that the suite has 12 committed cases: four repository-understanding,
four change-planning, and four review-risk cases. Each case runs the real
multi-agent runtime in mock mode and emits separate artifacts.

## 3. Show the evidence

Open one case directory and point to:

- `manifest.json`: workflow, policy and budget context.
- `agent-outputs.json`: six schema-validated agent results.
- `handoffs.json`: structured contracts between agents.
- `traces.json`: agent and stage timing.
- `metrics.json`: token, fallback, degraded, schema and latency fields.

The committed `benchmarks/results/mock-baseline.json` records stable facts:
12/12 passed, 100% schema pass rate, zero degraded and fallback runs. It omits
latency, timestamps, raw prompts and artifact paths because those are not stable
portfolio facts.

## 4. Explain the architecture

```text
RepositoryAnalyst
        |
Design + TestStrategy + RiskReview (parallel)
        |
Synthesis
        |
Review -> optional bounded revision -> completed
```

The topology is fixed. The Coordinator, state machine, SchemaRegistry and
RuntimeGuard own execution authority. A model cannot add agents, change
dependencies or exceed revision and token limits.

## 5. Close honestly

The benchmark demonstrates reproducible contract enforcement and artifact
integrity. It does not measure live model quality or real provider cost. A
previous M6 live-provider validation remains documented separately; T-049 was
skipped for this portfolio release because no provider credentials were present.

## Final command

```powershell
uv run pytest -v
```

The expected current result is 669 passed, 2 skipped and 3 known warnings.
