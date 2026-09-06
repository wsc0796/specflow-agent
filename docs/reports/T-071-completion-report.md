# T-071 Completion Report — V5.3 Learning Environment Upgrade

- Date: 2026-09-06
- Branch: `codex/v5-3-learning-contract`
- Base commit: `3fdb264038e77b316f637fdfa6a45b4e5c9f055e`
- Task: [T-071](../tasks/T-071-v5-3-learning-environment-upgrade.md)
- Result: COMPLETE

## Delivered

- Replaced the active V5.1 roadmap with the owner-supplied V5.3 roadmap at
  `docs/study/ROADMAP_V5_3.md`; V5.1 remains available through Git history.
- Updated the root learning contract with V5.3 Runtime Safety L0–L3, the
  separate 8–10 case Agent Behavior Suite, one bounded durability experiment,
  shorter cms-flow timebox, and capability-based external references.
- Updated Day 1 state and evidence capture to locate Tool schema, permission,
  approval, loop-guard, checkpoint, and trace hooks while marking absent hooks
  as `unknown`.
- Updated ADR guidance for approval/idempotency evidence and version-sensitive
  external references.
- Added the frozen T-071 task specification required by the repository workflow.

## Scope evidence

- No file under `src/`, `tests/`, `prompts/`, or `benchmarks/` changed.
- No dependency or runtime configuration changed.
- No V5.3 feature or Day 1 task was implemented or executed.
- The source Word document was not copied into the repository.
- No active V5.1 roadmap link remains in `AGENTS.md` or `docs/study/`.

## Validation evidence

| Check | Result |
| --- | --- |
| `uv run pytest -v` | Exit 0; 771 passed, 3 skipped, 3 known warnings in 13.52s |
| `uv run ruff check .` | Exit 0; all checks passed |
| `uv run ruff format --check .` | Exit 0; 208 files already formatted |
| Word-to-Markdown content check | 641 source units checked; 0 missing |
| Roadmap structure check | Sections 1–16 and all Day 1–30 schedule rows present |
| Active-roadmap check | 0 active `ROADMAP_V5_1` references |
| Local Markdown link check | 0 broken local file links under `docs/study/` |

## Known boundary

External ecosystem statements copied from the supplied roadmap are planning
inputs, not implementation evidence. They must be revalidated against current
official sources before triggering a framework experiment or migration. Day 1
remains `READY` / `SURVEY` and still requires learner-owned baseline evidence.
