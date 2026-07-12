# SpecFlow Agent — 面试准备清单

> 进面试间前 10 分钟看一遍这个文件就够了。所有数据都来自 Git 历史，可当场验证。

---

## 一、30 秒自我介绍

> 独立设计并实现了一个规范驱动的 AI 开发助手（Python/FastAPI），通过 Analyze → Generate → Review 三阶段 LLM Pipeline 对真实仓库进行只读分析，自动生成结构化技术规格和评测报告。7 层架构、88 个模块、404 个测试、43 次增量提交，已在真实仓库 + DeepSeek V4 上完成端到端验证。

---

## 二、量化数据速查

| 指标 | 数值 | 证明什么 |
|------|------|---------|
| 总 commit | 43 | 递增开发，非一次性生成 |
| 开发天数 | 2 | 高强度集中开发 |
| Python 代码 | 14,194 行 | 代码量够一人月项目 |
| 源模块 | 88 | 7 层模块化架构 |
| 测试文件 | 27 | 测试和源码 1:1 |
| 测试数量 | 404 passed | 高覆盖率 |
| Fix commit | 8 | 真实 debug 过程 |
| Code Review | 2 次 | 外部质量验证 |
| Review 发现 Bug | 11 个 | 非自我感觉良好 |
| 结构化 Task | 23 + 1 fix | 每个有 spec + report |
| 平均 commit | ~475 行 | 无巨型一次性提交 |
| 架构层数 | 7 层 | Tool → Evidence → Context → Budget → Worker → Artifact → Evaluation |
| Live Pipeline 延迟 | ~27s | Analyze 7.7s + Generate 9.4s + Review 10.4s |
| Live Token 消耗 | ~4,077 | input 1,694 + output 2,383 |
| 安全防护层 | 5 层 | 路径穿越、symlink、敏感文件名、内容脱敏、调用次数硬限制 |
| 评测维度 | 10 维 | 0/1/2 分制 |
| Live 人工 Rubric | 13/20 | degraded 运行，pipeline 集成缺口 |
| Live 凭据泄露 | 0 | 全量 Artifact 扫描 |

---

## 三、STAR 子弹（选 2-3 条贴简历）

### 子弹 1：架构设计

**S** — LLM 直接生成代码缺乏可审查性和可回滚性，需要一套有边界的确定性 Pipeline。

**T** — 设计一个从仓库证据收集到 AI 分析再到自动审查的完整工作流系统。

**A** — 独立设计了 7 层模块化架构，使用 Python Protocol 定义抽象接口，所有模块通过显式公开 API 解耦。

**R** — 交付 23 个渐进式任务、404 个测试。系统可在 <30 秒内完成 Analyze → Generate → Review 完整链路，产出 10 个结构化产物。

**简历一行版：** 独立设计并实现了一个 7 层模块化的 AI Pipeline 系统（Python/FastAPI），23 个渐进式任务、404 个测试，支持对任意 Python 仓库的只读分析和自动审查。

---

### 子弹 2：安全工程

**S** — AI Agent 访问仓库文件存在路径穿越、凭据泄露、敏感文件读取等安全风险。

**T** — 构建一套只读、可验证、有边界的仓库访问工具层。

**A** — 实现了沙箱化 RepositoryToolSet，包含 5 层安全防护：路径穿越拦截、符号链接边界检查、敏感文件名过滤、输出内容脱敏（正则匹配 sk-* / JWT / api_key）、文件大小和调用次数硬限制。

**R** — 通过真实 Provider 端到端验证，零 API Key、零 Token、零外部路径泄露，目标仓库零修改。

**简历一行版：** 为 AI Agent 设计了 5 层安全防护的沙箱化仓库访问工具，通过真实 Provider 端到端验证零凭据泄露。

---

### 子弹 3：测试与质量工程

**S** — AI 相关系统的不确定性使传统测试难以覆盖边界场景和失败路径。

**T** — 建立一套支持 Mock 确定性验证 + 真实 Provider 合同检查的测试体系。

**A** — 设计了 MockFirst 测试策略 + 10 维度人工 Rubric（0/1/2 分制）分离自动检查与内容质量评估。CLI 测试从"接受任何非零退出码"收紧为"必须验证完整 10 文件产出和 manifest status==completed"。

**R** — 404 个测试全通过。发现并修复了 CLI runner 只注册 analyze handler 导致 generate/review 永远失败的严重 Bug（"假绿灯"）。

**简历一行版：** 建立 MockFirst 确定性测试 + 10 维人工 Rubric 评估体系，404 测试全绿，发现并修复了 CLI Pipeline 的致命断链 Bug。

---

### 子弹 4：问题诊断与工程判断

**S** — Live Provider 首次真实运行返回 exit code 4，表象是"失败"。

**T** — 在不读取环境变量和 API Key 的前提下，仅通过 Artifact 审查定位根因。

**A** — 通过逐层追溯 trace.json 的 fallback_level → analysis.json 的 degraded 标记 → review.json 的 REJECT 决策链，定位到 Pipeline 集成缺口（CLI runner 未接入 scanner，ProjectContext 空框架/ORM 字段），判断这不是 AI 质量问题。

**R** — 将退出码 4 从"失败"正确重分类为"degraded + 正确 REJECT"，避免了对正常代码的无效排查。

**简历一行版：** 通过 Artifact 链逆向诊断，将 Live 运行退出码 4 从误判的"失败"正确定性为 Pipeline 集成缺口，展现了独立排障能力。

---

## 四、面试 Q&A

### Q1：介绍一下这个项目

**30 秒版：** SpecFlow Agent 是一个规范驱动的 AI 开发助手。你给它一个 Python 仓库和一个需求描述，它先用只读工具收集仓库证据，然后通过 Analyze → Generate → Review 三阶段 LLM Pipeline 产出结构化技术规格、测试计划和审查报告。整个系统是我从零独立设计实现的，已在真实仓库 + DeepSeek V4 上完成端到端验证。

**展开版（如果面试官追问架构）：**

核心思路是"有边界的 AI"——不是让 LLM 随意生成代码，而是每一步都有输入验证、输出校验和降级兜底。

```
仓库 → Evidence Collector (list_files/search_code/read_file)
     → Context Builder (Prompt + 项目上下文 + Token 预算)
     → Analyze Worker (需求分析 → AnalysisOutput JSON)
     → Generate Worker (技术方案 → GenerationOutput JSON)
     → Review Worker (自动审查 → PASS/REJECT)
     → 10 个结构化 Artifact (JSON + Markdown)
```

每一层都有独立的测试、独立的异常类型、独立的降级策略。比如 Analyze Worker 如果解析 LLM 返回的 JSON 失败，不是崩掉，而是 fallback 到 rule_baseline 并标记 degraded=true，后续 Worker 会传播这个状态。

---

### Q2：你在这个项目里具体做了什么技术决策？

**决策 1：Protocol 而非 ABC。** LLM Client 用 `typing.Protocol` 定义接口。因为 MockLLMClient 和 OpenAICompatibleLLMClient 没有任何共享实现逻辑——一个是读内存字符串，一个是发 HTTP 请求。Protocol 是 structural subtyping，不需要显式继承。

**决策 2：State Machine 而非 if-else。** Worker 执行顺序不是硬编码的 `analyze(); generate(); review()`，而是用显式的 WorkflowState 枚举 + 合法转换表。非法状态转换在运行时被拒绝。加新 Worker 不需要改已有代码。

**决策 3：MockFirst 测试策略。** 所有 404 个测试默认不调真实 API。MockLLMClient 返回确定性 JSON。只有人工触发的 Live Provider 验证会真正调用 API。CI 不消耗 Token 配额。

---

### Q3：遇到过什么技术难点？怎么解决的？

**难点：CLI runner 上线后发现无论如何都返回 exit code 3。**

排查过程：
1. 先看测试——全绿，404 passed。这反而说明测试覆盖有盲区。
2. 直接跑 `specflow run --mock`，看 error artifact：`Missing handler for step: generate`。
3. 定位到 runner.py 的 AgentExecutor 只注册了 `"analyze"` handler，没有 generate 和 review。
4. 状态机推进到 generating 时找不到 handler → ExecutionError → failed。

解决办法：
- 接入完整三 Worker 链，用 ExecutionContext-based factory 将上一步的 output 注入下一步的 prior_outputs
- 为每个 Worker 创建独立的 MockLLMClient（因为 analyze/generate/review 返回不同 JSON schema）
- 收紧 CLI 测试：之前允许 exit_code in {0, 3, 4}，现在必须 assert == 0 且验证 10 个 artifact 完整

**教训：** 单元测试 + 集成测试都绿 ≠ CLI 端到端能跑。这种"假绿灯"是最危险的。

---

### Q4：你是怎么保证代码质量的？

**1. 每个 Task 有合同。** 每个 Task 都有 spec（范围、禁止项、验收标准），完成有 completion report。违规了过不了 review。

**2. MockFirst + 确定性测试。** 所有 LLM 调用在测试里走 Mock，返回固定 JSON。同一个输入跑 100 次结果一样。Live Provider 验证是人工在独立终端做的，CI 从来不调真实 API。

**3. 10 维人工 Rubric。** 自动检查只能验证"管道没坏"——文件存在、JSON 合法、hash 对得上、没 secret。内容质量必须人工评分。10 个维度，0/1/2 分制，每个分数都要求写 artifact 证据。

---

### Q5：这个项目和直接用 Cursor/Copilot 写代码有什么区别？

Cursor/Copilot 是**交互式**的——你写 prompt，它生成代码，你接受或拒绝。问题是：没有审查环节、没有证据追溯、没有失败兜底。

SpecFlow Agent 是**管道式**的：必须先收集仓库证据 → 走 Analyze → Generate → Review 三段 → Review 可以 REJECT → 每一步都有降级兜底 → 所有产出物都是结构化 JSON，可自动检查 + 人工审查。

**适用场景不同：** Cursor 适合"帮我写这个函数"。SpecFlow 适合"给我分析这个需求对仓库的影响，生成可审查的技术方案"。

---

### Q6：后续打算怎么改进？

**M6 — Scanner 集成。** CLI runner 目前用最小 ProjectContext（空框架/ORM/数据库），导致 Live 运行时 LLM 缺少足够的项目事实。M6 会把已有的 RepositoryScanner + TechnologyDetector 接入 runner。

**工具链扩展。** 后续可能加 Git diff 工具（只读）、AST 分析工具（只读），但永远不会加自动修改仓库的工具。

**多案例评测。** T-023 只跑了一个 Live 案例。后续加 3~5 个不同类型的需求，丰富评测矩阵。

---

### Q7：（AI Agent 面试官）你的 Agent 架构和 LangGraph/ReAct 有什么区别？

SpecFlow 目前是**确定性 Pipeline**，不是 Agent Loop。

- **LangGraph/ReAct：** LLM 自主决定下一步做什么，适合开放式任务，但行为不可预测、调试困难。
- **SpecFlow：** 步骤是固定的（Analyze → Generate → Review），每个步骤的输入输出有严格 schema 约束。好处是完全可预测、可测试、可审计。

**为什么先做 Pipeline 而不是 Agent Loop？** 如果连固定步骤的输出质量都控制不了，让 LLM 自主决策只会更不可控。M5 证明了三段 Pipeline 的每一段都可以独立验证和降级。Agent Loop 是 M7+ 的方向，但必须建立在已验证的 Worker 质量基础上。

---

## 五、自主开发证明（回应"是不是 AI 写的"）

### 一句话回应

> "这个项目有 43 个增量 commit、8 个 fix、2 次 Code Review 闭环、23 个结构化 Task。如果 AI 能自动做到每 475 行就 commit 一次、自己修自己引入的 bug、自己给 code review 写 fix，那确实不需要我。但目前做不到。"

### 三条硬证据

**证据 1：8 个 Fix Commit — AI 不会自己修 Bug**

| Commit | 修了什么 |
|--------|---------|
| `fix(cli): complete worker pipeline delivery` | **假绿灯 Bug** — 404 测试全绿但 CLI 永远返回 exit 3 |
| `fix: address code review #1` | 外部 Code Review 发现的 5 个问题 |
| `fix: satisfy review #1 specification gaps` | Review 指出的规格缺口 |
| `fix(context): redact secrets and strip control characters` | JWT/sk-* 格式数据未脱敏就写入了 prompt |
| `fix(context): harden determinism` | Context 生成每次运行 hash 不同 |
| `fix(detector): integrate with safe scanner` | TechnologyDetector 绕过了 Scanner 的安全校验 |
| `fix(docs): harden evidence redaction test` | 文档和测试未覆盖 secret 脱敏边界场景 |
| `fix(eval): validate real tool call artifacts` | 评测框架未区分 Mock Tool Call 和真实 Tool Call |

**证据 2：2 次外部 Code Review + 修复闭环**

Review #1 发现 5 个问题 → 补充 7 个回归测试 → 2 个 fix commit
Review #2 发现 6 个问题 → 收紧 CLI 测试 → 1 个 fix commit
总计 11 个外部发现的问题被修复。不是自己看完就算了。

**证据 3：43 次增量 Commit，非一次性生成**

每个 commit 平均 475 行，最大不超过 1,300 行。每个 commit 对应一个独立 Task，有 spec、实现、测试、completion report。不存在 5,000 行的一次性提交。

---

### AI 辅助的真实角色

**诚实陈述：**
- **AI 角色：** Review（审查代码）、Debug（协助定位）、Generate boilerplate（生成框架代码）
- **我的角色：** 架构设计、技术决策、质量把关、问题诊断

**最有力的例子：** 那个 CLI 假绿灯 Bug——AI review 没发现，404 个测试全绿，但我手动跑 CLI 发现返回了错误码，然后自己 trace 代码找到根因。这种判断力不是 AI 能替代的。

---

## 六、面试前 5 分钟速览

1. **项目一句话：** 规范驱动的 AI 开发助手，Analyze→Generate→Review 三阶段 Pipeline
2. **核心数据：** 43 commits / 404 tests / 88 modules / 8 fixes / 2 reviews
3. **你的角色：** 独立设计 7 层架构，AI 做 review 和 debug，你负责决策和验收
4. **最大难点：** CLI "假绿灯" Bug（404 测试全绿但 CLI 跑不通）→ 手动发现 + 自己修复
5. **和 Cursor 的区别：** Pipeline 式 vs 交互式。有审查、有兜底、有证据追溯
6. **如果被问"是不是 AI 写的"：** 展示 `git log --oneline` 的 43 个 commit 和 8 个 fix
