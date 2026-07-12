# SpecFlow Agent — 项目掌握文档

> 面试前 30 分钟看一遍这个文件。所有内容均可从代码和 Git 历史验证。

---

## 一、30 秒项目介绍

> 独立设计并实现了一个规范驱动的 AI 开发助手（Python/FastAPI），通过 Analyze → Generate → Review 三阶段 LLM Pipeline 对真实仓库进行只读分析。M6 升级为 6-Agent 固定拓扑多智能体架构，由确定性 Coordinator 控制流程而非 LLM 自主决策。123 模块、593 测试、50+ 次增量提交。

---

## 二、项目全景图

```text
                        ┌──────────────────────────────┐
                        │     CLI / HTTP Entry          │
                        │  specflow run / POST /run     │
                        └─────────────┬────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
     ┌────────▼────────┐   ┌─────────▼────────┐   ┌─────────▼────────┐
     │  Legacy Runner  │   │  Multi-Agent     │   │  FastAPI Server  │
     │  (runner.py)    │   │  Runner          │   │  (main.py)       │
     │  Analyze→Gen→   │   │  (runner_multi.  │   │  /health         │
     │  Review Pipeline│   │  py) 6-Agent     │   │  /projects       │
     └────────┬────────┘   └─────────┬────────┘   └──────────────────┘
              │                       │
              └───────────┬───────────┘
                          │
          ┌───────────────┼───────────────┬──────────────┬──────────────┐
          │               │               │              │              │
    ┌─────▼─────┐  ┌──────▼──────┐  ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
    │  Evidence │  │   Context   │  │   Token   │  │   LLM   │  │  Artifact │
    │  Pipeline │  │   Builder   │  │   Budget  │  │  Client │  │   Store   │
    │           │  │             │  │           │  │         │  │           │
    │ Repository│  │ Assembles   │  │ Policy-   │  │ OpenAI- │  │ 10 output │
    │ scan +    │  │ prompt +    │  │ based     │  │ compat  │  │ files per │
    │ evidence  │  │ context +   │  │ trimming  │  │ HTTP    │  │ run       │
    │ collection│  │ requirement │  │           │  │         │  │           │
    └───────────┘  └─────────────┘  └───────────┘  └─────────┘  └───────────┘
                          │
          ┌───────────────┼───────────────┬──────────────┐
          │               │               │              │
    ┌─────▼─────┐  ┌──────▼──────┐  ┌─────▼─────┐  ┌────▼────┐
    │   Trace   │  │  Fallback   │  │   Tools   │  │  Eval   │
    │           │  │             │  │           │  │         │
    │ Step-by-  │  │ Rule-based  │  │ list_files│  │ Mock +  │
    │ step      │  │ degraded    │  │ search_   │  │ Live    │
    │ execution │  │ results     │  │ code,     │  │ Provider│
    │ recording │  │             │  │ read_file │  │ A/B test│
    └───────────┘  └─────────────┘  └───────────┘  └─────────┘
```

### 7 层架构

| 层 | 模块 | 职责 | 行数 |
|----|------|------|------|
| 1. Entry | `main.py`, `cli.py`, `runner.py`, `runner_multi.py` | CLI/HTTP 入口，流程编排 | ~1,000 |
| 2. Scanner | `scanner.py`, `technology.py` | 安全仓库扫描，技术栈识别 | ~400 |
| 3. Evidence | `evidence/` | 关键词提取→工具搜索→文件排序→EvidenceBundle | ~500 |
| 4. Context | `context.py`, `context_builder/`, `token_budget/` | 上下文组装 + Token 预算裁剪 | ~800 |
| 5. LLM | `llm/`, `prompts/` | OpenAI-compatible Provider + Prompt Registry | ~600 |
| 6. Worker/Agent | `workers/`, `agents/`, `coordinator/` | Analyze/Generate/Review Workers + 6-Agent 拓扑 | ~3,000 |
| 7. Quality | `trace/`, `fallback/`, `evaluation/`, `artifacts/` | Trace 记录、降级、评测、Artifact 持久化 | ~2,000 |

---

## 三、完整执行流程（一次 `specflow run` 发生了什么）

### Legacy Pipeline（单 Agent 模式）

```text
1. CLI 接收参数
   specflow run --repo ./my-project --requirement "增加订单取消"

2. Repository Scanner
   → 验证路径在仓库内（防路径穿越）
   → 识别 Python/FastAPI 技术栈

3. Evidence Collection
   → 从 requirement 提取关键词
   → search_code 搜索匹配文件
   → 按相关性排序，取 Top 10
   → 生成 EvidenceBundle（含 sanitized 文件内容）

4. Context Building
   → Prompt Registry 加载 Analyze Worker 的 prompt 模板
   → Context Builder 组装：system prompt + evidence + requirement + prior outputs
   → Token Budget Manager 裁剪超长上下文

5. LLM Call (Analyze)
   → OpenAI-compatible HTTP POST → DeepSeek
   → 返回结构化 AnalysisOutput（Pydantic 校验）
   → 校验失败 → JSON Repair → Retry → Rule Baseline Fallback

6. LLM Call (Generate)
   → 基于 AnalysisOutput 生成 GenerationOutput

7. LLM Call (Review)
   → 审查 GenerationOutput → PASS/REJECT

8. Artifact Delivery
   → manifest.json + agent-outputs.json + handoffs.json
   + traces.json + sources.json（5 个结构化文件）
```

### Multi-Agent Pipeline（M6）

```text
1-4. Evidence Collection → 仓库扫描 + 关键词匹配 + 证据收集
     （与 Legacy 共享同一 EvidenceCollector，但不经过 Context Builder/Token Budget）

5. Coordinator.plan()
   → DeterministicPlanner 生成固定拓扑
   → PlanCompiler 编译为执行阶段
   → PlanValidator 校验结构完整性 + SchemaRegistry 校验 Schema ID
   → SemanticPlanEnricher 用 LLM 为每个 Agent 生成任务语义

6. Stage 0（顺序执行）
   RepositoryAnalyst → 分析仓库结构，输出 RepositoryAnalysis

7. Stage 1（并行执行，ThreadPoolExecutor）
   Design        → 基于分析生成架构/接口方案
   TestStrategy  → 生成测试策略
   RiskReview    → 识别安全/并发/数据风险
   （三个 Agent 同时运行，无依赖冲突）

8. Stage 2（顺序执行）
   Synthesis → 合并三个 Specialist 输出为统一方案

9. Stage 3（顺序执行）
   Review → 审查合成结果

10. Revision（如果 Review 给出 REJECT）
    → RevisionController 检查是否已耗尽（max 1 round）
    → 未耗尽：创建 RevisionTask，定向返回指定 Agent 重做
    → 已耗尽：记录 revision_exhausted=true，正常终止

11. Artifact Delivery → 10 个结构化文件
```

---

## 四、6-Agent 拓扑

```text
Stage 0 ── RepositoryAnalyst ──→ 分析仓库，提取证据
                                      │
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                 ↓
Stage 1 ──    Design          TestStrategy       RiskReview
           (架构方案)        (测试策略)         (风险识别)
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      ↓
Stage 2 ──      Synthesis ──→ 合并三个 Specialist 输出
                                      │
                                      ↓
Stage 3 ──       Review   ──→ PASS → 输出
                           ──→ REJECT → RevisionController → 定向返工 → 再 Review
                                       → 耗尽 → revision_exhausted=true → 终止
```

**关键设计决策：为什么是自己实现而不是 LangGraph？**

```text
1. 行为可控：确定性代码拥有流程控制权。LLM 无权增加/删除 Agent、改变依赖、提高返工轮数。
   出问题直接定位到 Coordinator/Scheduler 层，不需要翻 LangGraph 源码。

2. 编排不复杂：固定 6-Agent 拓扑，不需要图编排的动态路由能力。

3. 完全自定义：Prompt、Tool 协议、审批策略、Trace 格式都按自己的方式定义，
   不需要适配 LangGraph 的抽象层。

4. 未来可迁移：任务流变复杂（多节点、可视化编排、长期工作流复用）后再引入 LangGraph。
```

---

## 五、关键模块面试速查

### 1. 如何保证 AI 输出可靠性？

```text
问题：LLM 返回格式不稳定怎么办？

我的方案（5 层防御）：
  Pydantic Schema → 校验失败 → JSON Repair → Retry → Rule Baseline Fallback
  → Trace 记录最终使用的层级（model_output / repaired / rule_baseline）

代码位置：fallback.py (FallbackManager), workers/ (Worker.execute), trace/

面试证据：
  - 593 个测试覆盖各种失败场景
  - Live Provider 验证：真实 DeepSeek 调用，完整 Agent Pipeline 跑通
```

### 2. 如何防止多 Agent 无限循环？

```text
问题：Agent 之间来回返工怎么办？

我的方案：
  RevisionController 是确定性代码，不是 LLM 决策。
  - max_total_rounds = 1（硬编码，LLM 无法修改）
  - Review 只能触发一次定向返工
  - 第二次 REJECT 后正常终止，记录 revision_exhausted=true
  - Trace 记录完整拓扑（哪个 Agent 被返工、什么原因、结果）

代码位置：coordinator/revision.py (RevisionController)
```

### 3. 如何处理 LLM 调用失败？

```text
问题：API 超时、429 限流、模型返回乱码怎么办？

我的方案：
  - FallbackManager：自动重试（可配置次数），失败后降级到 rule_baseline
  - rule_baseline：不依赖 LLM，用静态规则生成最低可用结果
  - 所有降级路径在 Trace 中记录，Artifact 标记 DEGRADED + requires_review
  - Provider 层：同步 HTTP 调用，socket timeout（不依赖 SDK，不执行自动 retry）

代码位置：fallback.py, llm/ (OpenAICompatibleLLMClient), trace/
```

### 4. 如何防止 AI 读取不该读的文件？

```text
问题：AI 工具调用越权读取密钥文件怎么办？

我的方案（4 层防护）：
  1. RepositoryToolSet 绑定单一 repo root（路径穿越阻断）
  2. read_file 检查文件是否在 repo root 下（符号链接拒绝）
  3. Context Builder 的 _redact_secrets() 在组装上下文时自动抹除
     URL credentials、token、api_key、secret、password 模式匹配
  4. Artifact 持久化前再次经过 sanitize 管线

代码位置：tools/repository_tools.py, context.py (_redact_secrets)
```

### 5. 为什么有 Legacy 和 Multi-Agent 两套 Runner？

```text
问题：为什么不做统一？

回答：
  Legacy Pipeline（runner.py）：3 Worker 串行，M1-M5 的产品形态。
  Multi-Agent Pipeline（runner_multi.py）：6 Agent 固定拓扑，M6 新增。

  保留 Legacy 不是为了兼容，而是作为 A/B 评测的 baseline。
  T-032 评测会对比：
    - Legacy 质量 vs Multi-Agent 质量
    - Legacy Token 消耗 vs Multi-Agent Token 消耗
    - 多 Agent 是否值得额外成本和延迟

  这是有意识的设计，不是技术债。
```

---

## 六、量化数据（面试直接引用）

| 指标 | 数值 | 证明什么 |
|------|------|---------|
| 源文件 | 123 个 Python 模块 | 模块化架构，非单文件脚本 |
| 测试文件 | 46 个 | 测试-源码比 1:2.7 |
| 测试数 | 593 passed | 高覆盖率 |
| 总代码量 | ~20,000 行 | 一人月级别 |
| 提交数 | 50+ commits | 递增开发，非一键生成 |
| 里程碑 | M1-M6 (6 个) | 结构化渐进交付 |
| 任务数 | 23+ 个结构化 Task | 每个有 spec + test + report |
| Live 验证 | DeepSeek V4 端到端 | 真实 LLM 调用，非 mock |
| 修复 bug | 11 个（Code Review 发现） | 真实质量过程 |
| 架构层数 | 7 层 | 非玩具项目 |

---

## 七、面试追问预判

| 追问 | 你的回答要点 |
|------|------------|
| "为什么不用 LangChain？" | 需要完全控制 prompt/tool/trace 格式；编排不复杂不需要图框架；未来需要时可以迁移 |
| "Agent 之间怎么通信？" | Handoff 协议：source_output_schema_id ↔ target_input_schema_id，HandoffValidator 运行时校验 |
| "Token 消耗怎么控制？" | Token Budget Manager 策略驱动裁剪；被移除的 section 记录在 trace 中；每个 Agent 有独立 context_window |
| "怎么评测 Agent 质量？" | T-032：Legacy vs Multi-Agent A/B 对比，覆盖风险覆盖率、延迟、Token 消耗、工具调用正确率 |
| "最大的技术难点？" | 让确定性代码和不确定的 LLM 输出安全协作——Pydantic Schema + JSON Repair + Fallback 三级防护 |
| "如果重新做会改什么？" | 证据收集管线对中文关键词支持不够（M5 已知限制），需要更好的跨语言代码搜索 |
