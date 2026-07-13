---
task_id: T-061
title: Change Review Decision Loop
stage_state: closeout
owner: Codex
branch: main
---

# Goal

Turn the existing mock-only repository-analysis Run into the smallest usable
research-change review loop: a developer creates a controlled Run, a reviewer
reads a bounded review package, then records an append-only `accepted` or
`needs_changes` decision with rationale.

# Context and Inputs

- `WorkflowRun` already owns controlled execution state, policy/requirement
  hashes and an application-owned artifact directory.
- T-056/T-057 provide synchronous mock Run creation and durable interruption
  classification, but no business decision is recorded after output is viewed.
- The hackathon research recommends a narrow, demonstrable human-review loop
  instead of a generic Agent platform.

## L2 system model

| Dimension | Decision |
| --- | --- |
| Object | `ReviewDecision` is one append-only human review event attached to a completed Run. |
| Truth source | SQLite `review_decisions` plus the existing `workflow_runs` and application-owned artifacts. |
| Lifecycle | Developer creates Run → completed/completed_degraded with reviewable artifacts → reviewer records zero or more decisions. Run state is never overwritten by a decision. |
| Invariants | Only reviewable terminal Runs accept a decision; each event has a bounded label/rationale and timestamp; unknown or non-reviewable Runs are rejected; no raw artifacts, repo paths, credentials or identity claims are returned. |
| Contracts | `GET /api/v1/runs/{id}/review-package`; `POST /api/v1/runs/{id}/review-decisions`. |
| Impact | New table is created by existing metadata startup; no existing `workflow_runs` column is changed. |

# Allowed Scope

## Files

- `src/specflow/db.py`
- `src/specflow/runs.py`
- `tests/test_runs.py`
- `tests/test_projects.py` (update its historical exact-table assertion so it
  continues to validate the T-002 core tables without prohibiting this task's
  separately specified append-only table)
- `README.md`
- `AGENTS.md`
- `CHANGELOG.md`
- `docs/handoffs/CURRENT-STATE-2026-07-13.md`
- `docs/demo/portfolio-release-demo.md`
- `docs/resume/current-resume-evidence.md`
- `docs/research/2026-hackathon-agent-delivery-patterns.md`
- `docs/tasks/T-061-change-review-decision-loop.md`
- `docs/reports/T-061-completion-report.md`

## Commands

- `uv run pytest tests/test_runs.py -v`
- `uv run pytest -v`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv build`
- `python scripts/check_secrets.py`
- `git diff --check`

# Forbidden Scope

- Do not add authentication, user accounts, authorization, a queue, async worker,
  retry/resume, WebSocket, dashboard, GitHub App/webhook, Docker, Redis, vector
  database, MCP, RAG, live-provider execution, or a repository write capability.
- Do not modify `runner_multi.py`, Agent topology, execution policy, artifact
  schema, existing Run terminal mapping, or published release tags.
- Do not call reviewer labels authenticated identities; they are unverified
  presentation metadata in this single-process portfolio slice.
- Do not alter or stage unknown `.claude/` files.

# Acceptance Criteria

- [x] A completed mock Run has a bounded `review-package` containing safe Run
  metadata, direct artifact filenames and chronological review decisions.
- [x] A reviewer can append an `accepted` or `needs_changes` decision with a
  bounded reviewer label and rationale; a later decision does not overwrite the
  earlier event or Run state.
- [x] Missing Runs return 404; non-reviewable states or absent artifact evidence
  return 409; invalid decisions/payloads return 422.
- [x] A pre-existing SQLite database receives the new decision table at startup.
- [x] API output contains no absolute repository/artifact path, raw artifact
  contents, provider exception detail or claim of authenticated identity.
- [x] README/Demo explain the developer → Run → reviewer decision loop and its
  single-process/mock-only boundaries.

# Verification

| Command / Check | Proves | Required |
| --- | --- | --- |
| Run API integration tests | decision persistence, package contract, invalid-state and safety paths | yes |
| Full pytest | no project regression | yes |
| Ruff / build / secret scan / diff check | static, distribution and sensitive-data gates | yes |
| Remote CI | clean-environment quality, benchmark and security gates | yes before close |

# Testing Subflow

- Required: yes
- Trigger reason: API, persisted state/decision data and Agent artifact consumption.
- Test matrix:

| Acceptance / risk | Normal | Boundary | Failure / security | Layer | Evidence |
| --- | --- | --- | --- | --- | --- |
| Review package | completed mock Run exposes safe filenames and empty history | 32-file artifact cap remains enforced | no raw path/content | API integration | JSON assertions |
| Decision audit | append accepted then needs_changes | two events stay chronologically visible | reviewer/rationale bounds reject invalid data | SQLite + API integration | durable-history assertions |
| Eligibility | completed_degraded allowed | unknown Run 404 | created/failed/empty artifacts 409 | API integration | status assertions |
| Startup compatibility | new DB table exists | re-open existing SQLite path | no workflow schema rewrite | SQLite integration | inspector assertion |

- Quality-gate exceptions: none.
- Uncovered risks: no authentication, multi-user conflict resolution or async
  ownership exists; these are explicit future product requirements, not claims of
  this task.

# Deliverables

- `ReviewDecision` persistence model and narrow repository/service behavior
- Bounded review-package and decision API contracts
- Integration regression tests, documentation and completion evidence

# Risks and Rollback

- Risk: a reviewer label can be mistaken for identity. Mitigation: explicitly
  label it unverified and defer auth to an independently scoped task.
- Rollback: revert the focused commit; it adds one isolated table and no existing
  Run column or public contract is removed.

# Next Allowed State

`execution` after red tests reproduce the missing review-decision contract.
