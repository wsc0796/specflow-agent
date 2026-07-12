# SpecFlow Agent — 面试讲稿

> 用途：面试前快速过一遍。每个问题 2~3 分钟回答。先讲结论，再给证据。

---

## Q1：介绍一下这个项目

**30 秒版：** SpecFlow Agent 是一个规范驱动的 AI 开发助手。你给它一个 Python 仓库和一个需求描述，它先用只读工具收集仓库证据，然后通过 Analyze → Generate → Review 三阶段 LLM Pipeline 产出结构化技术规格、测试计划和审查报告。整个系统是我从零独立设计实现的，7 层架构、404 个测试、23 个渐进式任务，目前已在真实仓库 + 真实大模型（DeepSeek V4）上完成端到端验证。

**展开版（如果面试官追问架构）：**

我设计的核心思路是"有边界的 AI"——不是让 LLM 随意生成代码，而是每一步都有输入验证、输出校验和降级兜底。

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

## Q2：你在这个项目里具体做了什么技术决策？

**选三个最有区分度的讲：**

**决策 1：Protocol 而非 ABC。** LLM Client 用 `typing.Protocol` 定义接口，而不是抽象基类。因为 MockLLMClient 和 OpenAICompatibleLLMClient 没有任何共享实现逻辑——一个是读内存字符串，一个是发 HTTP 请求。Protocol 是 structural subtyping，不需要显式继承，更干净。

**决策 2：State Machine 而非 if-else。** Worker 的执行顺序不是硬编码的 `analyze(); generate(); review()`，而是用显式的 WorkflowState 枚举 + 合法转换表。非法状态转换（比如从 completed 直接跳回 analyzing）会在运行时被拒绝并记录。这意味着以后加新 Worker（比如 M6 的 code-generate worker）不需要改已有代码，只加新的状态和转换规则。

**决策 3：MockFirst 测试策略。** 所有 404 个测试默认不调真实 API。MockLLMClient 返回确定性 JSON。只有一个人工触发的 Live Provider 验证会真正调用 API。这意味着 CI 不会因为 API 波动而挂，也不会消耗 Token 配额。

---

## Q3：遇到过什么技术难点？怎么解决的？

**难点：CLI runner 上线后发现无论如何都返回 exit code 3。**

排查过程：
1. 先看测试——全绿，404 passed。这反而说明测试覆盖有盲区。
2. 直接跑 `specflow run --mock`，看 error artifact：`Missing handler for step: generate`。
3. 定位到 runner.py 的 AgentExecutor 只注册了 `"analyze"` handler，没有 generate 和 review。
4. 状态机会从 analyzing → generating，到 generating 时找不到 handler → ExecutionError → failed。

**解决办法：**
- 接入完整三 Worker 链，用 ExecutionContext-based factory 将上一步的 output 注入下一步的 prior_outputs
- 为每个 Worker 创建独立的 MockLLMClient（因为 analyze/generate/review 返回不同 JSON schema）
- 收紧 CLI 测试：之前允许 exit_code in {0, 3, 4}，现在必须 assert == 0 且验证 10 个 artifact 完整

**教训：** 单元测试 + 集成测试都绿 ≠ CLI 端到端能跑。这种"假绿灯"是最危险的。现在 CLI 测试会真正调 `main()` 函数并验证 artifact 目录的完整产出。

---

## Q4：你是怎么保证代码质量的？

三件事：

**1. 每个 Task 有合同。** 不是我想到什么写什么。每个 Task 都有 spec（范围、禁止项、验收标准），完成有 completion report。违规了过不了 review。

**2. MockFirst + 确定性测试。** 所有 LLM 调用在测试里走 Mock，返回固定 JSON。同一个输入跑 100 次结果一样。这解决了 AI 系统测试不确定性的核心痛点。Live Provider 验证是人工在独立终端做的，CI 从来不调真实 API。

**3. 10 维人工 Rubric。** 自动检查只能验证"管道没坏"——文件存在、JSON 合法、hash 对得上、没 secret。内容质量必须人工评分。10 个维度，0/1/2 分制，每个分数都要求写 artifact 证据。这样 review 不会变成"看着还行就过了"。

---

## Q5：这个项目和直接用 Cursor/Copilot 写代码有什么区别？

Cursor/Copilot 是**交互式**的——你写 prompt，它生成代码，你接受或拒绝。问题是：
- 没有审查环节——生成的代码可能引入了你没想到的安全问题
- 没有证据追溯——你不知道它为什么推荐这个方案，参考了项目的哪个文件
- 没有失败兜底——JSON 解析失败就崩了

SpecFlow Agent 是**管道式**的：
- 必须先收集仓库证据（只读工具 + 路径验证）
- 必须走 Analyze → Generate → Review 三段
- Review 可以 REJECT，系统不会假装成功
- 每一步都有降级兜底（fallback 机制）
- 所有产出物都是结构化 JSON，可自动检查 + 人工审查

**适用场景不同：** Cursor 适合"帮我写这个函数"。SpecFlow 适合"给我分析这个需求对仓库的影响，生成可审查的技术方案"。

---

## Q6：后续打算怎么改进？

三个方向：

**M6 — Scanner 集成。** CLI runner 目前用最小 ProjectContext（空框架/ORM/数据库），导致 Live 运行时 LLM 缺少足够的项目事实。M6 会把已有的 RepositoryScanner + TechnologyDetector 接入 runner，让 ProjectContext 自动填充框架、依赖、入口文件、ORM 等信息。

**工具链扩展。** 目前只有只读工具。后续可能加 Git diff 工具（只读）、AST 分析工具（只读），但永远不会加自动修改仓库的工具。

**多案例评测。** T-023 只跑了一个 Live 案例。后续加 3~5 个不同类型的需求（性能优化、安全加固、重构建议），丰富评测矩阵。

---

## Q7：（如果面试官是做 AI Agent 的）你的 Agent 架构和 LangGraph/ReAct 有什么区别？

SpecFlow 目前是**确定性 Pipeline**，不是 Agent Loop。区别在于：

- **LangGraph/ReAct：** LLM 自主决定下一步做什么（think → act → observe → think），适合开放式任务，但行为不可预测、调试困难。
- **SpecFlow：** 步骤是固定的（Analyze → Generate → Review），每个步骤的输入输出有严格 schema 约束。好处是完全可预测、可测试、可审计。

**为什么先做 Pipeline 而不是 Agent Loop？** 因为如果连固定步骤的输出质量都控制不了，让 LLM 自主决策只会更不可控。M5 证明了三段 Pipeline 的每一段都可以独立验证和降级。Agent Loop 是未来的方向，但必须建立在已验证的 Worker 质量基础上。

---

## 面试前 5 分钟快速回顾

1. 项目是做什么的 → 规范驱动的 AI 开发助手，Analyze→Generate→Review
2. 你的角色 → 独立设计实现全部架构，不是 clone 的
3. 量化数据 → 404 测试、7 层架构、23 个任务、Live Provider 验证
4. 最大难点 → CLI "假绿灯" + Pipeline 集成缺口的诊断和修复
5. 和 Cursor 的区别 → Pipeline 式 vs 交互式，有审查 + 有兜底 + 有证据
