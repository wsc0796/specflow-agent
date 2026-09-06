# T-072 — No-Evidence Fail-Closed Boundary

- Status: CLOSED
- Owner: Codex
- Branch: `codex/t072-no-evidence-fail-closed`
- Source finding: Day 1 D2

## Goal

Stop the multi-agent pipeline before Coordinator planning or Agent execution
when repository evidence contains no usable excerpts. Persist a safe,
classified `EVIDENCE_NOT_FOUND` failure instead of producing a successful Mock
plan without grounding.

## Requirements

- **REQ-072-1:** After evidence collection, a bundle with zero excerpts must
  stop the multi-agent run before any Agent executor is called.
- **REQ-072-2:** The CLI runner must return exit code `3` for this classified
  runtime failure.
- **REQ-072-3:** The output directory must contain a bounded failure manifest
  with `workflow_state="failed"`, `error="EVIDENCE_NOT_FOUND"`, zero completed
  stages, and evidence-count fields sufficient to diagnose the boundary.
- **REQ-072-4:** The early failure artifacts must use the existing atomic write,
  artifact-size, integrity-manifest, and `_COMPLETE` conventions.
- **REQ-072-5:** Runs with at least one valid evidence excerpt must preserve the
  existing multi-agent behavior.
- **REQ-072-6:** The Run API must persist the classified runner outcome as
  `failed_runtime` with `error_code="EVIDENCE_NOT_FOUND"` without exposing raw
  repository paths or exception details.

## Allowed scope

- `src/specflow/runner_multi.py`
- `tests/test_cli_multi_agent.py`
- `tests/test_api_security.py`
- `tests/test_evaluation_multi_agent.py`
- `tests/test_runs.py`
- `docs/tasks/T-072-no-evidence-fail-closed.md`
- `docs/reports/T-072-completion-report.md`
- `docs/study/CURRENT.md`
- `docs/study/evidence/day-01.md`
- `README.md`
- `AGENTS.md` only if current phase facts must be synchronized after validation

## Forbidden scope

- Do not change Evidence ranking, keyword extraction, context size, or full-file
  injection (D1).
- Do not change Artifact consumer validation (D13).
- Do not change Agent input schemas, retry, permissions, approval, checkpoint,
  Review, revision, benchmark semantics, legacy runner behavior, API contracts,
  dependencies, or provider behavior.
- Do not add Vector/Hybrid RAG, frameworks, generic middleware, or a new state
  machine.

## Acceptance criteria

- **AC-072-1:** Given a valid repository and a requirement with zero matching
  evidence excerpts, the multi-agent runner returns `3` and no Agent executor
  is invoked.
- **AC-072-2:** The generated failure manifest records
  `workflow_state="failed"`, `error="EVIDENCE_NOT_FOUND"`, and
  `stages_completed=0` without raw repository paths or exception details.
- **AC-072-3:** The early failure directory ends with valid
  `artifact-integrity.json` and `_COMPLETE` files.
- **AC-072-4:** The existing evidence-backed Mock run remains successful.
- **AC-072-5:** Focused tests, full pytest, Ruff lint, Ruff format, secret scan,
  and `git diff --check` pass.
- **AC-072-6:** A project-bound API Run with zero evidence returns its normal
  HTTP creation response containing `failed_runtime`,
  `error_code="EVIDENCE_NOT_FOUND"`, and an available bounded failure artifact.

## Test-first plan

1. Add one focused regression test that creates a repository with unrelated
   source content and a unique zero-match requirement.
2. Override the repository-analyst executor with a sentinel that must not run.
3. Assert exit code, non-execution, safe failure manifest, zero evidence counts,
   and completion/integrity markers.
4. Run the focused test and confirm it fails because the current pipeline
   continues into Agent execution.
5. Implement the smallest post-collection evidence gate and bounded
   pre-execution failure persistence needed to satisfy the test.
6. Run focused and full validation, then write the completion report.

## Risks

- Treating every low-evidence case as zero-evidence would expand behavior beyond
  D2. This task gates only `len(evidence.excerpts) == 0`.
- Early failure happens before a Coordinator plan exists; failure persistence
  must not fabricate plan, Agent, Handoff, or Trace success.
- A generated failure directory is diagnostic evidence, not a successful run
  artifact.
