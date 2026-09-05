# AI Agent 工程化学习路线

*SpecFlow 主线 · 30 天能力战役 · Codex 共学 · 最终迭代版 V5.1*

> 本文由仓库所有者提供的 V5.1 Word 路线转换而来，是 30 天训练的总章程；每日只执行 `CURRENT.md` 指向的当天目标。

> 目标合同<br>用 30 天、每天 6–8 小时，以 SpecFlow 为唯一开发与简历旗舰项目。85% 时间用于接管现有 Tool、Context、Workflow、Multi-Agent、Eval 与安全链路，并完成 Repository RAG；15% 用于 agent-skeleton、diet-agent、cms-flow 的硬时间盒校准。V5.1 新增五条执行纪律：校准项目限时、Dev/Holdout 隔离、Fake/Live 证据分层、无答案阈值先假设后校准、简历证据前移。

| 维度 | 最终约束 |
| --- | --- |
| 目标岗位 | Python 后端 / AI 应用开发 / Agent 后端工程 |
| 唯一开发主线 | SpecFlow Agent |
| 跨项目校准 | agent-skeleton ≤4h；diet-agent ≤3h；cms-flow ≤3h；时间到即停 |
| 评测纪律 | 30 条需求拆 20 Dev + 10 Holdout；Holdout 到 Day 21 前不参与调参 |
| 证据纪律 | Fake 证明工程契约；真实 Embedding 才证明语义检索质量；Live E2E 在 Day 25 |
| 月底交付 | 能运行、能故障、能度量、能解释、能写进简历 |

> 最终原则<br>项目服务于能力，不让学习路线服务于项目。只有本人完成的预测、追链、故障定位、设计决策、关键修改和结果解释，才计入 Ownership。任何可选增强都不能挤占 RAG、Eval、Safety 和 Holdout 的时间。

## 1. V5.1 的五条执行压舱石

| 纪律 | 硬规则 | 为什么 |
| --- | --- | --- |
| 校准项目 Timebox | agent-skeleton 4h；diet-agent 3h；cms-flow 3h。时间到无论是否“完全懂”都停止。 | 防止四个仓库之间反复切换导致认知上下文损耗 |
| Dev / Holdout 隔离 | 30 条评测 = 20 Dev + 10 Holdout；Day 15–20 只看 Dev，Day 21 冻结后 Holdout 只跑一次。 | 避免 Top-K / Chunk / Hybrid 调参泄露测试集 |
| Fake / Live 分层 | Fake Embedding 只验证协议、维度、失败、索引、Citation；检索质量必须使用真实语义 Embedding。 | 防止把 deterministic fake 的工程可重复性误当成语义效果 |
| Threshold 是假设 | Day 8 记录初始无答案规则 T0；Day 15–20 用 Dev 校准；Day 21 冻结后再跑 Holdout。 | 避免拍脑袋把 0.7 等常量写成“正确阈值” |
| 简历证据前移 | Day 21 先写技术事实初稿；Day 28 才压缩成 Bullet；Day 29–30 做攻击式答辩。 | 避免月底仓促写成“功能介绍” |

> Holdout 红线<br>Day 21 之前，不允许因为 Holdout 结果去修改 Chunk Size、Top-K、Threshold、Retrieval Strategy、Prompt 或 Rerank。如果 Day 21 Holdout 掉分，记录为泛化结果；不要回头把测试集调好看。

## 2. 学习内容：看、实验、还是必须项目化

| 类别 | 内容 | 停止条件 |
| --- | --- | --- |
| 直接看知识点 | Transformer/Attention 直觉、模型训练基本概念、ReAct/Plan/Reflection 理论、Memory 分类、Prompt Injection 原理、框架/MCP/灰度定位 | 能说明它是什么、为什么存在、何时不该用 |
| 看 + 小实验 | Token/Context Window、Sampling、Prompt 顺序、Structured Output、SSE 基础 | 做 1–3 个对照实验，能解释失败现象 |
| 必须进项目 | Tool Calling、Context Engineering、Workflow/Multi-Agent、Repository RAG、Eval、Safety | 至少 G4；RAG/Eval/Safety 争取 G5 |

### 2.1 项目只做训练场

| 项目 | 只承担什么 | 硬停止条件 |
| --- | --- | --- |
| SpecFlow | 唯一开发/简历主线：Tool、Context、Workflow、Multi-Agent、RAG、Eval、安全、Trace | 30 天始终保持主线 |
| agent-skeleton | 校准 ReAct Tool Loop / Observation 回灌 / 循环终止 | 4 小时；输出状态机图 + 1 个故障后退出 |
| diet-agent | 校准 Conversation State / Session / Slots / History | 3 小时；完成四类状态边界表后退出 |
| cms-flow | 校准 DAG、并行依赖、资源隔离、Backpressure、Fallback、MDC Context | 3 小时；四张契约/思想图后退出 |
| 外部供体 | 每次只抽一个设计思想或源码链路 | 1–2 小时，不完整复刻 |

## 3. 月底能力目标与 Ownership Gate

| 能力 | 月底目标 | 证据 |
| --- | --- | --- |
| LLM / Token / 采样 / Attention | G2：能实验并预测常见失败 | 三组小实验 + 五种失败解释 |
| Prompt & Context | G4：能修改上下文装配与预算策略 | 压力实验 + 最小 Patch + 回归 |
| Tool Calling | G4：理解开放 Tool Loop 与受控 Evidence Tool | 两种模式对照 + 故障矩阵 |
| Repository RAG | G5：实现、评测并裁决方案 | 20 Dev + 10 Holdout + Citation + Benchmark |
| Memory / State | G3：区分 Conversation / Workflow / RAG Knowledge / Long-term Memory | 状态边界表 + 污染案例 |
| Workflow / Multi-Agent | G4：解释 Handoff、终止和失败语义 | 状态图 + required-agent 故障 |
| Eval & Safety | G5：定义成功、持续回归、安全失败 | 失败分类 + 安全反例 + Holdout |
| Trace / 成本 / 延迟 | G4：定位一次真实问题 | 阶段耗时 + Token + 降级证据 |

### 3.1 Ownership Gate

| Gate | 判断标准 | 示例 |
| --- | --- | --- |
| G0 | 能用自己的话说明目的和失败方式 | Context Window ≠ Memory |
| G1 | 不看笔记画出真实调用链 | 入口 → Context → Agent → Tool/Artifact |
| G2 | 本地能跑，知道关键输入输出 | 拿到一条 Trace / RAG Result |
| G3 | 主动制造并定位失败 | Timeout / 非法 JSON / 旧索引 |
| G4 | 自己设计并完成最小 Patch | fallback / policy / context trim |
| G5 | Test / Trace / Eval / 指标证明效果 | Recall / Citation / latency / token |
| G6 | 能解释替代方案、取舍和边界 | 为什么固定拓扑而不是开放 Planning |

## 4. 旗舰新增：SpecFlow Repository RAG

目标不是做“知识库聊天”，而是解决大型代码仓库中需求语言与代码命名不一致、关键词漏召回、低价值片段挤占 Context 的问题。RAG 只负责选择候选证据；版本、权限、敏感信息和 Citation 有效性继续由确定性代码控制。

> 用户需求 ↓ Repository Snapshot ↓ Code / Doc Chunk (commit / path / startLine / endLine / language / contentHash) ↓ Keyword Retrieval + Vector Retrieval ↓ Metadata / Permission / Version / Sensitive Filter ↓ 可回滚 Hybrid 实验（不预设采用） ↓ 可选 Rerank（只有 Dev 数据证明排序问题时） ↓ Citation Validation ↓ EvidenceBundle ↓ Context Builder / Token Budget ↓ Coordinator → Specialists → Synthesis → Review → Artifact

### 4.1 Fake / Live 证据边界

| 模式 | 允许证明什么 | 不允许证明什么 |
| --- | --- | --- |
| Deterministic Fake Embedding | 协议契约、维度、批处理、稳定索引、错误分类、fallback、Citation 集成 | 不能证明语义召回质量、Recall@K、Hybrid 优势 |
| 真实 Embedding | 语义检索质量、Recall/MRR、Threshold、Vector/Hybrid 对比 | 不能单独证明完整 Agent 最终回答质量 |
| 真实 Embedding + 真实 LLM E2E | 代表性 Live 端到端证据、Latency/Token、最终 Artifact 行为 | 不能替代固定 Benchmark 与 Holdout |

### 4.2 无答案阈值 ADR

- Day 8 只记录初始假设 T0，例如“Top-1 score + Top1/Top2 margin + Citation validity”的组合规则；明确标注为未验证。
- Day 15–20 只使用 Dev Set 校准阈值与规则，不允许查看 Holdout 来调参数。
- Day 21 冻结 threshold / strategy / prompt 后，再运行 Holdout。
- 如果不同 Embedding Provider 的分数尺度不同，阈值必须与 Provider/Index 版本绑定，不能当成跨模型常量。

## 5. 第一周：接管 SpecFlow + 三次短校准

| 天 | 任务 | 硬时间盒 / 交付 |
| --- | --- | --- |
| Day 1 | 冻结 branch/commit/git status；阅读规则和 README；运行 pytest、Ruff、benchmark；先画系统图 | 全天主线；基线记录 + 原始架构图 |
| Day 2 | LLM 三组小实验：采样、上下文位置、结构化输出；只补当天必要概念 | 实验表 + 五种失败解释 |
| Day 3 | agent-skeleton 只读 ReAct Tool Loop，再对照 SpecFlow 受控 Tool / Evidence | agent-skeleton 最多 4h；状态机图 + 1 个故障后立即切回 |
| Day 4 | 追 list_files / search_code / read_file / EvidenceCollector / EvidenceBundle | Keyword baseline 能力与缺口 |
| Day 5 | 上午长上下文/冲突证据；下午 diet-agent 对照 session / phase / slots / history 与 Run State | diet-agent 最多 3h；四类状态边界表后立即切回 |
| Day 6 | 追 Coordinator、并行 Specialist、Handoff、Review、Revision、Artifact；制造失败 | 状态图 + Handoff 图 + 失败终态表 |
| Day 7 | 关闭资料做 5 分钟讲解；提交本人设计的最小 Patch + 失败测试；留 2–3h 缓冲 | 第一周 Ownership 证据包 |

> 第一周 Gate<br>不看文档画出 SpecFlow 主链；能区分开放式 ReAct Tool Loop 与受控 Evidence Tool；能区分 Conversation State、Workflow State、RAG Knowledge、Long-term Memory；完成一次故障定位和一个最小修改。

## 6. 第二周：先用 Fake 保证闭环，再为真实语义评测做准备

| 天 | 任务 | 当天交付 |
| --- | --- | --- |
| Day 8 | 冻结 RAG 合同、失败语义和非目标；创建 30 条案例模板；写向量存储 ADR + 无答案规则 T0 + Dev/Holdout 协议 | RAG 规格 + ADR + 数据纪律 |
| Day 9 | 设计 Chunk 模型：commit / path / line / language / contentHash | Schema + 合同测试 |
| Day 10 | 实现代码/文档 Chunk；处理空文件、二进制、超大文件、敏感路径 | Chunker + 边界测试 |
| Day 11 | 实现 Embedding Protocol + Deterministic Fake；覆盖维度/批次/错误/稳定性 | Fake 合同测试；不声称语义效果 |
| Day 12 | 基于 Fake 跑通 Top-K Vector Retrieval、Metadata 过滤、稳定排序、去重 | Retriever 工程闭环 + failure tests |
| Day 13 | 实现 Citation Validation，并转换为 EvidenceBundle | 可重定位 Citation + 集成测试 |
| Day 14 | 接 Context Builder；验证 Fake 失败回退、旧索引拒绝、敏感路径隔离；接 1 个真实 Embedding Provider 做 smoke test | 第二周端到端工程证据包 + real embedding smoke |

> 第二周 Gate<br>即使真实 Embedding Provider 暂时不可用，工程闭环也能用 Fake 完成；但进入第三周质量 Benchmark 前，必须至少有一个真实语义 Embedding 可稳定运行。Fake 不能进入 Recall/Hybrid 质量结论。

## 7. 第三周：Dev 调参，Holdout 只做最终验证

| 天 | 任务 | 数据纪律 / 交付 |
| --- | --- | --- |
| Day 15 | 冻结 30 条案例并拆分 20 Dev + 10 Holdout；记录 case_id 与类别；真实 Embedding smoke 通过；跑 Keyword Dev baseline | Holdout 密封；Dev baseline |
| Day 16 | 只在 Dev 上跑 Vector baseline，记录 Recall/MRR/Citation/Token/Latency | Vector Dev 指标表 |
| Day 17 | 只在 Dev 上实验 Keyword + Vector 融合；不预设 Hybrid 上线 | Hybrid Dev 对比 |
| Day 18 | 只在 Dev 上校准 Retrieval Strategy、无答案 threshold；只有排序问题明确时实验 Rerank | 方案候选 + threshold 决策 |
| Day 19 | 只在 Dev 上比较 Top-K、Chunk Size、Context Budget | 参数对照表 |
| Day 20 | 只在 Dev / 安全专用案例上做 Prompt Injection、越界、敏感文件、旧索引、无答案压力测试；冻结代码/参数/Prompt/Threshold | 冻结候选版本 + 安全矩阵 |
| Day 21 | 先跑完整 Dev Benchmark；随后对冻结版本运行 Holdout 一次；不得根据 Holdout 回调参数；同时写 3 条简历技术事实初稿 | 第三周评测裁决 + Holdout 报告 + 简历初稿 |

### 7.1 30 条案例固定拆分

| 类别 | Dev | Holdout | 总数 | 观察重点 |
| --- | --- | --- | --- | --- |
| 精确关键词 | 5 | 3 | 8 | Keyword 不能明显退化 |
| 语义改写 | 5 | 3 | 8 | 真实语义检索是否召回代码 |
| 多文件链路 | 4 | 2 | 6 | 入口/服务/状态/测试是否共同进入证据 |
| 无答案 | 3 | 1 | 4 | 证据不足时是否安全拒答 |
| 安全与旧索引 | 3 | 1 | 4 | 敏感路径/越权/版本失配是否拒绝 |
| 合计 | 20 | 10 | 30 | Day 21 前 Holdout 不参与调参 |

> 第三周 Gate<br>最终方案由质量、延迟、Token、复杂度和 Holdout 泛化共同决定。Hybrid / Rerank 没明显收益可以拒绝采用。Holdout 结果即使差，也只记录，不回头“修测试集”。无效 Citation 为 0；无答案与安全案例有合法终态。

## 8. 第四周：工程收敛、cms-flow 校准、证据包装

| 天 | 任务 | 硬边界 / 交付 |
| --- | --- | --- |
| Day 22 | 上午记录 scan/chunk/embed/retrieve/filter/context/agent 阶段；下午只读 cms-flow：TopoScheduler / Executor / Resilience / MDC | cms-flow 最多 3h；四张契约/思想图 + 200 字迁移/不迁移笔记 |
| Day 23 | 覆盖 Provider 超时、限流、批次失败、索引不可用、重试上限；仅在有数据时讨论有界并发/Backpressure/Reject | 可靠性测试 + ADR；无压测证据则不实现资源治理 |
| Day 24 | 验证重复索引幂等、新 commit、删除/重命名后的 Citation；评估 contentHash 增量 Embedding | 版本一致性 + 增量索引测试 |
| Day 25 | 真实 Embedding + 真实 LLM 跑代表性 Live E2E；明确与 Benchmark/Holdout 的证据边界 | Live 验证记录 |
| Day 26 | 让新上下文 Reviewer 审查冻结规格、Diff、Test、Benchmark、Holdout 和失败样例 | 独立 Review + 处置记录 |
| Day 27 | 全部旧/新测试、Ruff、格式、CI、新环境复现；保留缓冲时间 | 绿色质量门禁 |
| Day 28 | 把 Day 21 技术事实初稿压缩成 2–3 条简历 Bullet；逐个核验数字与证据路径 | 作品集证据包 + Bullet v2 |
| Day 29 | Codex 以面试官方式攻击 Bullet：数据泄露、threshold、Hybrid、30 条是否够、个人贡献；回源码补证据 | 答辩记录 + 最后必要修正 |
| Day 30 | 无笔记演示：需求 → 检索 → Citation → Multi-Agent → Artifact → 故障 → Trace → Dev/Holdout 指标 | 最终验收报告 + Bullet Final |

> 第四周 Gate<br>README 可复现、Benchmark 可重跑、Holdout 未泄露、失败边界明确；本人能在 5 分钟内讲清设计、数据、替代方案和贡献。OTel、MCP、SSE 未完成不阻塞交付。

## 9. cms-flow：只做接口契约对比，不做第二主线

| 文件 / 主题 | 只问什么 | 输出 | 禁止 |
| --- | --- | --- | --- |
| TopoScheduler.java | 输入、依赖状态、输出、失败传播；为什么可以分波并行？ | DAG/Barrier 图 | 不逐行通读 105 个 Java 文件 |
| FlowExecutorRegistry.java | 资源为什么隔离？共享池的风险是什么？ | Executor isolation 图 | 无压测证据不迁移线程池体系 |
| NodeResilienceGuard.java | 何时 fallback / fail？异常如何传播？ | Failure hierarchy 图 | 不复制 CircuitBreaker 代码 |
| MdcPropagatingExecutor.java | Context 如何复制、恢复、清理？ | Async context 图 | 不把 OTel 扩成主线 |
| ResponseCacheCoordinator.java | LKG/SWR 依赖什么 freshness 语义？ | 迁移 / 不迁移表 | 旧 commit Evidence 绝不当当前事实 |

> 3 小时沙漏<br>cms-flow 只需要得到 4 张图 + 1 段“为什么不直接迁移”的笔记。时间到立即切回 SpecFlow。真正需要迁移的功能，必须由第四周的真实 Benchmark / Failure 证据触发。

## 10. Codex 共学协议

| 模式 | Codex 做什么 | 你必须做什么 |
| --- | --- | --- |
| SURVEY | 定位入口、调用链、状态、关键 symbol，只给源码证据 | 自己画图并复述 |
| TUTOR | 解释当天必要概念，并绑定代码 | 给出反例、边界与适用条件 |
| FAULT | 设计可复现故障、合法终态、观察点 | 先预测，再亲手复现与定位 |
| PATCH | 只实现你批准的最小方案 | Review Diff，理解关键行 |
| REVIEW | 从正确性、状态、权限、Test/Eval、安全挑战方案 | 决定接受/拒绝并说明理由 |

### 10.1 单次学习循环

1. SURVEY：只定位，不改代码。

2. 你自己追链并画图。

3. FAULT：Codex 给 3–5 个故障；你先预测。

4. 你亲手复现、定位根因。

5. 你提出失败语义与修复方案。

6. PATCH：Codex 只做最小修改。

7. 你 Review Diff + 跑 Test/Eval。

8. REVIEW：找反例和遗漏。

9. 写证据卡：问题、预测、结果、根因、改动、指标、取舍。

## 11. 每天 6–8 小时与延期处理

| 时间 | 动作 | 要求 |
| --- | --- | --- |
| 30m | 主动回忆 | 不看笔记画链路 / 回答 3 个问题 |
| 60m | 必要概念 | 只补当天代码要用的知识 |
| 90m | 源码追链 | 记录入口、对象、状态、真相源 |
| 150m | 实验 / 故障 / 本人修改 | 先预测和设计，再允许 PATCH |
| 60m | Test / Eval / Trace | 保存命令、退出码、关键输出 |
| 30m | Review Diff | 解释关键行，拒绝额外重构 |
| 30m | 证据卡 | 问题、根因、改动、结果、取舍 |

### 11.1 如果进度落后，按这个顺序砍

1. 先砍 SSE / MCP / OTel 的实现，只保留概念与 ADR。

2. 再砍 cms-flow / 外部供体的阅读深度，但保留硬时间盒校准结果。

3. 再砍 Rerank、复杂 Hybrid、额外 Provider 支持。

4. 不砍：Citation validity、旧 commit 拒绝、Dev/Holdout、无答案、安全案例、核心回归测试。

5. Day 7/14/21/28 允许作为缓冲/复盘日，但 Gate 标准不降低。

> 体力纪律<br>这是 30 天工程冲刺，不是连续 30 天满负荷编码。Gate 日优先复盘、修缺口和睡眠恢复；不要用熬夜换“多写一个功能”。

## 12. 证据与简历三阶段

| 时间 | 只做什么 | 产物 |
| --- | --- | --- |
| Day 21 | 写技术事实，不追求简历文风：问题、方案、Dev/Holdout、失败边界、实际数据 | 3 条技术事实初稿 |
| Day 28 | 压缩成简历 Bullet；所有数字回指 Benchmark/报告 | Bullet v2 + 证据路径 |
| Day 29–30 | 让 Codex 攻击：数据泄露？threshold 怎么来？为什么 Hybrid？你自己写了什么？ | Bullet Final + 答辩脚本 |

## 13. 最终验收清单

- [ ] SpecFlow branch / commit / baseline 有明确记录。
- [ ] 能不看文档画出 Evidence → Context → Multi-Agent → Artifact 主链。
- [ ] agent-skeleton / diet-agent / cms-flow 都遵守硬时间盒，没有演变成第二开发主线。
- [ ] Repository RAG 能在当前 commit 上生成可重定位 Citation。
- [ ] Fake Embedding 只用于工程契约；真实 Embedding 才用于语义质量 Benchmark。
- [ ] 30 条案例固定拆成 20 Dev + 10 Holdout；Day 21 前 Holdout 未参与调参。
- [ ] 无答案 threshold / strategy 有 Day 8 初始假设、Dev 校准记录和冻结版本。
- [ ] Keyword / Vector / Hybrid 结果可重复；最终方案没有为简历预设 Hybrid 必须采用。
- [ ] Holdout 只对冻结版本运行一次；结果差也没有回调参数。
- [ ] 无效 Citation 为 0；无答案、安全、旧索引案例都有合法终态。
- [ ] Embedding / Index / Provider 失败有 Test 与 fallback / fail-closed 证据。
- [ ] 旧 commit Evidence 不会冒充当前事实；contentHash / 幂等 / 版本一致性已验证。
- [ ] 全部旧/新测试、Ruff、格式、CI、新环境复现通过。
- [ ] Day 21 有技术事实初稿；Day 28 有证据支撑的 2–3 条 Bullet；Day 30 能无笔记答辩。
- [ ] 所有性能/质量数字都能指向实际报告，没有把计划或 Fake 结果写成已完成的 Live 效果。

> 完成判断<br>V5.1 的目标不是“功能最多”，而是“证据最干净”：数据没泄露、Fake/Live 边界清楚、阈值可解释、失败可复现、个人贡献可定位。Day 30 面对追问时，你能从 commit、Diff、Test、Benchmark、Holdout 和设计 ADR 回答，而不是靠记忆项目介绍。

## 14. Day 1 开场指令（直接给 Codex）

> 当前任务是 SpecFlow 30 天能力战役 Day 1。只做只读基线调查，不修改代码。 1. 读取仓库规则、规格基线和当前 README。 2. 记录 branch、commit、git status 和最近 CI 状态。 3. 给出完整验证命令，但先不要替我解释架构。 4. 定位 CLI/API、EvidenceCollector、Context Builder、Coordinator、Agents、 Handoff、Workflow、Eval、Artifact 的入口文件与关键 symbol。 5. 只输出证据位置和待我回答的问题；不能从代码证明的内容标记 unknown。 我会先画架构图并复述，你再根据源码指出遗漏。

版本定位：V3 是长期能力地图；V5 是 30 天主线；V5.1 在 V5 上增加执行纪律与数据诚信规则，是当前建议直接执行的版本。
