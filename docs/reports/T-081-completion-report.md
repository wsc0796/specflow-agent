# T-081 / D1 completion — 2026-09-11

## Identity and result

- Branch: `fix/t081-required-output-validity` (independently based on main).
- BASE_SHA: `1b44127747a7f7b8bfd9118eb56006d867986b39`.
- Source/claim and raw evidence identities: [dated correction](T-081-evidence-correction.md).
- Final fix identity: the focused commit containing this report; obtain with
  `git log -1 --format=%H -- docs/reports/T-081-completion-report.md`.
- Verification code: BASE_SHA plus the T-081 diff in that commit; offline fake
  model `offline-recording-provider`. Real HTTP transports are blocked by pytest.

| Finding → baseline | Reproduction | Actual baseline | Fixed result |
|---|---|---|---|
| `{}` / missing summary | `uv run pytest tests/test_required_output_validity.py -q` | All 12 role cases already refused; 22 tests passed overall | Preserved; no invented pre-fix failure |
| Blank summary / role content | Same suite, recorded provider through real CLI and AgentRunner | 12 cases wrongly returned 0 | Refused before required consumers |
| Explicit schema_validated=false | Stage envelope injection | Design was scheduled | Refused before consumer |
| Missing provider output contract | Captured real AgentRunner LLMRequest | Schema absent | Authoritative model JSON Schema transmitted |
| Valid / planning-degraded / empty findings / REJECT | Same real adapter path | Existing semantics passed | Preserved |
| Run API invalid output | Real Run API and mock runner, bad analyst injected | failed_runtime, no review package | Preserved |

Initial test-authoring mistake (fake LLMResponse omitted finish_reason) was
corrected before measuring the baseline. The valid baseline measurement was
**22 passed / 14 failed**, not the earlier invalid fake's result. After adding
two no-op/permitted-degradation controls, all 38 new cases pass.

## Changes

Tightened existing role schemas and stage envelope handling. Mock payloads now
contain explicit mock change/test/synthesis content under the same minimum
contract. This does not prove their semantic usefulness. Adapter prompts render
the authoritative schema rather than inventing another schema or relaxing it.
PR #5 already has a related prompt-field listing; it was inspected, not merged.
That still-open branch should reconcile this smaller registry-derived form.

Updated the README, current resume/demo references and dated M6/T-041 corrections.
T-041 receiver models use dictionary defaults; the runtime stage boundary, not
nested input model validation, is what prevents invalid outputs reaching consumers.
No new status, provider call, topology or revision behavior was introduced.

## Quality evidence

- Targeted adapter/payload/CLI/API group: **78 passed, 1 Windows symlink skip**
  before adding the two positive controls; those controls passed in the full run.
- `uv run pytest -v`: **809 passed, 3 skipped, 3 warnings**.
- Windows skips: repository_tools, scanner, runs symlink privileges. Warnings:
  two pre-existing TestStrategy class collection warnings and the Starlette
  httpx deprecation. No new-key regression was skipped.
- `uv run ruff check .`: passed; `uv run ruff format --check .`: 210 formatted.
- Existing benchmark command plus `git diff --no-index --exit-code` against
  `benchmarks/results/mock-baseline.json`: passed with no baseline changes.
- `git diff --check`, tracked-file secret scan and staged-diff review are required
  before this commit. No original live directory is staged.

## Evidence and build identities

- Derived summary SHA-256:
  `533a6d3dd296cb3bd5f1e60edb7a3617d728c7f36085f85014d162d373df76f7`.
- Independent synthetic fixture SHA-256:
  `fb2e1d799607798293c45d949d31ddca0b269504eec34aac95dc483c353df27b`.
- Built via `uv build --wheel --out-dir <fresh-d1-dist>` from the verified T-081
  working tree: version **1.1.1**, `specflow_agent-1.1.1-py3-none-any.whl`.
- Wheel SHA-256: `ff2303199bc819783f3898e4c0ad19168421f0ce0af6ae7ae214874e56d82431`.
- D1 does not fix installed legacy prompt loading; D2 has its own main-based branch,
  clean build and installed-entry reproduction. This wheel is not a release.

## Limits and next gate

Missing historical run identities remain unknown. M6 samples cannot establish
current strict-contract live validation. Nonblank fields do not prove factual
accuracy, executable design quality, usefulness, or superiority over legacy.
REJECT can still accompany execution completion; consumers must read the review
decision. `_COMPLETE` remains a file-publication marker, not approval.

The D3/D4 gate still needs independently fixed case criteria and explicit live
provider/data/cost authorization. No new live evaluation, production recovery,
M9/M10, version release or merge was performed. PR and CI identities are recorded
in the final delivery ledger after push; this local report does not preclaim CI.
