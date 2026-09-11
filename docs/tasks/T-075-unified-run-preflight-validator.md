# T-075 — Unified Run Preflight Validator

**Status:** FROZEN. Implementation requires T-074 to be closed and a new focused
session.

## Goal

Consolidate inexpensive run validation into one ordered, auditable preflight
before semantic plan enrichment or any live provider call, while retaining the
existing component validators as the owners of their individual contracts.

## Requirements

- **REQ-075-1 — Add an orchestration layer, not replacement validation.** A
  `RunPreflightValidator` (or equivalently focused module) calls existing
  repository, policy, topology/plan, schema, prompt, provider-configuration,
  Agent-constraint, single-flight-key, cache, and execution-admission validators.
  Component-level checks remain callable and authoritative; preflight must not
  duplicate or bypass their rules.
- **REQ-075-2 — Use a deterministic order.** Run security/input boundary checks
  first; static policy/topology/schema/prompt/Agent checks second; mock/live
  provider configuration third; cache/key compatibility and execution
  admissibility last. Stop before evidence can enter a prompt or the Coordinator
  can perform semantic enrichment.
- **REQ-075-3 — Cover both pipelines and entry points.** Legacy CLI,
  multi-agent CLI, mock-only Run API, and benchmark calls use the same applicable
  preflight contract. Mode-specific checks are explicit: mock mode never
  requires live credentials, and the HTTP API remains mock-only and
  project/allowlist-bound.
- **REQ-075-4 — Validate the fixed runtime contract.** For multi-agent mode,
  build and validate the deterministic structural plan without semantic LLM
  enrichment; verify the exact six registered Agents, all input/output schema
  IDs in a frozen registry, stage/parallel constraints against policy, and
  revision bounds. Preflight itself makes zero provider calls.
- **REQ-075-5 — Validate prompt availability.** Resolve every versioned prompt
  required by the selected legacy path and verify declared variables through
  `PromptRegistry`/loader contracts. Multi-agent hard-coded/system prompt and
  semantic-enrichment inputs must be validated through their owning static
  contracts. Preflight must not render repository evidence into a provider
  request.
- **REQ-075-6 — Validate live provider configuration safely.** For live mode,
  validate provider choice, model, URL, timeout, and credential presence through
  existing config types without opening a network connection and without
  persisting or logging credential values. Mock mode bypasses this check
  explicitly rather than supplying fake live credentials.
- **REQ-075-7 — Keep admission authoritative.** Preflight may report current
  lane capacity and reject a known-saturated request, but a later atomic T-072
  admission remains the truth because capacity can change after preflight. A
  race produces the existing explicit saturation error, never a silent retry or
  TOCTOU success claim.
- **REQ-075-8 — Return a safe structured result.** Successful preflight yields a
  bounded immutable report with validated mode, policy/topology/schema/prompt
  versions, effective provider/model aliases, repository/equivalence hash
  references, and admissibility status. Failure yields the existing or a
  narrowly added safe error code, stage `preflight`, and no raw exception,
  requirement, path, prompt, credential, provider body, or cache payload.
- **REQ-075-9 — Define failure mapping.** Invalid caller input remains an input
  failure; repository/security violations remain security failures; policy,
  topology, schema, prompt, or Agent contract failures fail closed; live
  provider configuration failure returns the documented configuration outcome;
  cache invalidity follows T-074 miss/recompute rules; saturation remains a
  T-072 admission failure. Preflight failures are not retried or degraded by
  provider fallback.
- **REQ-075-10 — Expected implementation surface.** Expected production files
  are a focused `src/specflow/preflight.py`, `src/specflow/runner.py`,
  `src/specflow/runner_multi.py`, `src/specflow/runs.py`,
  `src/specflow/cli.py`, `src/specflow/policy/validator.py`, and minimal
  Coordinator/schema/prompt/admission adapters. Expected tests are
  `tests/test_preflight.py`, `tests/test_cli.py`,
  `tests/test_cli_multi_agent.py`, `tests/test_runs.py`,
  `tests/test_execution_policy.py`, `tests/test_plan_validator.py`, and prompt/
  schema tests. Any validator removal or provider probe requires a spec
  amendment.

## Boundaries

The following are explicit non-goals for T-075:

- Depends on closed T-074 and preserves T-070 through T-074 behavior.
- No provider/network call, repository mutation, build command, shell command,
  Maven execution, migration, background check, or external health probe during
  preflight.
- No replacement or weakening of repository allowlists, PolicyValidator,
  PlanValidator, SchemaRegistry, PromptRegistry, Pydantic schemas, DLP, or lane
  admission.
- No dynamic Agents, topology change, general-purpose DAG validation, retry,
  fallback, resume, queue, or deployment behavior.
- No guarantee that a preflight capacity observation reserves future capacity.
- No Java/Maven authorization; T-075 remains within the Python baseline.

## Acceptance

- **AC-075-1:** A successful mock preflight validates all applicable static
  contracts and performs zero live provider calls.
- **AC-075-2:** Live preflight detects missing/invalid provider configuration
  before evidence, semantic enrichment, scheduler submission, or transport I/O,
  and never exposes credential values.
- **AC-075-3:** Focused tests independently fail repository boundary, policy,
  fixed topology, Agent registry, schema ID/freeze, prompt presence/variables,
  provider config, equivalence/cache compatibility, and known saturation gates
  with stable safe classifications.
- **AC-075-4:** Tests prove each owning component validator is still invoked and
  remains independently covered; preflight does not reimplement its rules.
- **AC-075-5:** API failures persist/return only the documented safe lifecycle
  outcome; CLI failures preserve compatible exit-code and error-artifact
  boundaries; no fallback turns preflight failure into success.
- **AC-075-6:** Existing mock/live-transport unit tests, Run API, benchmark,
  policy, plan, schema, prompt, DLP, and T-070 through T-074 tests remain green.
- **AC-075-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-075-8:** `docs/reports/T-075-completion-report.md` records validation
  order, component ownership, failure mapping, tests, zero-provider-call proof,
  and capacity-race limit. One focused implementation commit is created, then
  work stops for the M9 runtime review; T-076 must not begin automatically.
