# SpecFlow Agent Portfolio Release Plan

> **历史路线图快照**：其中的 660 测试数、Draft PR 和“不含 API/持久化”边界
> 反映发布规划时的事实，不能作为当前状态。当前事实以 README、handoff 和
> `docs/resume/current-resume-evidence.md` 为准。

**Date:** 2026-07-13

**Target:** `v0.1.0-portfolio`

**Release state:** `main` contains v1.0.1; the portfolio release is closed.
**Planning status:** T-047 through T-054 are closed; later tasks require their own task specs.

## Purpose

Turn the existing controlled multi-agent repository-analysis system into a
portfolio release that a reviewer can run, inspect, and evaluate quickly. The
release prioritizes reproducible evidence over new platform surface area.

## Current facts

- M8 hardening includes RuntimeGuard-based multi-agent budget enforcement and
  strict sender/receiver agent payload validation (T-040 and T-041).
- The default CLI remains the legacy pipeline; multi-agent mode is opt-in.
- The current local quality baseline is **660 passed, 2 skipped, 3 warnings**.
- M8 is branch-only and has no new live-provider claim.

## Explicit non-goals

- Do not add persistence, an API service, authentication, Docker, deployment,
  dynamic agent discovery, RAG, or automatic code modification.
- Do not claim live-provider results from mock runs or invent benchmark
  improvements.
- Do not modify target repositories used as read-only evaluation inputs.

## Release sequence

```text
T-047 facts and documentation closure
  -> T-048 reproducible benchmark harness
  -> T-049 bounded live validation (optional; credentials required)
  -> T-050 portfolio demo release
  -> T-051 independent branch review
  -> v1.0.1 released portfolio metadata and CI
```

Each task is independently mergeable. A missing live-provider credential skips
T-049 and does not block the mock-backed portfolio release.

## T-047 — Facts and documentation closure

**Goal:** make current-facing project documentation agree with the checked-out
branch, latest completed work, and verified test baseline.

**Deliverables:** a task spec, corrected current-state documentation, an updated
handoff, and a completion report. Historical reports retain their original
dated validation results and gain no retrospective claim.

**Acceptance:** current documents identify T-040/T-041 as complete, report the
660/2/3 baseline, name `feature/m8-production-hardening`, and state that M8 has
not been merged to `main`.

## T-048 — Reproducible benchmark harness

**Goal:** prove behavior with a versioned, deterministic mock benchmark rather
than an anecdotal demo.

**Scope:** 12 cases: four repository-understanding cases, four change-planning
cases, and four review/risk cases. Each case declares its requirement, permitted
read-only fixture/repository, and a machine-checkable evidence contract of
expected fixture paths. The runner produces a
machine-readable aggregate report from existing run artifacts.

**Metrics:** schema pass rate, completion/degraded/failure counts, fallback
rate, token totals, latency, and error-code distribution. Scores requiring human
judgment remain explicitly manual; no LLM judges are introduced.

**Acceptance:** the suite runs in mock mode from a clean checkout and produces
stable aggregate results plus traceable per-case artifacts. The task spec must
freeze file ownership and exact CLI command before implementation.

## T-049 — Bounded live validation

**Goal:** create a small, honest live-provider evidence set.

**Scope:** one or two authorized read-only repositories and one to three
representative benchmark cases. The run uses explicit execution-policy limits.

**Acceptance:** artifacts contain no credentials, raw prompts, or local absolute
paths; policy, schema, handoff, and output evidence are inspectable. Results are
labelled with provider, model, date, and `live` status, separately from mock
results.

**Stop condition:** no valid provider credentials or authorized target repository
means record T-049 as skipped; do not fabricate a substitute result.

## T-050 — Portfolio demo release

**Goal:** let a new reviewer understand and reproduce the project in five
minutes.

**Scope:** README quick start and architecture diagrams, a 3–5 minute demo
script, interview notes, a reproducible mock artifact walkthrough, and benchmark
summary tables.

**Acceptance:** a clean terminal can follow the documented mock command and
inspect the expected artifacts. Documentation distinguishes established facts,
mock evidence, and optional live evidence.

## T-051 — Independent branch review

**Goal:** establish merge readiness for the portfolio release.

**Scope:** review `main...feature/m8-production-hardening` against the frozen
baseline, M8 boundaries, and this roadmap. Review must be performed in an
independent context/agent; same-context review is labelled self-review.

**Acceptance:** documented findings and verdict; all required quality gates pass;
no untracked secrets or generated artifacts; create a Draft PR only after an
approved verdict.

## Common quality gate

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

## Decision rule after release

New production hardening work must be evidence-driven. Prioritize typed fallback,
token/cost accounting, or full-pipeline redaction only when benchmark or live
validation exposes a concrete gap. Persistence and API service require a real
consumer and a separately approved specification.
