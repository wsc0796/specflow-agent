# Runtime repair integration — 2026-09-13

## Authorization and goal

The owner approved contract coordination and isolated integration verification
for PRs #6, #7, #8, #9 and #10 after reviewing their concrete overlap. Build a
reviewable local integration branch, preserve each source commit, reconcile task
identity and runtime result contracts, and verify the combined behavior. This
does not authorize merging those PRs into main, publishing a release, beginning
M9 T-071, or any M10 runtime implementation.

## Pinned inputs

| Input | Commit |
| --- | --- |
| origin/main | 1b44127747a7f7b8bfd9118eb56006d867986b39 |
| #6 M9/M10 specification registration | 02556b90aeec5fcc55dd7426bb3098dcf1e788f4 |
| #7 T-081 required output validity | 0ab5545c756ae68ef7f9cad88515d47915e0062c |
| #10 T-082 trusted packaged prompts | 942f5d8a3e46ff0bced65931d0eb3bea5dd9fe4a |
| #8 T-070 single-flight plus A01 repair | c54aaf703313764cf4ea1605eb883d8263ae9e52 |
| #9 evidence gate / handoff classification / learning documents | c6c893c3a723a3f62c33265394ed1fcbf1c6029b |

PR #5 and the separate runtime-correctness branch are excluded. Source PRs and
their branch history remain unchanged. Local branch:
`integration/runtime-repairs-20260913`.

## Scope and invariants

1. Preserve M9/M10 frozen task meanings and numbering. Resolve PR #9's independent
   learning/repair task aliases with an explicit provenance mapping and distinct
   report paths. Never overwrite the T-070 single-flight completion report.
2. Integrate the pinned existing changes, then modify only necessary callers,
   shared runtime boundaries, fixtures, packaging smoke, and affected docs.
   Do not introduce dependencies, database columns, agents, retries, cache,
   distributed coordination, or a new scheduling system.
3. Authentication/path validation and minute accounting remain authoritative.
   A follower has independent durable identity and no duplicate execution permit.
4. Missing evidence fails before planning/provider work. Invalid required outputs
   stop their consumers. Business REJECT stays distinct from infrastructure errors.
5. Every normal owned-run exit yields the existing immutable integer-compatible
   RunResult directly. Newly integrated failures retain their safe error class
   and any safely completed diagnostic artifact reference; no result is rebuilt
   from a large manifest.
6. Publish terminal outcomes only after running work and required writes finish;
   API terminal persistence precedes follower publication. Cancellation must not
   release capacity while worker threads remain alive.
7. Trusted packaged prompts work from an unrelated CWD and remain isolated from
   repository/CWD prompt injection. Preserve original prompt bytes and versions.
8. Adapt positive test fixtures to supply real matching evidence when needed.
   Never weaken missing-evidence or invalid-output failure assertions to obtain
   a green suite. Historical standalone evidence stays attributed to its source.

## Acceptance and evidence

- Resolve textual conflicts with both change intents preserved, then inspect
  semantic interfaces even in automatically merged files.
- Exercise equivalent concurrent requests, no-evidence early rejection,
  invalid required outputs, safe handoff classification, large legacy manifests,
  cancellation/draining, and API commit failure with explicit synchronization.
- Run affected targeted tests, `uv run pytest -v`, `uv run ruff check .`,
  `uv run ruff format --check .`, `git diff --check`, staged checks, and
  `uv run python scripts/check_secrets.py` with locked dependencies and no live calls.
- Build wheel/sdist, execute the integrated installed-wheel smoke with locked
  dependency constraints, and compare the 12-case mock benchmark without rewriting
  its baseline. Test the sdist-rebuilt wheel as required by T-082.
- Record source commits, resolutions, actual commands/results, pending decisions,
  and the integrated delta in `docs/reports/runtime-repairs-integration-2026-09-13.md`.
- Preserve the reviewable local branch and stop. Local merge commits are source
  assembly checkpoints; only the final combined gates establish integration evidence.
