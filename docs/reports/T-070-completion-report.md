# T-070 Completion Report — V5.1 Learning Environment

- Date: 2026-09-05
- Branch: `codex/v5-1-learning-contract`
- Base commit: `1b44127747a7f7b8bfd9118eb56006d867986b39`
- Task: [T-070](../tasks/T-070-v5-1-learning-environment.md)
- Result: COMPLETE

## Delivered

- Preserved the existing development rules and added the five-mode V5.1
  learning contract to the root `AGENTS.md`.
- Converted the owner-supplied V5.1 Word document into
  `docs/study/ROADMAP_V5_1.md`, preserving all 30 days, weekly gates, evidence
  boundaries, timeboxes, and the final acceptance checklist.
- Added `docs/study/CURRENT.md` with Day 1 in `READY` / `SURVEY`; the learning
  session has not been started and no architecture answer has been prefilled.
- Added a learner-owned Day 1 evidence card and an ADR directory guide.
- Added the frozen T-070 task specification required by the repository workflow.

## Scope evidence

- No file under `src/`, `tests/`, `prompts/`, or `benchmarks/` changed.
- No dependency or runtime configuration changed.
- The source Word document was not copied into the repository.
- No Repository RAG implementation was started.

## Validation evidence

| Check | Result |
| --- | --- |
| `uv sync --all-groups` | Exit 0; Python 3.12.10 environment created from the committed lockfile |
| `uv run pytest -v` | Exit 0; 771 passed, 3 skipped, 3 known warnings in 19.46s |
| `uv run ruff check .` | Exit 0; all checks passed, with the existing invalid-`noqa` warning in `tests/test_coordinator.py:113` |
| `uv run ruff format --check .` | Exit 0; 208 files already formatted |
| `git diff --check` | Exit 0 |
| Word-to-Markdown content check | 410 source units checked; 0 missing |
| Roadmap day check | All Day 1–30 rows present exactly in the schedule |
| Local Markdown link check | 0 broken local file links under `docs/study/` |

## Known boundary

This task initializes the teaching environment only. Day 1 begins after the
learner explicitly requests it; the learner must still run, interpret, and
record the baseline evidence required for ownership.
