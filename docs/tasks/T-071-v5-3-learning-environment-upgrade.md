# T-071 — V5.3 learning environment upgrade

- Status: FROZEN
- Owner: repository owner
- Source: `AI_Agent工程化学习路线_最终迭代版_V5.3.docx`
- Supersedes: [T-070](T-070-v5-1-learning-environment.md)

## Objective

Replace the active V5.1 study roadmap with the owner-supplied V5.3 roadmap and
synchronize every active teaching instruction that depends on the roadmap,
without changing SpecFlow runtime behavior or starting Day 1.

## Allowed scope

- Rename `docs/study/ROADMAP_V5_1.md` to `ROADMAP_V5_3.md` and replace its
  contents with a faithful Markdown conversion of the supplied Word document.
- Update the root `AGENTS.md` learning contract for V5.3 Runtime Safety,
  Behavior Eval, minimal Durability, supplier timeboxes, and external-reference
  discipline.
- Update `docs/study/CURRENT.md`, the Day 1 evidence card, and the ADR guide so
  their active rules and links match V5.3.
- Add this task specification and its completion report.

## Forbidden scope

- Do not modify `src/`, `tests/`, prompts, benchmark fixtures, dependencies, or
  runtime configuration.
- Do not implement Tool Permission, Behavior Suite, checkpoint/resume,
  Repository RAG, or any other roadmap feature.
- Do not execute the Day 1 opening instruction embedded in the roadmap.
- Do not weaken the frozen MVP baseline, existing mandatory workflow, learner
  ownership gate, Dev/Holdout isolation, or Fake/Live evidence boundary.
- Do not commit the source Word document or preserve a second active roadmap.

## Migration decisions

- `ROADMAP_V5_3.md` becomes the sole active roadmap; V5.1 remains recoverable
  from Git history rather than as a competing active file.
- The five learning modes and their transition rules remain unchanged.
- V5.3 additions are recorded as future study gates, not as claims that the
  corresponding SpecFlow hooks or behavior already exist.
- Any external framework or ecosystem statement in the supplied roadmap remains
  attributed to that roadmap and must be revalidated against official sources
  before it drives implementation.

## Acceptance criteria

1. All non-empty V5.3 Word paragraphs and table cells appear in the converted
   Markdown, including Day 1–30 and sections 1–16.
2. No active V5.1 roadmap link remains in `AGENTS.md` or `docs/study/`.
3. The teaching contract enforces cms-flow ≤2.5h, a separate 8–10 case Behavior
   Suite, L0–L3 Runtime Safety, one bounded durability experiment, and no
   supplier becoming a second implementation track.
4. Day 1 remains `READY` / `SURVEY` and asks only for source-hook discovery;
   absent permission/checkpoint hooks must be marked `unknown`.
5. All local Markdown file links resolve and no product-code diff exists.

## Validation

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```
