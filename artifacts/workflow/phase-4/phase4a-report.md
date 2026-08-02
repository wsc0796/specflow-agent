# Phase 4A — Live Case 只读准备报告

窗口:phase_4a_live_prep · 分支:fix/phase-4a-live-case-prep · Base commit:bc76214
状态:**PASS(准备完成;冻结草案全部 PENDING_USER_APPROVAL,未定案)**

## 1. 现状盘点(全部基于 bc76214 代码)

### 1.1 执行策略与预算
- `src/specflow/policy/models.py::ExecutionPolicy`:默认 `max_wall_time_seconds=300`、`max_provider_call_attempts=24`(已批准校准)、`max_parallel_agents=3`、`max_parallel_provider_calls=3`、`max_revisions=1`;`max_llm_calls` 是 deprecated 别名,显式传入时会驱动 provider-attempt 预算。
- `TokenPolicy` 默认值:`max_run_input_tokens=50000`、`max_run_output_tokens=12000`、`max_run_total_tokens=62000`、`max_agent_input_tokens=10000`、`max_agent_output_tokens=3000`、`reserved_retry_tokens=6000`。
- `src/specflow/policy/defaults.py::DEFAULT_POLICY` 是编译期常量;**当前没有任何环境变量 / CLI / API 入口可以覆盖 Run 级预算**。
- `src/specflow/policy/runtime_guard.py::RuntimeGuard`:`reserve_provider_attempt` 在同一临界区完成 wall-clock、并行上限、attempt 预算检查;`release_provider_attempt` 结算 token(usage 缺失 → `TOKEN_USAGE_UNAVAILABLE`,绝不记 0);`snapshot()` 已输出 limits + tokens + provider/agent 计数。
- `src/specflow/policy/budget.py::ExecutionBudget` 是 legacy 计数,仅 legacy `runner.py` 使用,不在多 Agent 运行时路径。

### 1.2 配置入口
- CLI `src/specflow/cli.py`:`specflow run` 只有 `--repo/--requirement/--output/--provider/--model/--max-files/--mock/--mode`;无预算/token 参数。
- API `src/specflow/main.py` + `src/specflow/runs.py`:`RunCreate` 只有 `project_id/requirement`;`policy_hash=DEFAULT_POLICY.policy_hash()`,无预算覆盖字段。
- Provider `src/specflow/llm/providers/config.py`:`SPECFLOW_LLM_BASE_URL`、`SPECFLOW_LLM_API_KEY`、`SPECFLOW_LLM_MODEL`、`SPECFLOW_LLM_TIMEOUT_SECONDS`(1–600s)。

### 1.3 Manifest 与失败证据
- `runner_multi.py`:`manifest.json` 已含 `budget_snapshot`、policy 摘要(`max_wall_time_seconds`、`max_llm_calls`)、制品 SHA-256 与 revision 制品;planning/runtime 失败都会写 FAILED manifest + budget snapshot + partial trace。

### 1.4 Claim 现状(claim-evidence-ledger.md)
- 已解锁:task brief 影响真实请求、finding-driven revision、provider 调用统一受控、token 统计准确。
- 仍 REJECTED:`Default provider-attempt budget supports the live path`(默认 10 < 正常 live 路径 12 次 attempts,见 DECISION_D1)。
- 仍 BLOCKED:live validation、multi-agent quality improvement、production-ready。

## 2. 定案任务改动点预估(只分析,不实现)

任务文本:为 SpecFlow 增加 **Run 级 Token 预算配置**,涉及配置 Schema、RuntimeGuard、manifest、API、CLI、测试和文档。

| # | 改动点 | 涉及文件 | 说明 |
| --- | --- | --- | --- |
| 1 | 配置 Schema | `policy/models.py`、`policy/defaults.py` | 新增/扩展 Run 级 token budget 配置模型(输入/输出/总、agent 级、retry 预留),strict 校验;保留默认值不变 |
| 2 | RuntimeGuard 强制 | `runtime_guard.py` | fail-closed 执行;错误码细分 `INPUT_TOKEN_BUDGET_EXCEEDED` / `OUTPUT_TOKEN_BUDGET_EXCEEDED` / `TOTAL_TOKEN_BUDGET_EXCEEDED` / `TOKEN_USAGE_UNAVAILABLE`(当前为统一 `TOKEN_BUDGET_EXCEEDED`) |
| 3 | manifest | `runner_multi.py` | 记录配置值与 enforcement 结果(现有 `budget_snapshot` 可复用) |
| 4 | API | `runs.py` | `RunCreate` 增加可选 token 预算字段,经 `PolicyValidator` + hard limit 校验,纳入 `policy_hash` |
| 5 | CLI | `cli.py` | `specflow run` 增加对应参数或环境变量 |
| 6 | 测试 | `tests/` | policy 校验、guard 强制、API/CLI 接线、manifest 一致性;全量回归 + benchmark baseline 不变 |
| 7 | 文档 | `README.md`、Live guide | 配置说明、边界、未支持主张清单 |

## 3. 风险与未决问题
- **DECISION_D1(已批准)**:默认 `max_provider_call_attempts` 校准为 **24**(2026-08-02 批准);48 不作为全局默认,仅允许 Live/Evaluation/实验显式配置。
- **Live 运行费用上限缺失**:仓库没有费用记账,只能用 token + wall-clock 作为代理上限;Phase 4B 需用户批准模型与最大费用边界。
- **API 认证不在 verified base**:`api_security.py` 只存在于主工作区未提交改动中,bc76214 不含;live 阶段仅限本地单用户。
- 错误码粒度与 Phase 3F taxonomy 存在差距(见改动点 2)。
- Live artifact 的完整性与可复现性依赖 Phase 4C 独立审计,本阶段不声称 live 完成。

## 4. 结论
Phase 4A 只读准备完成:现状盘点、改动点预估、Live case 草案(frozen-config 全部 PENDING_USER_APPROVAL)、Phase 4B 审批清单均已产出。未改任何代码,未调用任何模型,未触碰 benchmark baseline。
