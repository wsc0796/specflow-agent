# T-059 Completion Report — v1.1.0 Release Truth Gate

## Result

**PASS (self-review).** `main` is now an untagged `v1.1.0` release candidate.
The latest published tag remains `v1.0.1` at `a4fc16c`; this task does not
create a tag, GitHub Release, or package publication.

## Delivered

- `pyproject.toml` is the sole version truth source (`1.1.0`).
- `specflow.__version__` reads installed package metadata; FastAPI/OpenAPI and
  CLI `--version` consume that value instead of carrying a duplicate literal.
- Release tests verify the exact candidate, package/runtime/OpenAPI equality,
  CLI output and exit code, and current README/CHANGELOG/handoff wording.
- CI now smoke-tests `uv run specflow --version` after package installation.
- Current README, demo, handoff and resume evidence call v1.1.0 unreleased and
  retain v1.0.1 as the latest published release.

## Test-subflow report

```yaml
scope: package release metadata, OpenAPI version, CLI version command, and current release docs
behavior_and_risks:
  - version literals can drift after a package metadata change
  - a CLI may parse successfully while reporting a stale source version
tests_added_or_changed:
  - exact package/runtime/OpenAPI version contract
  - README/CHANGELOG/handoff candidate-versus-published contract
  - CLI --version output and zero exit-code contract
commands_and_results:
  - uv sync --all-groups: installed specflow-agent 1.1.0 from local source
  - focused release and CLI tests: 15 passed
  - uv run pytest -v: 671 passed, 2 skipped, 3 warnings
  - uv run ruff check . and format check: passed
  - uv build: specflow_agent-1.1.0 sdist and wheel built
  - uv run specflow --version: specflow 1.1.0
  - benchmark baseline comparison and secret scan: passed
quality_gates:
  - no new skip or xfail
  - CI receives installed-CLI version smoke coverage
uncovered_risks:
  - tag-to-commit and GitHub Release publication require a separate user-authorized action
next_recommended_gate: remote GitHub Actions after push
```

## Acceptance evidence

| Criterion | Evidence |
| --- | --- |
| One runtime version truth | `tests/test_release_metadata.py` compares PEP 621 metadata, `specflow.__version__`, app version and generated OpenAPI version. |
| CLI version contract | `tests/test_cli.py` checks `specflow 1.1.0` and zero exit; CI executes the installed command. |
| Current release wording | deterministic test checks README, CHANGELOG and handoff distinguish v1.1.0 candidate from v1.0.1 published tag. |
| Quality and benchmark gates | 671 passed, build, Ruff, secret scan, and normalized 12-case baseline comparison passed. |

## Boundary check

- No new dependency, Agent behavior, Runner change, provider expansion, API
  endpoint, database change, tag, release, or publication.
- Historical documents and published v1.0.1 record remain intact.

## Known limit

This gate proves metadata consistency in the checked-out candidate. It does not
prove a future Git tag points at the intended commit; create and verify a tag
only after the user explicitly authorizes publishing v1.1.0.
