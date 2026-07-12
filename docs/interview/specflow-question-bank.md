# SpecFlow Agent — 项目专属面试题库

> 每题 5 段：30 秒回答 → 项目实现 → 代码位置 → 测试证据 → 当前限制

---

## 架构类

### Q1：为什么使用多 Agent 而不是单个 LLM？

**30 秒回答：**
单 Agent 在复杂需求上容易遗漏风险和测试覆盖。我把分析拆成 6 个职责独立的 Agent——仓库分析、设计、测试策略、风险审查、综合和终审——其中设计/测试/风险三个 Specialist 并行执行，Review 做最终质量门禁。A/B 对比证明多 Agent 在风险覆盖和测试完整度上优于单链路。

**项目实现：**
- 固定 6 Agent 拓扑：RepositoryAnalyst → (Design ‖ TestStrategy ‖ RiskReview) → Synthesis → Review
- Coordinator 通过 `StructuralDelegationSpec` 确定性生成 Agent 集合、依赖图和执行阶段
- `PlanCompiler` 用 Kahn 算法做 DAG 验证和拓扑排序，编译出 `execution_stages`
- LLM 只补充 `SemanticTaskBrief`（任务描述、分析重点），无权改变拓扑

**代码位置：**
- `src/specflow/coordinator/coordinator.py` — Coordinator 编排入口
- `src/specflow/plan/planner.py` — `FIXED_TOPOLOGY_AGENTS` + `DeterministicPlanner`
- `src/specflow/plan/compiler.py` — `PlanCompiler`（Kahn 算法 DAG 编译）
- `src/specflow/coordinator/scheduler.py` — `MultiAgentScheduler`（阶段串行、阶段内并行）

**测试证据：**
- `tests/test_structural_plan.py` — 13 tests（拓扑正确性、DAG 验证、阶段分组）
- `tests/test_coordinator.py` — 29 tests（端到端编排）
- `docs/evaluations/M6-ab-comparison.md` — A/B 对比数据

**当前限制：**
固定拓扑，不支持根据需求类型动态选择 Agent 组合；6 个 Agent 是 MVP 硬编码的。

---

### Q2：为什么不用 LangGraph？

**30 秒回答：**
LangGraph 适合需要灵活图遍历和动态路由的场景。SpecFlow 的需求分析任务有明确的阶段依赖关系——分析 → 设计/测试/风险 → 综合 → 审查——用确定性 Coordinator 比用图框架更可控、更可审计。而且自建编排层能证明我理解 Agent 调度的底层机制，不只是会用框架。

**项目实现：**
- `AgentExecutor`（Legacy）和 `Coordinator`（Multi-Agent）都是纯 Python 实现
- 状态机：`WorkflowState`（6 状态线性）+ `MultiAgentWorkflowState`（9 状态含 Revision）
- 并行用 `concurrent.futures.ThreadPoolExecutor`，没有外部依赖
- `AgentDependency` 是逻辑真相源，`execution_stages` 由 `PlanCompiler` 编译生成

**代码位置：**
- `src/specflow/workflow/engine.py` — 旧状态机
- `src/specflow/coordinator/state_machine.py` — 新状态机
- `src/specflow/coordinator/scheduler.py:48-153` — 并行调度实现

**测试证据：**
- `tests/test_plan_compiler.py` — DAG 编译正确性
- `tests/test_scheduler.py` — 并行执行验证

**当前限制：**
不支持动态拓扑；如果需要运行时根据中间结果改变 Agent 组合，需要扩展 Coordinator。

---

### Q3：如何划分 Agent 职责？

**30 秒回答：**
按"输入独立性"划分——能独立消费同一份仓库分析结果、不需要互相等待的职责就并行为不同 Agent。仓库分析是前置依赖，设计/测试策略/风险审查三者可以并行（都只依赖分析结果），综合需要等三个都完成，终审是最后门禁。

**项目实现：**
- `AgentRole` 枚举定义了 6 种角色，每种有独立的 `AgentIdentity`、`prompt_id`、`input_schema_id`、`output_schema_id` 和 `tool_permissions`
- RepositoryAnalyst 有工具权限（list_files/search_code/read_file），其他 Agent 默认不调工具
- Stage 2 的三个 Agent（Design/TestStrategy/RiskReview）消费相同的 `RepositoryAnalyst` 输出，无互相依赖

**代码位置：**
- `src/specflow/agents/models.py` — `AgentRole`、`AgentIdentity`
- `src/specflow/plan/planner.py` — `FIXED_TOPOLOGY_AGENTS`
- `src/specflow/agents/repository_analyst.py` 等 — 各 Agent 实现

**测试证据：**
- `tests/test_agent_models.py` — Agent 身份和角色验证
- `tests/test_agent_implementations.py` — 6 个 Agent 身份唯一性

**当前限制：**
Agent 职责边界通过约束文档定义，未在代码中做硬性校验（如"Design Agent 禁止输出风险结论"）。

---

### Q4：如何保证 Agent 调度权不被 LLM 夺走？

**30 秒回答：**
这是 M6-ADR-001 的核心设计决策。`StructuralDelegationSpec` 中的所有执行字段（Agent 集合、依赖图、并行分组、Token 预算、工具权限、超时、返工上限）全部由确定性代码生成。LLM 只能填充 `SemanticTaskBrief` 中的建议性字段（task_description、analysis_focus、evaluation_hints）。LLM 填充失败时使用规则默认值继续执行，不作为单点故障。

**项目实现：**
- `DeterministicPlanner.generate()` → `StructuralDelegationSpec`（纯代码，不调 LLM）
- `PlanCompiler.compile()` → `CompiledStructuralPlan` + `structure_hash`
- `SemanticPlanEnricher.enrich()` → LLM 只补充语义字段，异常时 `degraded_default()`
- `PlanValidator` 静态校验：Agent 集合一致性、阶段内无依赖、Schema ID 存在

**代码位置：**
- `src/specflow/plan/planner.py:85-130` — 确定性规划器
- `src/specflow/plan/enricher.py:48-67` — 语义增强（含降级）
- `docs/superpowers/specs/2026-07-12-m6-multi-agent-design.md` — M6-ADR-001 完整记录

**测试证据：**
- `tests/test_structural_plan.py::test_spec_has_no_compiled_fields` — 证明 LLM 无权修改结构
- `tests/test_semantic_enricher.py` — 9 tests（含 LLM 失败降级）

**当前限制：**
规则默认的任务描述较泛化，未根据 Agent 角色做差异化默认值。

---

## 稳定性类

### Q5：如何保证 Agent 输出稳定？

**30 秒回答：**
我没有直接信任模型输出。LLM 原始 JSON 先经过 Pydantic Schema 校验（SchemaRegistry），失败时经过 JSON Repair → 定向重试 → Rule Baseline Fallback 三层防线。最终状态（success/degraded/failed）和 Fallback 级别全部写入 Trace 和 Artifact，可审计。

**项目实现：**
- Legacy Worker：`FallbackManager` 三层（Retry → JSON Repair → Rule Baseline）
- Multi-Agent：`SchemaRegistry` + `AgentRunner` 的 `schema_validated` 状态追踪
- `FallbackManager` 按 `FallbackLevel`（RETRY / JSON_REPAIR / RULE_BASELINE）逐级降级
- 每级结果记录在 `LLMTrace` 和 `AgentTraceSpan` 中

**代码位置：**
- `src/specflow/fallback/manager.py` — `FallbackManager`
- `src/specflow/fallback/strategies.py` — Retry、JSON Repair、Rule Baseline
- `src/specflow/workers/analyze.py:197-247` — Worker 中的完整 LLM 调用链路
- `src/specflow/agents/adapter.py:62-113` — AgentRunner 的 Schema 校验和降级

**测试证据：**
- `tests/test_analyze_worker.py` — 包含 degraded/fallback 场景
- `tests/test_agent_adapter.py::test_runner_degraded_on_llm_failure` — LLM 失败降级

**当前限制：**
Multi-Agent 侧 Retry 和 JSON Repair 尚未完整接入 FallbackManager；当前 Schema 校验失败后 raw pass-through（M8 修复）。

---

### Q6：如何处理 LLM 返回非法 JSON？

**30 秒回答：**
分三层处理。第一层：temperature=0.0 + `response_format="json"` 降低概率。第二层：如果返回了 Markdown 包裹的 JSON 或夹杂解释文字，用正则提取最外层 `{...}` 做 JSON Repair。第三层：JSON 结构和字段校验（Pydantic `model_validate`），失败则用规则生成基线输出并标记 `degraded=True`。

**项目实现：**
- LLMRequest 固定 `response_format="json"` 和 `temperature=0.0`
- `FallbackManager` 的 `_try_json_repair()` 用正则 `r'\{[\s\S]*\}'` 提取首尾花括号
- `WorkerResult` 和 `AgentRunner` 返回 `degraded=True` + `requires_review=True`
- 降级输出包含明确的 `rule_baseline` fallback 标记

**代码位置：**
- `src/specflow/fallback/manager.py` — `_try_json_repair()`
- `src/specflow/workers/analyze.py:233-237` — parse-or-degrade 逻辑
- `src/specflow/agents/adapter.py:84-99` — Schema 校验路径

**测试证据：**
- `tests/test_fallback.py` — JSON Repair 和 Rule Baseline 测试
- Live Artifact：`analysis.json` 中 `degraded=True` 标记

**当前限制：**
JSON Repair 只能处理"最外层花括号"情况，多层嵌套 JSON 中的注释或尾逗号会导致提取不完整。

---

### Q7：Agent 崩溃或 API 超时后如何排查？

**30 秒回答：**
每个 Agent 都有独立的 `AgentTraceSpan`（包含 agent_id、stage、模型、延迟、Token、状态、Fallback 级别）。运行时异常会触发 `_persist_failed_run()`，写入 FAILED manifest（含完整状态历史、已完成阶段数、错误详情）和部分 Trace。所有时序数据带 UTC 时间戳，可以按 stage → agent 层级追溯。

**项目实现：**
- `AgentTraceSpan`：span_id、agent_id、stage、parent_span_id、timing、model、tokens、status、fallback_level、revision_round
- `_persist_failed_run()`：异常时写 manifest.json + traces.json + agent-outputs.json
- `MultiAgentWorkflowEngine`：维护完整的状态转换历史

**代码位置：**
- `src/specflow/trace/models.py` — `AgentTraceSpan`
- `src/specflow/runner_multi.py:212-225` — 异常捕获和 FAILED 持久化
- `src/specflow/runner_multi.py:488-542` — `_persist_failed_run()`

**测试证据：**
- `tests/test_agent_trace.py` — TraceSpan 构建和序列化
- Live 案例：第一次 DeepSeek 运行时 Review Agent 格式不匹配，FAILED manifest 记录了完整 history

**当前限制：**
原始异常消息直接写入 manifest，未做脱敏；Provider URL 等敏感信息可能在错误详情中泄露。

---

### Q8：如何防止多 Agent 无限循环？

**30 秒回答：**
Coordinator 拥有流程控制权，LLM 无权增加 Agent、改变依赖或提高返工轮数。Review 最多触发一次 Revision（`RevisionController`，`max_total_rounds=1`），Revision 只能定向返回被 Review 标记的 Agent。第二次 Review 无论是 PASS 还是 REJECT，都正常进入 COMPLETED 并标记 `revision_exhausted=true`，不会进入 FAILED——因为业务拒绝不是系统故障。

**项目实现：**
- `RevisionPolicy.max_total_rounds = 1`（硬编码，LLM 不可改）
- `RevisionController.exhausted`：`round > max_total_rounds` 时返回 None
- `_review_decision()` 提取 Review 结果时，不仅检查 `decision` 字段，还搜索 `conclusion`/`verdict`/`recommendation` 等 LLM 常见回复格式
- 第二次 REJECT → COMPLETED + `revision_exhausted=true`（不是 FAILED）

**代码位置：**
- `src/specflow/agents/models.py:89-110` — `RevisionPolicy`
- `src/specflow/coordinator/revision.py` — `RevisionController`
- `src/specflow/runner_multi.py:169-212` — Revision 流程
- `src/specflow/runner_multi.py:324-368` — `_review_decision()` + `_normalize_decision()`

**测试证据：**
- `tests/test_revision_controller.py` — 14 tests（含 exhausted 行为）

**当前限制：**
`_normalize_decision` 的决策规范化是启发式的，边缘情况下可能将合法 REJECT 误判为 PASS。

---

### Q9：如何做有界返工？

**30 秒回答：**
Review Agent 返回 REJECT 时，`RevisionController` 创建结构化 `RevisionTask`（包含目标 Agent、Review 发现、修正指令和轮次号），只将任务发给被 Review 标记的那个 Agent，不影响其他已完成 Agent。返工完成后重新走 Synthesis → Review。最多一轮。超过后标记 `revision_exhausted=true`，进入 COMPLETED。

**项目实现：**
- `RevisionTask`：revision_id、target_agent_id、target_role、review_finding、instruction、round_number
- `RevisionController.create_revision_task()`：检查 exhausted + is_revisable，返回 None 或 RevisionTask
- 返工流程：REVISING → 被标记 Agent 重执行 → SYNTHESIZING → REVIEWING → 最终判断

**代码位置：**
- `src/specflow/coordinator/revision.py:20-62` — `RevisionTask` + `RevisionController`
- `src/specflow/runner_multi.py:170-212` — Revision 执行流

**测试证据：**
- `tests/test_revision_controller.py::test_exhausted_after_max_rounds`
- `tests/test_cli_multi_agent.py::test_reject_runs_one_revision_then_completes_when_limit_is_exhausted`

**当前限制：**
Revision 指令是固定文本，未将 Review 的具体发现动态注入 RevisionTask。

---

## 工具与安全类

### Q10：如何选择工具并避免选错？

**30 秒回答：**
SpecFlow 不是让 Agent 自由选择工具。`AgentIdentity` 中预先声明每个 Agent 的 `tool_permissions`（frozenset），ToolExecutor 在运行前校验。RepositoryAnalyst 可以调 list_files/search_code/read_file，其他 5 个 Agent 默认不调工具——它们消费已采集的 Evidence。这样避免了"LLM 决定调哪个工具"的不确定性。

**项目实现：**
- `AgentIdentity.tool_permissions: frozenset[str]` — 静态权限声明
- `ToolRegistry` + `ToolExecutor`：执行前校验 Tool 是否已注册、参数是否合法
- `RepositoryToolSet`：只读工具（list_files/search_code/read_file），绑定单一仓库根目录
- 工具调用记录写入 `tool-calls.json` 和 `sources.json`

**代码位置：**
- `src/specflow/tools/registry.py` — `ToolRegistry`
- `src/specflow/tools/executor.py` — `ToolExecutor`
- `src/specflow/tools/repository_tools.py` — 只读仓库工具

**测试证据：**
- `tests/test_tool_registry.py` / `tests/test_tool_executor.py`
- `tests/test_repository_tools.py` — 路径穿越、二进制、敏感文件拒绝

**当前限制：**
工具权限校验在 Agent 级别，未在每次工具调用时动态检查——如果 Agent 的权限在运行时被篡改，不会被检测到。

---

### Q11：如何限制 Agent 权限？

**30 秒回答：**
SpecFlow 所有 Agent 默认只读。RepositoryToolSet 绑定一个经过 `resolve()` 的仓库根目录，阻止 `..` 路径穿越、Symlink 追踪、二进制文件和敏感文件（`.env`、`.git/`、密钥文件）的读取。没有 Shell 工具、没有文件写工具、没有 Git 工具。Agent 权限通过 `AgentConstraints` 中的 `allowed_paths` 和 `denied_paths` 进一步限制。

**项目实现：**
- `RepositoryToolSet`：`_validate_path()` 检查路径是否在 repo root 内
- `_is_safe_to_read()`：拒绝二进制、超大文件、敏感文件名
- `AgentConstraints.allowed_paths` / `denied_paths`：路径级访问控制
- `tool_permissions`：声明式工具白名单

**代码位置：**
- `src/specflow/tools/repository_tools.py:40-80` — 路径验证和安全检查
- `src/specflow/tools/repository_policy.py` — 安全策略
- `src/specflow/agents/models.py:63-82` — `AgentConstraints`

**测试证据：**
- `tests/test_repository_tools.py::test_reject_path_traversal`
- `tests/test_repository_tools.py::test_reject_sensitive_files`

**当前限制：**
`allowed_paths` 和 `denied_paths` 在 AgentConstraints 中定义但下游路径匹配逻辑尚未完整实现。

---

### Q12：如何保证 Agent 之间的数据交接可靠？

**30 秒回答：**
Agent 间交接不是隐式的"把上一个输出丢给下一个"，而是经过 `HandoffValidator` 的结构化契约校验。每个 `AgentHandoff` 包含发送方的 `source_output_schema_id` 和接收方的 `target_input_schema_id`，校验器比对 Schema ID 是否一致；payload 通过 `canonical_json_bytes()` 计算 SHA-256 hash，确保创建端和校验端用同一序列化规则。中文输出的 hash 一致性已在 DeepSeek Live Run 中验证。

**项目实现：**
- `AgentHandoff`：handoff_id、from_agent_id、to_agent_id、source_output_schema_id、target_input_schema_id、payload_ref、input_hash、output_hash
- `HandoffValidator.validate()`：Schema ID 比对
- `HandoffValidator.validate_payload()`：payload 存在 + agent_id 匹配 + output 格式 + output_hash 一致
- `canonical_json_bytes()`：统一 `ensure_ascii=False` + `separators=(",",":")` + `sort_keys=True`

**代码位置：**
- `src/specflow/handoff/models.py` — `AgentHandoff`
- `src/specflow/handoff/validator.py` — `HandoffValidator`
- `src/specflow/plan/hash_utils.py:18-26` — `canonical_json_bytes()`

**测试证据：**
- `tests/test_handoff_validator.py` — Schema 不匹配和 Hash 不匹配的拒绝
- Live Run：7 条 Handoff 全部通过校验（DeepSeek 中文输出）

**当前限制：**
Synthesis Agent 接收 3 个 Specialist 输出时，输入 Schema 尚未定义为显式聚合模型。

---

## 评测与成本类

### Q13：如何评估 Agent 系统好不好？

**30 秒回答：**
不是跑通了就完了。我保留了旧的 Analyze→Generate→Review 线性管道作为 baseline，用完全相同的仓库、需求、Provider 条件，对比 Legacy 和 Multi-Agent 在 10 个维度上的差异：需求覆盖、文件引用准确率、风险覆盖、测试完整度、Review 发现数、人工修改量、Token 成本、端到端延迟、Fallback 率和 Revision 次数。这是"为什么多 Agent 更好"的数据证据。

**项目实现：**
- `ABComparisonResult`：legacy_scores、multi_agent_scores、improvement (delta)
- 10 个 `RubricDimension`：requirement_coverage、file_reference_rate、risk_coverage、test_completeness、review_findings、human_edit_reduction、token_cost、end_to_end_latency、fallback_rate、revision_count
- `RunMetrics` + `AgentMetrics`：统一指标采集（Token、耗时、Fallback、Schema、文件命中、并行加速比）

**代码位置：**
- `src/specflow/evaluation/metrics.py` — `RunMetrics` + `AgentMetrics`
- `src/specflow/evaluation/rubric.py` — `RubricDimension`
- `evaluation/multi_agent_runner.py` — `ABComparisonResult` + `compare_legacy_vs_multi_agent`

**测试证据：**
- `tests/test_evaluation_multi_agent.py` — A/B 对比框架测试
- `docs/evaluations/M6-ab-comparison.md` — Mock A/B 数据

**当前限制：**
A/B 评测框架已建立，Live Provider 的 3 案例数据待采集（T-034）。

---

### Q14：如何统计 Token 和延迟？

**30 秒回答：**
每次 LLM 调用都记录在 `LLMTrace` 或 `AgentTraceSpan` 中。多 Agent 模式额外产出 `metrics.json`，包含每个 Agent 的 input/output tokens、wall_time、并行加速比。Token 目前从 LLM Response 的 `usage` 字段提取，延迟从 Python `time.monotonic()` + Agent submission/completion 时间戳计算。并行加速比 =（Design + Test + Risk 各自耗时之和）/（实际阶段墙钟）。

**项目实现：**
- `LLMTrace`：input_tokens、output_tokens、latency_ms — 每次 LLM 调用
- `AgentTraceSpan`：stage_started_at、agent_submitted_at、agent_completed_at — Stage 级和 Agent 级时间戳
- `RunMetrics`：聚合的 total_tokens、wall_time_ms、parallel_speedup
- `AgentMetrics`：per-agent 的 input_tokens、output_tokens、duration_ms

**代码位置：**
- `src/specflow/trace/models.py` — `LLMTrace`、`AgentTraceSpan`
- `src/specflow/evaluation/metrics.py` — `RunMetrics`、`AgentMetrics`
- `src/specflow/runner_multi.py:651-669` — `_build_multi_agent_metrics()` 中的并行加速比计算

**测试证据：**
- `tests/test_agent_trace.py` — TraceSpan 字段完整性
- Live Artifact：`metrics.json` 中的 agent_metrics 数组

**当前限制：**
Token 采集依赖 Provider 返回的 `usage` 字段，DeepSeek v4-flash 返回的 usage 格式可能为 0；`referenced_file_count` 仍为占位值 0（需解析 Agent 输出提取文件引用）。

---

### Q15：如何证明多 Agent 比单 Agent 更值得？

**30 秒回答：**
用数据说话。Legacy 和 Multi-Agent 在相同仓库、相同需求、相同 Provider 条件下对比。Multi-Agent 在风险覆盖和测试完整度上优于 Legacy，代价是 Token 增加约 X%（取决于需求复杂度）。对于跨模块、高风险需求，Multi-Agent 的额外成本值得；对于简单单模块需求，Legacy 更经济。这是真实的工程权衡，不是"多就一定好"。

**项目实现：**
- A/B 框架支持 3 个维度的对比：自动统计（Token、耗时、文件数）+ 人工评分（需求覆盖、风险覆盖、测试完整性）+ 经济判断（成本收益比）
- 3 个案例设计覆盖不同复杂度：局部业务需求（订单超时取消）→ 跨模块一致性需求（Redis 缓存失效）→ 风险密集型需求（并发幂等下单）
- `ABComparisonResult.improvement` 直接计算 delta
- `resume-claims.md` 只收录可追溯数据的结论

**代码位置：**
- `evaluation/multi_agent_runner.py` — `ABComparisonResult` + `compare_legacy_vs_multi_agent()`
- `docs/evaluations/M6-ab-comparison.md` — Mock A/B 报告

**测试证据：**
- Mock A/B：Legacy 3 workers 串行 vs Multi-Agent 6 agents (stage 2 并行)
- Live A/B：待 T-034 采集

**当前限制：**
尚无完整的 Live Provider 3 案例 A/B 数据（T-034）；人工评分需要操作者手动评价，尚未自动化。
