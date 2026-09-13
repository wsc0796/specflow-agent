# T-083 Completion Report — No-Evidence Fail-Closed Boundary

> Integration identity (2026-09-13): T-083, formerly PR #9 T-072. Source: `c6c893c3a723a3f62c33265394ed1fcbf1c6029b` at `docs/reports/T-072-completion-report.md`. Original branch names, commits, dates and standalone validation below remain historical evidence, not integrated acceptance.

## Outcome

The multi-agent runner now stops before Coordinator planning or Agent execution
when evidence collection produces zero excerpts. It returns exit code `3` and
persists a bounded failure manifest with `error="EVIDENCE_NOT_FOUND"` using the
existing atomic write, integrity manifest, and final `_COMPLETE` conventions.

The Run API preserves this classified outcome in SQLite as
`failed_runtime/EVIDENCE_NOT_FOUND` without exposing raw repository paths or
exception details.

## Root cause

`EvidenceCollector.collect()` could return a valid `EvidenceBundle` with no
matched files, selected files, source hashes, or excerpts. `run_multi_agent()`
serialized that empty bundle and continued into Coordinator planning and Mock
Agent execution. Existing Mock fixtures then produced structurally valid output
and a successful run despite having no repository grounding.

## Changes

- Added a post-collection gate for `len(evidence.excerpts) == 0` before
  Coordinator construction.
- Reused the existing `EVIDENCE_NOT_FOUND` classified error code.
- Added bounded pre-execution failure persistence with evidence counts and no
  fabricated plan, Agent, Handoff, or Trace success.
- Added a runner regression test proving zero evidence stops both
  `Coordinator.plan()` and Agent execution and produces a hash-covered failure
  manifest.
- Added a Run API integration test for the persisted classified outcome.
- Updated unrelated success-path fixtures to contain minimal matching source
  evidence so they continue testing their intended policy, revision, API, and
  Artifact contracts.

## TDD evidence

### RED

```powershell
uv run pytest tests/test_cli_multi_agent.py::TestMultiAgentRunner::test_zero_evidence_fails_before_agents_and_persists_reason -q -p no:cacheprovider
```

Result: exit `1`; the current runner returned `0` instead of expected `3`.
The generated `sources.json` independently confirmed `Matched files: 0` and an
empty `source_hashes` mapping while the manifest recorded `completed`.

### GREEN

The same focused runner test passed after the minimal evidence gate. The runner
and API D2 tests then passed together: `2 passed`.

## Regression evidence

```text
Focused affected paths: 19 passed, 1 known warning
Full pytest:            773 passed, 3 skipped, 3 known warnings
Ruff lint:              passed (existing non-failing invalid-noqa warning)
Ruff format:            208 files already formatted
Secret scan:            passed
Mock benchmark:         passed, 12 cases
Normalized baseline:    matches benchmarks/results/mock-baseline.json
git diff --check:       passed
```

An independent read-only review found no Critical issues. Its required
completion-report finding and two Minor test-evidence findings were addressed:
the regression test now proves Coordinator non-execution and verifies the
failure manifest's recorded SHA-256.

## Boundaries retained

- D1 context-window quality is unchanged; full file content is not injected.
- D13 Artifact consumer validation is unchanged.
- Agent schemas, retry, permissions, approval, checkpoint/resume, Review,
  revision, benchmark semantics, legacy runner, provider behavior, and
  dependencies are unchanged.
- This task treats only zero excerpts as no usable evidence. It does not invent
  a general relevance or semantic-quality threshold.

## Files

- `src/specflow/runner_multi.py`
- `tests/test_cli_multi_agent.py`
- `tests/test_api_security.py`
- `tests/test_evaluation_multi_agent.py`
- `tests/test_runs.py`
- `docs/tasks/T-083-no-evidence-fail-closed.md`
- `docs/reports/T-083-completion-report.md`
- `docs/study/CURRENT.md`
- `docs/study/evidence/day-01.md`
- `README.md`
- `AGENTS.md`
