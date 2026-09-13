# T-082 / D2 completion — 2026-09-12

## Result and source identity

The default legacy CLI now runs after non-editable wheel installation at an
unrelated CWD. Default prompts are trusted package resources, not CWD files.

- Branch: `fix/t082-packaged-prompt-resources`, independent of D1 / PR #7.
- BASE_SHA: `1b44127747a7f7b8bfd9118eb56006d867986b39` (`origin/main`).
- Final fix commit: the focused commit containing this report; locate with
  `git log -1 --format=%H -- docs/reports/T-082-completion-report.md`.
- Test/config identity: baseline plus this commit's diff; Python 3.12.10,
  `uv.lock` runtime dependencies, mock only, no provider credentials inherited
  by installed-smoke subprocesses. Pytest real HTTP transports are blocked.
- Final clean-commit wheel/sdist hashes and PR/CI identity are recorded in the
  delivery ledger and PR after the post-commit build; no remote CI is preclaimed here.

## Facts and reproduction

| Finding | Version / identity | Reproduction | Result / disposition |
|---|---|---|---|
| Default installed CLI broken | Fresh 1.1.1 wheel built from BASE_SHA | Non-editable temporary venv, unrelated CWD, no PYTHONPATH, `specflow run --repo <fixture> --requirement "Add a health endpoint." --output <new-output> --mock` | exit **3**, empty stdout/stderr, only error JSON (`Workflow execution failed`), no successful run directory |
| Missing prompt resource | Same venv, verified specflow.__file__ and metadata inside its site-packages | `PromptRegistry().get("analyze_requirement", "1.0.0")` | `PromptNotFoundError`; root prompts absent from wheel |
| Source default uses untrusted CWD | Source tests at BASE_SHA | Bundled prompt lookup and forged CWD root | six new cases fail; 29 existing cases pass |
| Fixed installation | Verified T-082 working tree, intermediate wheel below | Expanded existing installed smoke, then standalone sdist → wheel and repeated smoke | both **PASS**, all ten checks, no skipped default entry |
| Historical 1.1.0 wheel | Not required as current-source evidence | Not installed or modified in this task | No claim about that historical binary |

Initial unit test authoring selected the internal `.traces` directory and expected
Python None for fallback; corrected to the actual run directory and existing
`FallbackLevel.NONE == "none"` contract. Neither correction changed product behavior
or relaxed the requirement to avoid fallback.

## Minimal implementation

- Moved the six versioned metadata/template files from root `prompts/` into
  `src/specflow/prompt_assets/`, the sole authoritative copy. All six files are
  byte-identical to the original files in the baseline sdist. Versions, template
  variables, wording and security rules are unchanged.
- PromptRegistry defaults to `importlib.resources.files("specflow")`. It fully
  loads each definition inside `as_file` and returns owned strings/metadata;
  it never caches an extracted temporary filesystem path. Custom roots still
  use the original name/version/path/template validation and never fall back.
- Existing Hatch `packages = ["src/specflow"]` includes these package resources
  in both release paths; no dependency or build-version changes are needed.
- Updated current resource documentation; T-006 retains a dated-layout note.
- Extended `scripts/smoke_installed_wheel.py`; its existing CI job now lets the
  script build in a fresh directory, selecting exactly one new wheel/sdist.
  It never chooses an old `dist/` file by sort order.

## Installed acceptance

For both the supplied wheel and a wheel rebuilt from an extracted standalone
sdist, a new venv installs the exact artifact and verifies package and metadata
origins. Runtime children clear PYTHONPATH/PYTHONHOME/SPECFLOW variables; isolated
Python probes use `-I`. All runtime executions use mock fixtures.

1. Default legacy CLI: no `--mode`, unrelated CWD, parsed AnalysisOutput,
   GenerationOutput and ReviewOutput, matching lineage, PASS, required Markdown
   artifacts, three correct worker roles, fallback_level=`none` for every trace.
2. Explicit legacy: same success contract; explicit multi-agent: six validated
   outputs, seven handoffs, manifest/metrics/PASS consistency.
3. Run API: create project/run, inspect terminal state, artifact integrity and
   parsed multi-agent contracts, retrieve completed review package.
4. Resources: all six installed files match the chosen wheel's bytes; every
   template loads and renders. Explicit custom copy loads, invalid roots and
   traversal fail. Valid forged CWD prompts load only when explicitly selected;
   defaults and a subsequent default CLI still use the bundled resources.
5. Source/editable tests additionally cover parent-directory spoofing and
   extraction lifetime, along with existing metadata/template/path validations.

## Verification and real failures

- Targeted tests: **39 passed**.
- `uv run pytest -v`: **777 passed, 3 skipped, 3 warnings**.
- Windows skips remain the three existing symlink privilege checks. Two existing
  TestStrategy collection warnings and the Starlette/httpx warning remain.
- Ruff check: passed. Ruff format check: **209 files already formatted**.
- Final diff/secrets/staged review are performed before the focused commit;
  raw build output and virtual environments are outside the repository.
- Installed smoke first failed at dependency installation: pip's hash mode,
  activated by locked requirement hashes, lacked a hash for the new local wheel.
  Corrected by first installing pinned hashed requirements, then installing the
  exact wheel with `--no-deps`. The complete second run passed both wheels.
  No dependency versions were upgraded and no acceptance was skipped.

## Package identities

All artifacts are version **1.1.1**, named
`specflow_agent-1.1.1-py3-none-any.whl` / `specflow_agent-1.1.1.tar.gz` in separate
fresh output directories. None are published releases.

| Build | Wheel SHA-256 | Sdist SHA-256 |
|---|---|---|
| BASE_SHA reproduction | `7265690830652697d0bcc388c255ba9eb68a602d2becf18ae5b6dadc255909dd` | `86d04d5c796cea6cdd2b6f28aa9b34b8c668801021a59ae3d9db289902a114ca` |
| Intermediate verified T-082 tree | `61d694e3c2bfcf4bd9e4326ada952db140c8a3657001a8497f0bae624035859b` | `ccc94eca3dff250a7d0e368182b65934b5e157f7304bcf2725ed9c3b9ed812e0` |

The intermediate standalone sdist rebuild produced the same wheel SHA-256.
Those hashes identify the intermediate tree, not the final commit: later changes
format source comments and finalize smoke/reporting. The final clean-commit build
is separately identified and re-smoked before push. Its identities are placed in
the delivery ledger/PR, avoiding a self-referential sdist hash inside its own report.

## Limits

Mock installation success proves resource availability and entry contracts, not
generated specification usefulness or live quality/speed superiority. D1 remains
a separate PR; no D1 runtime diff is included here. No live validation, production
recovery, M9/M10, release, automatic merge or unrelated refactor was performed.
