# Day 01 Evidence Card

- 状态：已完成，C1/C2 练习中
- Roadmap: [V5.3 Day 1](../ROADMAP_V5_3.md#5-第一周接管-specflow--三次短校准)
- Study state: [CURRENT.md](../CURRENT.md)

> Fill in `My prediction` before asking Codex for a root cause, correction, or
> patch. Codex assistance is recorded separately and is not learner ownership.

## Today's question

How does the current multi-agent path turn a requirement and repository into
validated, reviewable artifacts, and which controls are only declared rather
than enforced?

## Baseline identity

- Branch: `codex/v5-3-learning-contract`
- Commit: `55fdca728e4a3a9587d045f9842b49b166547a74`
- Working-tree status: clean at session start; this evidence card is the only
  tracked Day 1 administrative change after the learner requested issue
  recording. Benchmark output is under an ignored artifact directory.
- Environment notes: Python 3.12.10 via `uv`; latest verifiable remote CI for
  unchanged product code was successful on `main@1b441277`.

## My prediction


## My first call-chain drawing

- Learner blind reconstruction v0:
  `cli.main -> run_multi_agent -> EvidenceBundle -> Coordinator.plan ->`
  `MultiAgentScheduler -> Handoff -> Review -> Artifact`.
- Refinement retained for later defense: Handoffs occur between scheduled Agent
  stages rather than as one single post-Scheduler phase.

## Source evidence

| Claim | File | Symbol / line | Confirmed or unknown |
| --- | --- | --- | --- |
| CLI selects legacy or multi-agent execution | `src/specflow/cli.py` | `main`, lines 46-68 | Confirmed |
| Multi-agent runner collects bounded repository evidence | `src/specflow/runner_multi.py` | `run_multi_agent`, lines 86-122 | Confirmed |
| Evidence is serialized and DLP-scanned before Agent input | `src/specflow/runner_multi.py` | `run_multi_agent`, line 111 | Confirmed |
| Coordinator builds a structurally compiled and validated plan | `src/specflow/coordinator/coordinator.py` | `Coordinator.plan`, lines 90-164 | Confirmed; semantic correctness not established |
| Scheduler submits Agent executors and records results/timing | `src/specflow/coordinator/scheduler.py` | `MultiAgentScheduler.execute`, lines 114-183 | Confirmed and tested |
| Runtime handoffs validate identity/schema IDs and output hash | `src/specflow/handoff/validator.py` | `HandoffValidator`, lines 21-84 | Confirmed; `input_hash` validation unknown/absent |
| Multi-agent artifacts use atomic per-file writes and a final marker | `src/specflow/runner_multi.py` | `_safe_write`; `_finalize_run_directory`, lines 815-876 | Writer confirmed; consumer enforcement absent |

## Deferred issue ledger

> Recorded during Day 1 SURVEY at the learner's request. These entries are not
> approved patches. After Day 1, reproduce or test each candidate, decide
> whether it is a defect, an intentional boundary, or insufficient evidence,
> and only then propose the smallest solution.

| ID | Observed fact / candidate issue | Evidence | Current status | Resolution gate after Day 1 |
| --- | --- | --- | --- | --- |
| D1 | `read_file` is called for selected files, but its full `content` is not added to `EvidenceBundle`; Agent context is built from `search_code` line excerpts. This may omit multi-line control flow or surrounding function context. | `src/specflow/evidence/collector.py:100-118`; `src/specflow/evidence/models.py:117-139` | ENFORCED fact; quality impact untested | Add a focused case where the matched line is insufficient without surrounding context; compare the produced evidence and result before designing a change. |
| D2 | A no-match search could return an `EvidenceBundle` with empty `selected_files` and `excerpts`, after which the multi-agent runner continued without a no-evidence gate. T-072 now stops before Coordinator/Agent execution and persists `EVIDENCE_NOT_FOUND`. | `src/specflow/evidence/collector.py:87-148`; `src/specflow/runner_multi.py:105-139`; `tests/test_cli_multi_agent.py`; `tests/test_runs.py` | RESOLVED and TESTED by T-072 | Keep the zero-evidence regression and API persistence test; do not broaden this gate into D1 relevance/semantic scoring. |
| D3 | `RepositoryAnalystInput` gives `requirement`, `repository_evidence`, and `repository_root` default empty strings. `_validated_inputs` also converts context values with `str(...)`, so the input Schema does not establish non-empty business content. | `src/specflow/schema/models.py:16-26`; `src/specflow/runner_multi.py:593-620` | DECLARED structural validation; non-empty contract absent | Add direct boundary cases for missing, empty, `None`, and wrong-type inputs; decide which layer owns non-empty validation. |
| D4 | Receiver input Schema failures occur before scheduling, but the outer generic exception path persists `MULTI_AGENT_RUN_FAILED` rather than a specific input-Schema error code. | `src/specflow/runner_multi.py:551-558`; `src/specflow/runner_multi.py:388-405` | ENFORCED fail-closed behavior; diagnostic precision untested | Trigger the failure through the full runner and inspect manifest, trace, log, and exit code before deciding whether error classification must change. |
| D5 | `AgentIdentity.tool_permissions` is populated, but no runtime consumer or pre-Tool enforcement call site has been confirmed. Repository path and sensitive-file policy are separately enforced. | `src/specflow/agents/models.py:18-28`; `src/specflow/plan/planner.py:14-80`; `src/specflow/tools/repository_policy.py:106-239` | DECLARED; runtime enforcement UNKNOWN | Trace a Tool call from Agent identity to `ToolExecutor.execute`; keep UNKNOWN until an actual permission check is found or a bypass test proves the gap. |
| D6 | No Human Approval gate for Tool execution and no general Agent/Tool loop guard have been confirmed. The append-only `ReviewDecision` API and bounded revision count are different mechanisms. | `src/specflow/runs.py:203-217`; `src/specflow/policy/runtime_guard.py:127-134` | UNKNOWN | Search the complete execution path, then design permission/termination fault cases only if the hooks remain absent. |
| D7 | Multi-agent runs write a stage-summary `checkpoints.json`, but startup recovery explicitly marks interrupted Runs failed and does not retry or resume execution. | `src/specflow/runner_multi.py:469-480`; `src/specflow/runs.py:267-285` | Checkpoint artifact DECLARED; durable resume absent | Run one bounded crash experiment after Day 1 and verify whether completed work or side effects repeat before considering a resume design. |
| D8 | `AgentRunner` implements bounded retry but defaults to `max_retries=0`; `run_multi_agent` constructs it without passing the policy's retry values. | `src/specflow/agents/adapter.py:29-48`; `src/specflow/agents/adapter.py:83-101`; `src/specflow/runner_multi.py:160-171` | Retry mechanism DECLARED; multi-agent policy wiring unconfirmed | Inject a transient provider failure and record actual attempts, backoff, budget usage, and terminal state. |
| D9 | `PlanValidator` validates the compiled structure before semantic enrichment. `SemanticTaskBrief` checks agent identity/status but does not require non-empty task description, focus, hints, or scope, so an `ENRICHED` brief can still be semantically empty. | `src/specflow/coordinator/coordinator.py:90-120`; `src/specflow/plan/models.py:91-113`; `src/specflow/plan/enricher.py:73-102` | Structural plan TESTED; semantic-plan completeness untested | Add deterministic enrichment cases for empty, irrelevant, and malformed semantic briefs; define whether to reject, degrade, or continue. |
| D10 | The mock `ReviewAgent` deterministically returns `PASS`, while the portfolio benchmark marks a run passed when workflow state is completed and all six outputs are schema-validated. This does not establish semantic task quality. | `src/specflow/agents/review.py:36-50`; `src/specflow/evaluation/benchmark.py:164-203`; `src/specflow/evaluation/rubric.py:15-25` | Contract path TESTED; semantic quality gate absent from mock benchmark | Keep Mock as contract evidence; evaluate real outputs separately with fixed cases, evidence-validity checks, human rubric, and later Dev/Holdout results. |
| D11 | `AgentHandoff.input_hash` records the requirement hash, but no runtime consumer recomputes or compares it. `HandoffValidator.validate_payload` verifies only the referenced output envelope and `output_hash`, so a requirement/output-version mismatch is not detected by this field. | `src/specflow/runner_multi.py:704-715`; `src/specflow/handoff/models.py:17-24`; `src/specflow/handoff/validator.py:59-84` | `input_hash` DECLARED; output integrity TESTED; input lineage unverified | Add a tamper case that changes the requirement between upstream output and receiver input; define the canonical receiver-input envelope and validate its hash before scheduling. |
| D12 | After the bounded revision, a second `REJECT` transitions the workflow to `completed` with `revision_exhausted=true`. The mock portfolio benchmark currently treats `completed` plus six schema-valid outputs as passed without checking the final review decision or revision exhaustion. | `src/specflow/runner_multi.py:248-340`; `src/specflow/evaluation/benchmark.py:188-203`; `tests/test_cli_multi_agent.py:186-239` | Terminal semantics TESTED; benchmark business-acceptance signal absent | Add a final-REJECT benchmark case and decide whether contract success and business acceptance need separate reported fields rather than changing workflow semantics. |
| D13 | The writer creates `artifact-integrity.json` and writes `_COMPLETE` last, but current benchmark and Run API artifact listing do not require `_COMPLETE` or verify the recorded artifact hashes before accepting/listing a directory. | `src/specflow/runner_multi.py:848-876`; `src/specflow/evaluation/benchmark.py:164-191`; `src/specflow/runs.py:188-201`; `tests/test_cli_multi_agent.py:83-106` | Write-side integrity TESTED; read-side enforcement absent | Create interrupted-write and tampered-file cases against every artifact consumer; define one shared read-side integrity validator before changing acceptance behavior. |

### Rejected design shortcut

- Do not use Spring's singleton early-reference / three-level-cache mechanism
  to accept an Agent execution cycle. Spring addresses object-reference
  construction; an Agent cycle lacks prerequisite outputs. Keep fail-fast DAG
  cycle detection in `src/specflow/plan/compiler.py:44-84`. If a real cycle is
  encountered, compare shared earlier context, staged independent drafts, and
  bounded revision instead.

## Tool/runtime hook inventory

Record `unknown` when the repository does not prove that a hook exists. Do not
turn a roadmap target into an implementation claim.

| Hook | File | Symbol / line | Confirmed behavior or unknown |
| --- | --- | --- | --- |
| Tool schema | `src/specflow/mcp/adapter.py`; `src/specflow/tools/repository_tools.py` | `_INPUT_SCHEMAS`; Tool `execute` validators | TESTED argument/schema validation |
| Permission / policy | `src/specflow/tools/repository_policy.py`; `src/specflow/agents/models.py` | `RepositoryAccessPolicy`; `AgentIdentity.tool_permissions` | Path/sensitive policy TESTED; per-Agent Tool permission DECLARED only |
| Human approval | `src/specflow/runs.py` | `RunService.record_decision`, lines 210-217 | Tool approval gate UNKNOWN; append-only review decision is not execution approval |
| Loop guard / termination | `src/specflow/policy/runtime_guard.py` | `consume_revision`, lines 127-134 | Revision bound TESTED; general Agent/Tool loop guard UNKNOWN |
| RuntimeGuard | `src/specflow/policy/runtime_guard.py` | `RuntimeGuard` | TESTED time/call/token/parallel/revision/artifact budgets |
| Retry | `src/specflow/agents/adapter.py`; `src/specflow/runner_multi.py` | `AgentRunner`; construction lines 160-171 | Mechanism DECLARED; multi-agent runtime defaults to zero retries |
| Checkpoint / resume | `src/specflow/runner_multi.py`; `src/specflow/runs.py` | checkpoint write lines 469-480; recovery lines 267-285 | Checkpoint artifact TESTED; durable resume absent |
| Trace | `src/specflow/runner_multi.py` | `_build_trace_tree`, lines 752-812 | TESTED stage/Agent timing artifacts |
| DLP | `src/specflow/tools/sanitization.py`; `src/specflow/runner_multi.py` | `final_dlp_scan`; lines 111 and 648-657 | TESTED evidence/output sanitization |

## Failure I created


## Root cause I located


## My design decision

- Learner decision (Day 1): enforce per-Agent Tool permissions centrally at
  the `ToolExecutor` boundary, analogous to an AOP interception point, to keep
  policy consistent, reduce duplicated authorization logic, and make later
  policy changes reviewable in one place. This design is not yet approved for
  implementation. Its required invariant is that every Tool entry point must
  pass through the same enforcement boundary and caller identity must come
  from trusted execution context rather than caller-controlled Tool arguments.

## Patch I reviewed


## Verification commands and results

| Command | Exit code | Key result | Evidence path |
| --- | ---: | --- | --- |
| `uv run python --version` | 0 | Python 3.12.10 | terminal output |
| `uv run pytest -q -p no:cacheprovider` | 0 | 771 passed, 3 skipped, 3 known warnings; 13.41s pytest time | terminal output |
| `uv run ruff check . --no-cache` | 0 | All checks passed; one non-failing invalid `# noqa` warning | terminal output |
| `uv run ruff format --check .` | 0 | 208 files already formatted | terminal output |
| `uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/day1-baseline-20260906-1 --baseline artifacts/day1-baseline-20260906-1/baseline.json` | 0 | 12-case deterministic Mock benchmark passed | `artifacts/day1-baseline-20260906-1/` |
| `git diff --no-index --exit-code benchmarks/results/mock-baseline.json artifacts/day1-baseline-20260906-1/baseline.json` | 0 | Generated normalized baseline matches committed baseline | generated baseline path above |

## Test / Eval interpretation

- Learner interpretation: a passing Mock run proves repeatable workflow,
  Handoff, Schema, and Artifact contracts; it does not prove real-LLM semantic
  analysis quality.

## Day 1 能力结果

Day 1 帮助我建立了第一版 SpecFlow 项目心智模型。这不代表我已经普遍掌握 Agent 工程，也不代表我已经具备独立维护 SpecFlow 的能力。

### 已验证或已有直接学习者证据

| 能力 | 当前状态 | 学习者证据 |
| --- | --- | --- |
| 说明 SpecFlow 的基本用途 | 已验证（仅限本项目） | 能说明系统接收仓库路径和开发需求，搜索代码证据并输出可审查结果。 |
| 区分 Mock 与真实模型证据 | 已验证（仅限本项目） | 能说明 Mock 证明流程、Schema、Handoff、Artifact 等工程合同，但不能证明真实 LLM 的语义质量。 |
| 提出 Tool 权限执行位置 | 已验证的设计决策 | 学习者提出在 `ToolExecutor` 统一执行单个 Agent 的权限，并用 AOP 切面解释统一治理、减少重复和方便调整。 |

### 正在练习

| 能力 | 当前状态 | 已达到的程度 | 仍需补强 |
| --- | --- | --- | --- |
| 追踪主调用链 | C1 练习中 | 能重建 `cli.main -> run_multi_agent -> EvidenceBundle -> Coordinator.plan -> MultiAgentScheduler -> Handoff -> Review -> Artifact`。 | 仍需减少对提示的依赖，并能为关键调用边独立给出 `path:line`。 |
| 区分结构正确与业务正确 | C2 练习中 | 能说明 `PlanValidator` 可以证明结构合法，但不能证明计划内容或业务结果正确。 | 需要在新案例中独立识别“Schema 合法但内容错误”。 |
| 区分声明与真实执行 | C2 练习中 | 能使用“已声明、已执行、已测试、未知”判断 `tool_permissions`、`input_hash`、`_COMPLETE` 等控制。 | 需要在陌生模块中独立完成一次消费者追踪。 |
| 解释失败终态 | C2 练习中 | 已接触技术失败 `failed + exit 3` 与业务拒绝 `completed + revision_exhausted=true` 的区别。 | 仍需在没有提示时准确使用状态名称，并说明为什么不能混为一谈。 |
| 审查完整性边界 | C2 练习中 | 能理解“写入端生成哈希和完成标记”不等于“读取端已经执行验证”。 | 需要亲自完成一次 Artifact 篡改实验，并解释消费者的行为。 |

### 尚未验证，不能写成已经掌握

- C3 工程维护：D2 的测试、实现、回归和提交由 Codex 完成；学习者尚未独立复现、定位并实现一个补丁。
- C4 架构设计：已有一条集中式权限决策，但尚未完整比较两个候选方案的约束、取舍和故障路径。
- C5 创造：尚未根据需求独立完成一个可维护的 Agent 工程闭环。
- 独立测试设计、Trace 定位、故障注入、数据库建模、checkpoint/resume 和 Live Provider 质量评估均未验证。

### Day 1 结束后能够做什么

- 面对陌生 Agent 仓库时，先寻找入口、Evidence、计划、执行、Handoff、Review 和 Artifact，不再从目录树开始逐个阅读文件。
- 看到 `permission`、`retry`、`checkpoint`、`hash` 等字段时，继续追踪运行时消费者，不把“代码中存在”误认为“功能已经生效”。
- 阅读测试或 benchmark 结果时，能够区分工程合同通过与业务、语义质量通过。
- 对无法从源码或实验证明的结论标记为“未知”，并把下一步改写成可以复现的验证问题。

## What surprised me

- A field or artifact can exist without being enforced by any consumer
  (`input_hash`, per-Agent `tool_permissions`, `_COMPLETE`).
- `completed` means the controlled workflow finished; it does not necessarily
  mean the final business review passed. A second `REJECT` is represented by
  `completed + revision_exhausted=true`, while technical execution failure is
  represented by `failed` and CLI exit code 3.

## Alternative design and trade-off


## What Codex helped with

- Ran and compressed the deterministic baseline commands; indexed source
  symbols; proposed counterexamples; distinguished DECLARED, ENFORCED, TESTED,
  and UNKNOWN controls. These are scaffolding and are not counted as learner
  ownership without the learner's own explanation.

## Can I explain it without notes?

- [x] I can draw the main chain without opening documentation.
- [x] I can distinguish confirmed repository facts from assumptions.
- [x] I can identify where Tool permission should be enforced without claiming
  that an absent hook already exists.
- [x] I can explain at least one failure mode and its legal terminal state.

## Next action

- Await an explicit mode/day transition. Before any patch, use FAULT/REVIEW to
  reproduce and classify the deferred D1-D13 entries; do not batch-fix them
  merely because they were discovered during SURVEY.
