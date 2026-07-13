# T-060 Completion Report — Portfolio Application Materials

## Result

**PASS (self-review).** SpecFlow now has a concise application-facing resume V0
and a three-minute interview talk that use only current, reproducible v1.1.0
candidate evidence.

## Delivered

- `docs/resume/specflow-resume-v0.md`: two resume bullets, one compact bullet,
  stack, evidence boundaries and interview evidence links.
- `docs/demo/specflow-three-minute-talk.md`: timed problem → architecture →
  control design → evaluation → boundary narrative.
- README and credential-free demo now link to those materials.
- README’s DeepSeek claim is explicitly marked as historical M6 validation,
  not current v1.1.0 or mock-benchmark evidence.

## Evidence boundaries

Current material cites only: v1.1.0 unreleased candidate, 671 passed / 2
skipped, fixed six-agent topology, RuntimeGuard, schema-validated handoffs,
read-only evidence, and the 12-case mock artifact-contract benchmark.

It explicitly avoids production, user-traffic, semantic-accuracy, cost-reduction
and current live-provider claims. The historical M6 DeepSeek run is retained
only as separately scoped interview context.

## Verification

| Check | Result |
| --- | --- |
| `tests/test_release_metadata.py` | 2 passed |
| `uv run pytest -v` | 671 passed, 2 skipped, 3 warnings |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed (191 files) |
| `python scripts/check_secrets.py` | passed |
| `git diff --check` | passed |

## Boundary check

- No product/runtime code, dependency, package version, release tag, provider,
  runner or benchmark behavior changed.
- The portfolio-audit helper was attempted but could not read Windows GBK Git
  output; manual evidence review and repository gates were used instead.
- Untracked local `.claude/` files remain outside this task.
