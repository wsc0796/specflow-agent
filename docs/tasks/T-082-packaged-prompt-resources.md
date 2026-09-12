# T-082 — Installed default CLI and packaged prompt resources (D2)

- Date: 2026-09-11; BASE_SHA: `1b44127747a7f7b8bfd9118eb56006d867986b39`.
- Branch: `fix/t082-packaged-prompt-resources`, independent of T-081 / PR #7.
- Authorization: owner's D1/D2 instruction. Scope fixed before implementation.
- T-070–T-080 remain allocated; T-081 is the separate output-validity repair.

## Reproduction and root cause

A fresh 1.1.1 wheel built from main and non-editably installed with locked
dependencies returns exit 3 from the default CLI at an unrelated CWD, leaving
only a workflow-error JSON. PromptRegistry resolves `prompts` relative to CWD;
the root-level assets are not installed in the wheel. The existing smoke only
exercises multi-agent Run API and therefore misses the default legacy entry.

## Invariants and modification surface

1. Move the single authoritative set of six YAML/Markdown files from root
   `prompts/` to `src/specflow/prompt_assets/`. Preserve their bytes, versions,
   variables and security wording. Current docs/test references follow the move.
2. Default PromptRegistry uses importlib.resources without CWD/parent/target
   searches. Complete file loading inside as_file's context; do not cache a
   potentially expired materialized path. Explicit custom roots retain the
   existing loader's validation and fail without fallback when wrong.
3. Extend `scripts/smoke_installed_wheel.py`: installed default CLI (no --mode),
   explicit legacy, multi-agent mock, API mock, parsed business contracts,
   resource integrity, custom/invalid roots and malicious CWD prompt isolation.
4. Build wheel and sdist in a fresh directory. Rebuild sdist alone into another
   wheel and repeat installed smoke. Verify venv import/metadata and remove
   PYTHONPATH/PYTHONHOME/provider env from runtime children. Use locked dependencies.
5. Preserve default mode, prompt content, APIs and dependencies. No release,
   automatic merge, D1 runtime changes, M9/M10 or unrelated CI platform matrix.

## Acceptance

- Unit regressions cover all bundled prompts at unrelated CWD, malicious CWD,
  explicit valid/invalid root, zip resource lifecycle, and existing lookup,
  metadata/template/path validation. Default legacy CLI parses its three business
  artifacts and verifies three worker trace identities without silent fallback.
- Existing installed-wheel script exercises all entries above and is called by
  the existing smoke CI job. No key acceptance is skippable.
- Targeted tests, full `uv run pytest -v`, Ruff check/format, diff/secrets/staged
  checks, fresh builds and both installed-wheel smokes pass before commit/PR.
- Record original/current package identity, actual failures and successful output
  contracts in a completion report. No original wheel is overwritten or released.
