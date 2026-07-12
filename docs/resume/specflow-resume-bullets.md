# SpecFlow Agent — 简历描述与 STAR 故事

## 通用版简历 Bullets（AI/后端开发）

**SpecFlow Agent | 面向代码仓库的可控多智能体规格分析系统**
*Python 3.12 · Pydantic v2 · FastAPI · SQLAlchemy · pytest (607 tests) · DeepSeek API*

- 独立设计并实现固定六 Agent 编排架构（Coordinator + RepositoryAnalyst + Design ‖ TestStrategy ‖ RiskReview → Synthesis → Review），由确定性 Coordinator 生成 Agent 拓扑、依赖图和执行阶段，LLM 仅补充语义任务描述（M6-ADR-001）
- 基于 Kahn 算法实现 DAG 编译与分层并行调度，Design/TestStrategy/RiskReview 三个 Specialist 并行执行，`ThreadPoolExecutor` 管理并发
- 建立版本化 Agent/Schema Registry、结构化 AgentHandoff（含 source/target schema 校验 + canonical JSON SHA-256 hash）、AgentTraceSpan（stage timing + parent/child topology），实现 Agent 间契约与全链路可审计
- 接入 OpenAI-compatible LLM Provider 与只读仓库 Evidence Pipeline，在真实 Python/FastAPI 仓库（sky-takeout-python）上完成 DeepSeek 六 Agent 端到端运行，6/6 Agent 执行、7 条 Handoff 校验通过、52 个仓库文件命中
- 保留 Legacy 线性管道（Analyze→Generate→Review）作为 A/B 基线，建立 10 维度评测框架（需求覆盖、风险覆盖、测试完整度、Token 成本、延迟、Fallback 率等），607 测试全绿
- 实现有界返工（max 1 轮 Revision）、角色级降级、FAILED 运行审计持久化、canonical JSON 哈希一致性（修复中文输出 `ensure_ascii` Bug）

---

## JD 定制版 — MiniMax（AI Agent 方向）

> 针对 MiniMax JD 的关键词：多 Agent、自研框架、工具调用、评测体系

**SpecFlow Agent | 自研多智能体需求分析系统**
*Python · Pydantic · FastAPI · DeepSeek · pytest (607 tests)*

- **多 Agent 编排**：从零设计 Coordinator-Subagent 架构，6 个专职 Agent（分析/设计/测试策略/风险审查/综合/终审）通过确定性 DAG 编译和分层并行调度协作，不依赖 LangGraph 等第三方框架
- **Agent 工程化**：建立 AgentRegistry（身份/角色/Schema/权限）、结构化 Handoff（source/target schema 校验 + SHA-256 hash）、AgentTraceSpan（stage timing + 全链路拓扑），Agent 间契约可审计、可复现
- **工具调用与安全**：实现只读 Repository Tool（list_files/search_code/read_file）+ ToolRegistry + ToolExecutor，路径穿越阻断、敏感文件拒绝、输出上限控制
- **评测闭环**：保留单 Agent 基线，建立 10 维度 A/B 对比框架（需求覆盖、风险识别、Token 成本、延迟、Fallback 率），用数据证明多 Agent 架构的价值
- 真实仓库 DeepSeek 六 Agent 端到端运行通过，7 条 Handoff 校验 + 52 文件证据命中

---

## JD 定制版 — 复保科技（Python 后端 + AI 方向）

> 针对复保科技 JD 的关键词：FastAPI、Pydantic、确定性、异常处理、持久化

**SpecFlow Agent | 可控多智能体代码分析服务**
*Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy · pytest (607 tests)*

- **确定性工作流引擎**：设计 9 状态 MultiAgentWorkflowEngine + 6 状态 WorkflowEngine，所有状态转换可审计、可恢复、可快照回放，业务拒绝 ≠ 系统故障
- **Pydantic 契约体系**：SchemaRegistry（版本化、冻结语义）+ AgentIdentity.input_schema_id/output_schema_id + HandoffValidator（运行时 Schema 校验 + payload hash 验证），全链路类型安全
- **异常处理与容错**：三层 Fallback（Retry → JSON Repair → Rule Baseline）+ 角色级降级策略 + FAILED 运行审计持久化（manifest + state history + partial trace），异常路径可追溯
- **并行调度**：ThreadPoolExecutor 实现分层并行（阶段串行、阶段内并行），agent_submitted_at/agent_completed_at 时间戳记录并行加速比
- 607 测试 · Ruff 规范 · 真实仓库验证 · Git 可审计 commit 历史

---

## 30 秒项目介绍

> "我做了一个多 Agent 代码分析系统，叫 SpecFlow。它不依赖 LangGraph——Coordinator、状态机、并行调度、Agent 注册和 Handoff 校验都是自己写的。6 个 Agent 分工协作，3 个 Specialist 并行执行。DeepSeek 上跑过真实 Python 项目的端到端分析，607 个测试全绿。代码在 GitHub 上开源。"

---

## STAR 故事 1：为什么从 Legacy 升级到 Multi-Agent

**Situation：** SpecFlow 最初只有一条线性管道：Analyze → Generate → Review。单链路上 Review 只能给出 PASS/REJECT，无法区分"设计不足"还是"风险遗漏"还是"测试缺失"。

**Task：** 在不破坏现有 Legacy 管道（404 tests 必须保持通过）的前提下，增加可控的多 Agent 协作能力，让设计、测试策略和风险审查由独立 Agent 并行完成。

**Action：**
- 设计 M6-ADR-001：确定性结构 + LLM 语义增强。规则层拥有 Agent 集合、依赖图、并行分组、预算和权限的全部控制权，LLM 仅补充 `SemanticTaskBrief`
- 用 Kahn 算法实现 DAG 编译（`PlanCompiler`），将 `AgentDependency` 编译为 `execution_stages`
- 实现 `MultiAgentScheduler`：阶段串行、阶段内 `ThreadPoolExecutor` 并行
- 创建独立的 `MultiAgentWorkflowState`（9 状态），不修改旧 `WorkflowState`（6 状态）
- 596 个新测试 + 404 个旧测试全部通过

**Result：**
- 6 Agent 端到端运行：RepositoryAnalyst → (Design ‖ TestStrategy ‖ RiskReview) → Synthesis → Review
- DeepSeek Live Run 成功，7 条 Handoff 校验通过，52 个仓库文件命中
- A/B 对比框架建立，10 维度评测可量化多 Agent 的增益

---

## STAR 故事 2：中文 Handoff Hash Bug

**Situation：** Mock 测试全绿，但第一次 DeepSeek Live Run 直接 FAILED。错误是 `Handoff output_hash does not match payload`。

**Task：** 定位根因并修复，确保中文 Agent 输出的 Hash 在创建端和校验端一致。

**Action：**
- 排查发现根因：创建端 `json.dumps(payload, sort_keys=True)` 默认 `ensure_ascii=True`，中文被转义为 `缓存...`；校验端 `json.dumps(..., ensure_ascii=False, ...)` 保留中文原文。SHA-256 不同。
- 创建 `canonical_json_bytes()` 统一序列化规则：`ensure_ascii=False` + `separators=(",",":")` + `sort_keys=True`
- 修改 `runner_multi.py`（创建端）、`HandoffValidator.validate_payload()`（校验端）、`tests/test_handoff_validator.py`（测试端）全部调用同一个函数
- 移除 `import json` 中不再需要的引用，避免未来误用

**Result：**
- 第二次 DeepSeek Run 全部 7 条 Handoff 通过
- 新增 defensive 约束：任何新增 Hash 逻辑必须使用 `canonical_json_bytes()`

---

## STAR 故事 3：防止 Agent 无限返工

**Situation：** Review → Generate → Review → Generate 是经典的多 Agent 循环风险。如果 LLM 可以无限触发 Revision，Token 成本和延迟会失控。

**Task：** 设计有界返工机制，保证执行一定终止，且业务拒绝（REJECT）不被错误标记为系统故障（FAILED）。

**Action：**
- 设计 `RevisionPolicy`：`max_total_rounds=1`（硬编码，LLM 不可改），`revisable_roles` 限制只有 Design/TestStrategy/RiskReview 可被 Revision
- 实现 `RevisionController`：`create_revision_task()` 在 `exhausted` 时返回 None
- 定义语义：第二次 Review REJECT → `COMPLETED` + `revision_exhausted=true`（不是 FAILED）。只有 Agent 崩溃、Schema 校验失败、Scheduler 异常才进入 FAILED
- 14 个测试覆盖 `exhausted` 行为

**Result：**
- Mock Run 验证：REJECT → 1 次 Revision → 再 Review → 正确终止
- 面试可明确回答"多 Agent 防循环靠的是 Coordinator 的确定性控制，不是 LLM 自觉"

---

## STAR 故事 4：Schema 校验 Bug 排查与修复

**Situation：** SchemaRegistry 和 12 个 Pydantic Schema 已在 `build_schema_registry()` 中注册，但第一次 DeepSeek Run 时 5/6 Agent 返回 `schema_validated=False`。原因是 `AgentRunner` 在 Schema 校验失败时直接吞掉异常并标记为 degraded。

**Task：** 在不阻断 Live Run 的前提下，区分"Schema 未注册"和"Schema 存在但输出格式不匹配"两种情况，并为两种场景提供不同的处理路径。

**Action：**
- 将 `AgentRunner._execute()` 中的 `except Exception` 拆分为 `SchemaNotFoundError`（跳过校验，raw pass-through + `schema_validated=False`）和其他异常（标记 degraded）
- 增加 `schema_validated` 字段到 Agent 返回值，写入 `metrics.json`
- 在 `AgentMetrics` 中分别追踪 `schema_validated_count` 和 `schema_unvalidated_count`

**Result：**
- DeepSeek Run 成功：Review Agent 输出通过 Pydantic `ReviewOutput.model_validate()`
- 5 个 Agent 标记为 raw pass-through（已知限制，M8 修复）
- 面试时诚实说明"当前 Schema 校验非阻塞，这是有意设计——先跑通全链路，再收紧契约"
