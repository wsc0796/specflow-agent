# T-075 — Unified Run Preflight Validator

> **修订说明（2026-09-13）：AMENDMENT PROPOSED / 待重审。** 来源为
> PR #12 固定提交 `558004b2bfc46ddcf76317ba30123a12f486445f` 的外部规范重审
> S12-02 / P2。本次修订 preflight 与 follower admission 的边界，不代表实现
> 完成或 dependency gate 已满足。下方 FROZEN 为既有冻结记录；本修订尚待重审，
> 不构成实施放行。

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
- **REQ-075-2 — Use a deterministic order.** 所有请求先经过适用的 authentication、
  repository allowlist/security boundary、caller input validation 及 request/rate
  accounting 检查；再做适用的静态 policy/topology/schema/prompt/Agent 检查、
  mock/live provider configuration 检查和 cache/key compatibility 检查。
  同 key 不能豁免这些检查或既有请求/速率计数规则。按 T-070 REQ-070-2/-3/-6
  确定 owner/follower 身份后，才能判断是否需要新的 execution capacity；
  不得在身份未确定时，以 lane capacity 为零一律拒绝请求。request/rate
  accounting 保持既有原子接纳与计数语义，不重复扣计；确认 follower 前仍须
  通过适用的速率门。全部检查须在 evidence 进入 prompt 或 Coordinator 进行
  semantic enrichment 前完成，且不得为 follower 启动昂贵执行。
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
- **REQ-075-7 — Keep admission authoritative.** Preflight 的 capacity observation
  不是 reservation；真正容量事实由 T-072 atomic admission 决定。execution
  lane saturation rejection 仅适用于真正需要启动新执行的 owner，不适用于
  已通过上述检查并确认加入现有 owner 的 follower。依照 REQ-072-8，follower
  不取得第二份 expensive execution permit，不提交第二份 provider/local lane
  work，只按 T-070 做 bounded wait，并保留独立 Run API 审计身份。
  对需要新执行的 owner，已知 saturation 通过 T-072 原子接纳明确拒绝；
  preflight 不另建容量裁决或预留机制。observation 到 actual admission 之间
  即使发生竞争，失败仍返回已有 T-072 saturation outcome，不 silent retry、
  不生成第二 owner，也不声称观察到容量就已接纳。ownership 清理及 follower
  失败/超时语义仍遵循 T-070。
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
  provider config, equivalence/cache compatibility, and owner saturation gates
  with stable safe classifications. 使用确定性同步覆盖 REQ-075-2/-7：
  - lane saturated + same valid equivalence key → 合法 follower 可加入仍在执行的
    owner；不增加 execution permit 或 provider/local lane submission，仅 bounded wait；
  - lane saturated + different key → 需要新执行的 owner 由 atomic admission
    明确拒绝，返回 T-072 saturation outcome；
  - same key 但 unauthenticated、unauthorized repo 或 rate-limited → 仍拒绝，
    不因可合并而绕过安全或 request/rate accounting；
  - preflight 观察有容量但 admission race 失败 → 显式 T-072 saturation outcome，
    无 silent retry、重复 owner 或重复昂贵执行。
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
