# T-071 — Provider Resilience Guard

> **规范复审结案（2026-09-13）：AMENDMENT FROZEN。** 用户转交的外部静态规范
> 复审确认固定提交 `c14e0380b6daa1be9fa49101bfd79ccb582cd46c` 中的
> R12-01 / P2 为 **RESOLVED / CLOSED BY STATIC SPEC RE-REVIEW**，
> S12-01 → R12-01 → CLOSED。本文件该提交的 REQ/AC 正文作为后续 T-071
> 的权威规范，本次仅登记结案，不修改条款。以下两块“待重审”为此前阶段的历史
> 记录；规范结案不代表实现或运行时验收，仍须满足 T-070 关闭及新 focused session。
> 详细依据见[规范结算与开工门检查](../reports/T-071-T-080-spec-review-entry.md)。

> **修订说明（2026-09-13）：AMENDMENT PROPOSED / 待重审。** 来源为
> PR #12 固定提交 `558004b2bfc46ddcf76317ba30123a12f486445f` 的外部规范重审
> S12-01 / P2。本次修订后端资源身份，不代表实现完成或 dependency gate 已满足。
> 下方 FROZEN 为既有冻结记录；本修订尚待重审，不构成实施放行。

> **后续修订（2026-09-13）：AMENDMENT PROPOSED / 待重审。** 固定提交
> `a178735b335628d650e9755c91545c94af926c9b` 的复审发现 R12-01 / P2 接续
> S12-01：在 endpoint 隔离基础上补充内部 provider tenancy 身份，与公开审计别名
> 分离。本次仍为规范修订，不代表实现完成或实施门已满足。

**Status:** FROZEN. Implementation requires T-070 to be closed and a new focused
session.

## Goal

Add deterministic, bounded resilience state around live provider/model calls so
repeated transient provider failures open an explicit circuit and later allow
bounded half-open probes, while preserving existing retry, fallback, error,
mock, schema, and audit semantics.

## Requirements

- **REQ-071-1 — Scope state by provider resource.** Maintain independent
  process-local state for the internal breaker key:

  ```text
  (backend_resource_identity, effective_model, provider_tenancy_discriminator)
  ```

  `backend_resource_identity` 以有界不透明身份表示有效配置实际连接的后端，
  必须区分不同 effective endpoint；`openai-compatible` 等协议名不是唯一后端
  身份。`effective_model` 使用有界、规范化身份。原始 URL 仅在已有配置边界内
  用于后端解析，不作为 registry key 或公开标签。
  `provider_tenancy_discriminator` 必须区分会影响 availability/rate-limit domain
  的 credential/provider tenancy。默认采用仅驻留进程内、抗碰撞的不可逆凭据
  指纹（例如 SHA-256）；raw API key 绝不能放入 key。也可采用明确配置的有界
  不透明 provider-project/tenant alias，但其绑定必须区分相关配额/可用性域。
  不得仅因 endpoint/model 相同或公开 alias 相同就共享状态。若不同 credentials
  的 tenancy 要共享，必须明确说明为何其 availability/rate-limit domain 可安全
  共享，并提供对应测试证据；否则按凭据隔离。同一真实后端、effective model
  和 tenancy 可以合法共享 breaker。
  内部 discriminator（无论凭据指纹还是 opaque tenancy alias）仅用于内部 breaker
  identity，不持久化，也不进入 metrics、trace、artifact 或日志。内部 key 与
  REQ-071-8 的公开 audit alias 分离，公开 alias 不能用作完整内部 key 的替代。
  raw API key、prompt、request body、repository data、原始 tenant/user data 均
  不得进入 key；允许内部使用派生指纹/不透明 tenancy 标识，不等于允许公开它们。
- **REQ-071-2 — Implement the state machine.** Provide explicit
  `CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN` behavior with configurable positive
  thresholds, open duration, and bounded half-open probe count. Use an injected
  monotonic clock so transition tests require no wall-clock sleeps.
- **REQ-071-3 — Count only classified provider availability failures.** Reuse
  the existing error taxonomy. Provider timeout, rate limit, server, and
  connection failures may count toward opening. Authentication, model-not-found,
  invalid JSON, schema mismatch, security, policy, artifact, and local coding
  errors must retain their existing classifications and must not be mislabeled
  as circuit health failures.
- **REQ-071-4 — Keep one retry owner.** The guard wraps actual live provider
  attempts and reports their result; it must not create a second retry loop.
  Existing AgentRunner/FallbackManager retry budgets remain the retry owners.
  Failure accounting occurs once per real provider attempt, not once per
  fallback result or degraded envelope.
- **REQ-071-5 — Reject open circuits explicitly.** An OPEN circuit rejects
  before network I/O with a new safe provider-circuit error. The rejection is
  non-retryable within the same request, may flow into the existing honest
  fallback/degraded path where that path is already allowed, and must never look
  like a successful provider response. A HALF_OPEN probe is exclusive up to the
  configured probe bound; excess probes are rejected explicitly.
- **REQ-071-6 — Integrate both live pipelines.** Legacy and multi-agent live
  calls must pass through the same guard contract. Mock mode bypasses live
  resilience state entirely: it neither opens a circuit nor consumes half-open
  probes, and remains deterministic.
- **REQ-071-7 — Clean up safely.** Every permitted call must release its probe
  slot after success or failure. Exceptions must not strand a HALF_OPEN probe or
  corrupt another backend/model/tenancy key's state. State access must
  be thread-safe.
- **REQ-071-8 — Keep audit data bounded.** Expose only safe state, transition,
  rejection, failure-count, provider-resource alias, and model alias metadata
  required by T-073. 公开 metrics、trace、artifact、日志中的身份字段仅可使用有界安全别名，
  不得包含原始 URL、API key、prompt、repository data、tenant/user data、
  exception body、raw provider output 或无界 registry key。别名不得直接拼入
  这些原始值；公开 model alias 同样受既有 sanitization/DLP 边界约束。
  完整 internal breaker key、credential fingerprint 及 internal tenancy
  discriminator 均不得输出；不得直接用指纹充当公开 provider-resource alias。
- **REQ-071-9 — Expected implementation surface.** Expected production files
  are a focused `src/specflow/llm/resilience.py`,
  `src/specflow/llm/providers/openai_compatible.py` or a shared LLM decorator,
  `src/specflow/agents/adapter.py`, `src/specflow/runner.py`,
  `src/specflow/runner_multi.py`, and the minimum policy/error/default files.
  Expected tests are `tests/test_provider_resilience.py`,
  `tests/test_openai_compatible_provider.py`, `tests/test_fallback.py`,
  `tests/test_cli.py`, and `tests/test_cli_multi_agent.py`. If integration would
  duplicate retry/fallback ownership or require a third-party dependency, stop
  and amend the specification with evidence before editing.

## Boundaries

The following are explicit non-goals for T-071:

- Depends on closed T-070; do not reopen its equivalence contract except for
  compatible audit hooks.
- No Resilience4j or other third-party resilience dependency unless a separately
  reviewed spec amendment proves the standard library design insufficient.
- No Agent-level circuit: six agents sharing one backend resource, effective
  model, and provider tenancy share that state; Agent IDs do not create separate breakers.
- No distributed breaker, persistence across restart, external health probe,
  provider failover router, load balancer, or background recovery task.
- No new retry budget, unbounded probe traffic, sleep-based tests, or network
  dependent tests.
- No change to schema validation, DLP, topology, revision, or business
  PASS/REJECT semantics.

## Acceptance

- **AC-071-1:** Deterministic unit tests cover CLOSED success, counted failures,
  threshold opening, OPEN rejection without transport calls, clock-driven
  transition to HALF_OPEN, probe success closing, probe failure reopening, and
  excess probe rejection.
- **AC-071-2:** 测试覆盖以下资源身份与共享边界，并验证 registry 有界及线程安全：
  - same protocol + same model + different backend resource（不同 effective
    endpoint）→ breaker state isolated；后端 A 打开熔断不阻断健康后端 B；
  - same endpoint + same effective model + different credential/provider tenancy
    → rate-limit/failure state isolated；A 因多次 429 打开 breaker 后，健康 B 仍被允许；
  - same real backend resource + same effective model + same tenancy → breaker
    state legitimately shared；不同 effective model 的状态独立；
  - mock → neither reads nor mutates live breaker state，也不消耗 half-open probe；
  - internal key 的 tenancy 分量仅使用进程内不可逆指纹或明确配置的不透明标识，
    不含 raw credential；metrics/trace/artifact/log 均无 raw credential、fingerprint
    或 internal tenancy discriminator，符合 REQ-071-1/-8；
  - authentication failure 仍按 REQ-071-3 排除在 breaker health 计数之外，
    不能因加入 credential identity 而改变既有错误分类。
- **AC-071-3:** Tests prove counted transient failures versus excluded auth,
  model, JSON, schema, security, and internal failures using the existing
  taxonomy.
- **AC-071-4:** Integration tests prove retry counts are unchanged, one real
  attempt is counted once, circuit rejection is safe/non-success, and allowed
  fallback remains honest and degraded.
- **AC-071-5:** Mock clients remain deterministic and never alter or consult live
  breaker state. No test performs network I/O.
- **AC-071-6:** Existing live-provider transport safety, CLI/mock, fallback,
  schema, DLP, and T-070 concurrency tests remain green.
- **AC-071-7:** Targeted tests pass, followed by `uv run pytest -v`,
  `uv run ruff check .`, `uv run ruff format --check .`, and
  `git diff --check`.
- **AC-071-8:** `docs/reports/T-071-completion-report.md` records the state key,
  counted failures, retry ownership, mock boundary, tests, and known
  single-process limit. One focused implementation commit is created, then work
  stops before T-072.
