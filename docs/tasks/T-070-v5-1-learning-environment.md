# T-070 — V5.1 learning environment

- Status: FROZEN
- Owner: repository owner
- Source: `AI_Agent工程化学习路线_最终迭代版_V5.1 (1).docx`

## Objective

Turn the supplied 30-day AI Agent engineering roadmap into durable repository
instructions and study-state files without changing SpecFlow runtime behavior.

## Allowed scope

- Merge a teaching-mode contract into the existing root `AGENTS.md`.
- Add the faithful Markdown roadmap at `docs/study/ROADMAP_V5_1.md`.
- Add the active Day 1 state at `docs/study/CURRENT.md`.
- Add the Day 1 evidence card and an ADR directory guide under `docs/study/`.
- Add this task specification and its completion report.

## Forbidden scope

- Do not modify `src/`, `tests/`, prompts, benchmark fixtures, or runtime
  configuration.
- Do not implement Repository RAG or any other roadmap feature.
- Do not weaken the frozen MVP baseline or the existing development workflow.
- Do not treat Codex-generated explanations, diagrams, or patches as evidence of
  the learner's ownership.
- Do not commit the source Word document.

## Instruction precedence

The learning contract is an additional gate over the existing repository rules.
When the current study mode is `PATCH`, code modification still requires a
separately frozen implementation task specification and the repository's normal
validation workflow. `SURVEY`, `TUTOR`, `FAULT`, and `REVIEW` remain read-only.

## Acceptance criteria

1. The V5.1 roadmap preserves its 30-day schedule, weekly gates, ownership
   levels, calibration timeboxes, Dev/Holdout isolation, Fake/Live evidence
   boundary, threshold discipline, and final acceptance checklist.
2. `CURRENT.md` selects Day 1 and `SURVEY`, forbids code changes, and stops after
   source-entry discovery so the learner can draw the first architecture map.
3. The root `AGENTS.md` retains all existing development rules and clearly
   defines the five learning modes plus the learner/Codex responsibilities.
4. The evidence card requires a learner prediction before Codex reveals a root
   cause or proposed fix.
5. All added Markdown links resolve locally, and no business-code diff exists.

## Validation

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```
