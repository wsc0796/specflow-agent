# T-058 Completion Report — Current Documentation Reconciliation

## Result

**PASS (self-review).** Current-facing material now distinguishes the published
`v1.0.1` tag from the later `main` code baseline instead of presenting them as
the same fact.

## Reconciled facts

| Fact | Canonical wording |
| --- | --- |
| Published release | `v1.0.1` at `a4fc16c` |
| Current pre-documentation code baseline | T-057 commit `07b38c5` |
| Quality evidence for that baseline | 669 passed, 2 skipped, 3 warnings |
| Remote CI | GitHub Actions run `29227064939` passed |

## Delivered

- README, handoff, credential-free portfolio demo and a new current resume
  evidence page use the same release-versus-development-baseline distinction.
- Current resume bullets now cite the T-057 669-test baseline and link to the
  dedicated evidence page.
- The M6 live demo, v0.1.0 candidate, M6/M7 project-mastery document and
  portfolio roadmap preserve their original numbers but visibly identify
  themselves as historical snapshots.

## Verification

| Check | Result |
| --- | --- |
| `uv run pytest -v` | 669 passed, 2 skipped, 3 warnings |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed (191 files) |
| `uv build` | source distribution and wheel built |
| `python scripts/check_secrets.py` | passed |
| `git diff --check` | passed |

## Boundary check

- No source code, behavior, package version, tag, release, dependency,
  runner, provider, or benchmark contract changed.
- Historical evidence was not rewritten; it is retained with a visible scope
  and date/status distinction.
- Untracked local `.claude/` files remain outside the task.

## Remaining risk

The current evidence number will change if a later task adds tests. T-059 must
update the current-facing facts in the same focused release-truth change rather
than leaving them implicit.
