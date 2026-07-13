# T-061 Completion Report — Change Review Decision Loop

## Outcome

`APPROVED (self-review)` — the mock-only Run API now supports the smallest
human-in-the-loop change-review decision loop without changing the existing
Agent runtime, execution policy or Run terminal-state semantics.

## Delivered behavior

- `GET /api/v1/runs/{run_id}/review-package` returns safe Run metadata, at most
  32 direct artifact filenames, and chronological decisions only for completed
  or completed-degraded Runs with artifact evidence.
- `POST /api/v1/runs/{run_id}/review-decisions` appends a bounded `accepted` or
  `needs_changes` event. It never overwrites an earlier event or the Run state.
- SQLite owns the new isolated `review_decisions` table. `Base.metadata.create_all`
  creates it when an older local database starts; no existing `workflow_runs`
  column is changed.
- Reviewer labels are explicitly unverified presentation metadata. The slice has
  no authentication, authorization, queue, async worker, GitHub integration,
  live provider or repository-write capability.

## Acceptance evidence

| Acceptance criterion | Evidence |
| --- | --- |
| Bounded, safe completed-Run review package | `test_completed_run_exposes_review_package_and_append_only_decisions` asserts safe JSON, filenames, empty and populated history. |
| Append-only accepted/needs_changes events preserve Run state | Same integration test appends two chronological records and verifies the Run remains completed. |
| 404/409/422 error contracts | `test_review_decision_rejects_unknown_nonreviewable_and_invalid_runs` and `test_empty_artifact_directory_is_not_exposed_as_a_valid_artifact_index`. |
| Completed-degraded remains reviewable | `test_completed_degraded_run_remains_reviewable`. |
| Existing SQLite compatibility | `test_startup_adds_run_metadata_to_a_legacy_sqlite_database` verifies `review_decisions` appears on startup. |
| Documentation and boundary synchronization | README, current demo, resume evidence, handoff and changelog describe the review loop and explicitly state its limits. |

## Test subflow

```yaml
scope: FastAPI Run API, SQLite decision persistence, artifact-consumption contract
behavior_and_risks:
  - only completed/completed_degraded Runs with artifact evidence are reviewable
  - decisions are append-only and preserve Run state
  - API does not return artifact paths/content or authenticate labels
tests_added_or_changed:
  - tests/test_runs.py: package, chronological decisions, invalid state, absent artifacts, degraded state, legacy database
  - tests/test_projects.py: preserves the T-002 core-table assertion without forbidding this independently specified table
commands_and_results:
  - uv run pytest tests/test_projects.py tests/test_runs.py -v: 14 passed
  - uv run pytest -v: 674 passed, 2 skipped, 3 warnings
  - uv run ruff check .: passed
  - uv run ruff format --check .: 191 files already formatted
  - uv build: source distribution and wheel built
  - python scripts/check_secrets.py: passed
  - git diff --check: passed
quality_gates: no new skip or xfail; deterministic API and SQLite integration coverage added
uncovered_risks:
  - no authentication, authorization, multi-user concurrency control or reviewer identity proof
  - mock benchmark remains a contract test, not a live-model quality or business-impact measure
  - remote CI remains required after push
next_recommended_gate: inspect remote GitHub Actions before any v1.1.0 release decision
```

## Self-review

- **Specification and scope:** implementation matches T-061 and does not modify
  `runner_multi.py`, Agent topology, execution policy or artifacts.
- **Persistence:** new data is isolated in its own table; existing database
  metadata fields are untouched.
- **API safety:** responses expose only Run DTO metadata, direct filenames and
  explicit decision fields; they do not expose paths, raw artifacts or caught
  exceptions.
- **Adversarial checks:** missing Run maps to 404; created/empty-artifact Run
  maps to 409; unsupported decision maps to Pydantic 422; a completed-degraded
  Run is accepted; a decision cannot mutate the Run status.

This is a self-review in the same coding context, not an independent review.

## 90-day premortem

| Likely failure | Early signal | Mitigation / next gate |
| --- | --- | --- |
| Users interpret a label as authorization | Demo or resume says “approved by reviewer” | Keep `reviewer_label` unverified; add authenticated identity only in a separately approved auth task. |
| Multiple reviewers make conflicting decisions | Alternating accepted/needs_changes events | Preserve append-only history; define user ownership/conflict rules before multi-user delivery. |
| Mock-only sync execution is mistaken for a service worker | Long requests block a local process | Keep the boundary in README; only design queue/timeout/cancellation after an observed product need. |
| Teams claim quality improvement without data | Resume claims risk-detection accuracy | Build a human-labeled public change-request set before reporting quality, time or cost metrics. |

## Release status

Local gates are complete. The focused commit and remote CI verification are the
remaining closeout steps; this report does not authorize a tag or GitHub Release.
