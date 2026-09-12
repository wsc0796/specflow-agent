# AI Agent 工程化学习路线

> 历史版本：本路线已于 2026-09-07 被
> [ROADMAP_V5_3_2.md](ROADMAP_V5_3_2.md) 取代。当前学习阶段与后续计划不得再从本文件推导。

*SpecFlow 主线 · 30 天能力战役 · Codex 共学 · 最终迭代版 V5.3*

> 本文由仓库所有者提供的 V5.3 Word 路线转换而来，是当前 30 天训练总章程；每日只执行 `CURRENT.md` 指向的当天目标。文中的外部生态判断需在触发实现前重新核对官方来源。

> 目标合同 用 30 天、每天 6–8 小时，以 SpecFlow 为唯一开发与简历旗舰项目。85% 时间用于接管现有 Tool、Context、Workflow、Multi-Agent、Eval 与安全链路，并完成 Repository RAG；15% 用于短时校准与最小实验。V5.3 在 V5.2 的 Runtime Safety、Behavior Eval、最小 Durability 基础上，对实际 cms-flow 源码做裁决：cms-flow 仅保留为 ≤2.5h 的底层执行语义供体；Agent Workflow 以上位参考 LangGraph 为主，Durability 以上位参考 Temporal 为主，Java Agent 只在目标岗位触发时看 Spring AI 2.0。任何供体不得演变成第二主线。

| 维度 | 最终约束 |
| --- | --- |
| 目标岗位 | Python 后端 / AI 应用开发 / Agent 后端工程 |
| 唯一开发主线 | SpecFlow Agent |
| 跨项目校准 | agent-skeleton ≤4h；diet-agent ≤3h；cms-flow ≤2.5h；durability-lab ≤2h（仅 SpecFlow 无现成 hook 时）；时间到即停 |
| 评测纪律 | 30 条需求拆 20 Dev + 10 Holdout；Holdout 到 Day 21 前不参与调参 |
| 证据纪律 | Fake 证明工程契约；真实 Embedding 才证明语义检索质量；Live E2E 在 Day 25 |
| 月底交付 | 能运行、能故障、能度量、能解释、能约束副作用、能选择合适 runtime/workflow 抽象、能写进简历 |

> 最终原则 项目服务于能力，不让学习路线服务于项目。只有本人完成的预测、追链、故障定位、设计决策、关键修改和结果解释，才计入 Ownership。任何可选增强都不能挤占 RAG、Eval、Safety 和 Holdout。外部供体只能回答一个明确问题；已有成熟上位实现时，优先做对照实验而不是在 SpecFlow 里重造基础设施。

## 1. V5.3 的十条执行压舱石

| 纪律 | 硬规则 | 为什么 |
| --- | --- | --- |
| 校准项目 Timebox | agent-skeleton 4h；diet-agent 3h；cms-flow 2.5h。时间到无论是否“完全懂”都停止。 | 防止四个仓库之间反复切换导致认知上下文损耗 |
| Dev / Holdout 隔离 | 30 条评测 = 20 Dev + 10 Holdout；Day 15–20 只看 Dev，Day 21 冻结后 Holdout 只跑一次。 | 避免 Top-K / Chunk / Hybrid 调参泄露测试集 |
| Fake / Live 分层 | Fake Embedding 只验证协议、维度、失败、索引、Citation；检索质量必须使用真实语义 Embedding。 | 防止把 deterministic fake 的工程可重复性误当成语义效果 |
| Threshold 是假设 | Day 8 记录初始无答案规则 T0；Day 15–20 用 Dev 校准；Day 21 冻结后再跑 Holdout。 | 避免拍脑袋把 0.7 等常量写成“正确阈值” |
| 简历证据前移 | Day 21 先写技术事实初稿；Day 28 才压缩成 Bullet；Day 29–30 做攻击式答辩。 | 避免月底仓促写成“功能介绍” |
| Runtime Safety 分层 | 先做 Schema / 路径 / 权限硬规则；中风险可用模型 Reviewer 辅助；不可逆或外部副作用必须显式审批；硬拒绝不可被模型覆盖。 | 把“模型觉得安全”与“系统保证安全”分开，限制 Agent blast radius |
| Behavior Eval 轻量旁路 | 另建 8–10 条 Agent Behavior Suite，覆盖 Tool 选择、参数、恢复、终止、权限；与 30 条 RAG Benchmark 分离。 | 避免只看最终答案，忽略中间 Tool trajectory 与失败语义 |
| Durability 只做最小实验 | 只做 1 次 crash→checkpoint→resume + 幂等验证；不引入 Temporal/DBOS/复杂工作流平台，除非真实故障证据触发。 | 先理解恢复语义，不把 30 天主线变成基础设施项目 |
| 供体按能力分工 | cms-flow 只看调度/资源隔离/上下文传播/降级语义；LangGraph 只校准 state/checkpoint/HITL；Temporal 只校准 durability/side-effect；Spring AI 2.0 只在 Java 路线触发。 | 防止一个仓库被当成“万能教材”，让学习内容与目标岗位保持同构。 |
| 不强行迁移 | 外部项目的机制只有在 SpecFlow 出现真实 failure/gap，且能在 ≤2h 内形成可验证实验时才允许迁移；否则只写 ADR/对照卡。 | 避免为了“学到了”而把成熟框架能力硬塞进旗舰项目，破坏主线和证据完整性。 |

> Runtime Safety 红线<br>敏感路径、凭据、越权访问、不可逆删除、强制覆盖、外部发布/发送等高风险动作，不能把“另一个模型审批”当作唯一安全边界。优先硬权限 / sandbox / fail-closed；模型只处理模糊判断，高风险最终交给 Human Approval。

> Holdout 红线<br>Day 21 之前，不允许因为 Holdout 结果去修改 Chunk Size、Top-K、Threshold、Retrieval Strategy、Prompt 或 Rerank。如果 Day 21 Holdout 掉分，记录为泛化结果；不要回头把测试集调好看。

## 2. 学习内容：看、实验、还是必须项目化

| 类别 | 内容 | 停止条件 |
| --- | --- | --- |
| 直接看知识点 | Transformer/Attention 直觉、模型训练基本概念、ReAct/Plan/Reflection 理论、Memory 分类、Prompt Injection / Tool Misuse 原理、MCP/A2A 定位、Durable Execution 直觉、Temporal / LangGraph / Spring AI 2.0 的角色边界 | 能说明它是什么、为什么存在、何时不该用 |
| 看 + 小实验 | Token/Context Window、Sampling、Prompt 顺序、Structured Output、SSE、Tool Schema Validation、HITL、checkpoint-resume；必要时 LangGraph durability micro-lab ≤2h | 做 1–3 个对照实验，能解释失败现象 |
| 必须进项目 | Tool Calling / Runtime Safety、Context Engineering、Workflow/Multi-Agent、Repository RAG、Agent Behavior Eval、Safety | 至少 G4；RAG/Eval/Safety 争取 G5；Durability 只到 G3 |

### 2.1 项目只做训练场

| 项目 | 只承担什么 | 硬停止条件 |
| --- | --- | --- |
| SpecFlow | 唯一开发/简历主线：Tool、Context、Workflow、Multi-Agent、RAG、Eval、Runtime Safety、Trace；只补 1 次 checkpoint/resume | 30 天始终保持主线 |
| agent-skeleton | 校准 ReAct Tool Loop / Observation 回灌 / 循环终止 | 4 小时；输出状态机图 + 1 个故障后退出 |
| diet-agent | 校准 Conversation State / Session / Slots / History | 3 小时；完成四类状态边界表后退出 |
| cms-flow | 底层工程语义供体：Kahn wave/barrier、Executor isolation、MDC context、CircuitBreaker、best-effort side-effect；ResponseCache 仅可选 | ≤2.5h；只读 6 个关键文件 + 5 张对照卡；不改 Java 代码、不完整跑框架 |
| 外部供体 | 按能力选一个上位参考：OpenAI Agents SDK=Runtime；LangGraph=Agent Workflow；PydanticAI=typed/eval；Temporal=Durability；Spring AI 2.0=Java Agent | 单次 1–2h；同一能力只保留一个主参考 + 一个对照；不因热点改主线 |
| durability-lab | 只验证 crash → checkpoint → resume、幂等与外部副作用不重复；优先用 SpecFlow 现成 hook，无 hook 时用 LangGraph 微型实验 | ≤2h；禁止为了打勾自研完整持久化/工作流引擎 |

## 3. 月底能力目标与 Ownership Gate

| 能力 | 月底目标 | 证据 |
| --- | --- | --- |
| LLM / Token / 采样 / Attention | G2：能实验并预测常见失败 | 三组小实验 + 五种失败解释 |
| Prompt & Context | G4：能修改上下文装配与预算策略 | 压力实验 + 最小 Patch + 回归 |
| Tool Calling / Runtime Safety | G4：理解 Tool Loop、Schema、权限边界、side-effect policy 与 HITL | 两种 Tool 模式对照 + 权限决策矩阵 + 攻击/故障案例 |
| Repository RAG | G5：实现、评测并裁决方案 | 20 Dev + 10 Holdout + Citation + Benchmark |
| Memory / State | G3：区分 Conversation / Workflow / RAG Knowledge / Long-term Memory | 状态边界表 + 污染案例 |
| Workflow / Multi-Agent / Durability | G4/G3：解释 Handoff、终止、失败传播；完成一次 checkpoint/resume；能说明何时用 Agent workflow、何时用 durable workflow | 状态图 + required-agent 故障 + crash/resume 证据 + cms-flow/LangGraph/Temporal 角色对照 |
| Eval / Behavior / Safety | G5：定义成功、持续回归、trajectory 与安全合法终态 | 30 条 RAG + 8–10 条 Behavior Suite + 安全反例 |
| Trace / 成本 / 延迟 | G4：定位一次真实问题 | 阶段耗时 + Token + 降级证据 |

### 3.1 Ownership Gate

| Gate | 判断标准 | 示例 |
| --- | --- | --- |
| G0 | 能用自己的话说明目的和失败方式 | Context Window ≠ Memory |
| G1 | 不看笔记画出真实调用链 | 入口 → Context → Agent → Tool/Artifact |
| G2 | 本地能跑，知道关键输入输出 | 拿到一条 Trace / RAG Result |
| G3 | 主动制造并定位失败 | Timeout / 非法 JSON / 旧索引 / 权限拒绝 |
| G4 | 自己设计并完成最小 Patch | fallback / policy / context trim / idempotency |
| G5 | Test / Trace / Eval / 指标证明效果 | Recall / Citation / trajectory / latency / token |
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

### 4.3 Tool Runtime Safety / Permission Boundary

原则：LLM 处理语义上的模糊性；确定性代码负责不可妥协的边界；不可逆或外部副作用需要 Human Approval。模型 Reviewer 可以辅助中风险判断，但不能覆盖 hard deny，也不能替代真正的权限隔离。

| 风险层级 | 默认动作 | 必须留下的证据 |
| --- | --- | --- |
| L0 只读 / 明确安全 | Schema + path/version 校验后自动允许 | tool args + result + trace |
| L1 可回滚 / 低副作用 | Policy 允许；限制范围、次数、timeout；必要时模型 Reviewer | policy reason + bounded execution |
| L2 不可逆 / 外部副作用 | 默认需要 Human Approval；加入 idempotency / dry-run / preview | approval + side-effect result + audit |
| L3 敏感 / 越权 / 明确禁止 | hard deny / sandbox / fail-closed；模型无覆盖权 | deny reason + security event |

> V5.3 最小安全案例<br>至少覆盖：read_file(.env)；越权路径；rm/删除项目目录；git push --force 或等价强制覆盖；外部文本诱导 Agent 改写工具参数；重复 side-effect call。目标不是“拦住所有攻击”，而是证明边界、合法终态和审计链。

## 5. 第一周：接管 SpecFlow + 三次短校准

| 天 | 任务 | 硬时间盒 / 交付 |
| --- | --- | --- |
| Day 1 | 冻结 branch/commit/git status；阅读规则和 README；运行 pytest、Ruff、benchmark；先画系统图 | 全天主线；基线记录 + 原始架构图 |
| Day 2 | LLM 三组小实验：采样、上下文位置、结构化输出；只补当天必要概念 | 实验表 + 五种失败解释 |
| Day 3 | agent-skeleton 只读 ReAct Tool Loop，再对照 SpecFlow 受控 Tool / Evidence | agent-skeleton 最多 4h；状态机图 + 1 个故障后立即切回 |
| Day 4 | 追 list_files / search_code / read_file / EvidenceCollector / EvidenceBundle；同时定位 Tool schema / permission / approval hooks，不存在就标 unknown | Keyword baseline 能力与缺口 |
| Day 5 | 上午长上下文/冲突证据；下午 diet-agent 对照 session / phase / slots / history 与 Run State | diet-agent 最多 3h；四类状态边界表后立即切回 |
| Day 6 | 追 Coordinator、并行 Specialist、Handoff、Review、Revision、Artifact；制造失败 | 状态图 + Handoff 图 + 失败终态表 |
| Day 7 | 关闭资料做 5 分钟讲解；提交本人设计的最小 Patch + 失败测试；补 1 个 tool permission 反例；留 2–3h 缓冲 | 第一周 Ownership 证据包 + Runtime Safety 边界草图 |

> 第一周 Gate<br>不看文档画出 SpecFlow 主链；能区分开放式 ReAct Tool Loop 与受控 Evidence Tool；能区分 Conversation State、Workflow State、RAG Knowledge、Long-term Memory；能指出 Tool permission/approval 应插在哪里；完成一次故障定位和一个最小修改。

## 6. 第二周：先用 Fake 保证闭环，再为真实语义评测做准备

| 天 | 任务 | 当天交付 |
| --- | --- | --- |
| Day 8 | 冻结 RAG 合同、失败语义和非目标；创建 30 条 RAG 案例模板 + 8–10 条 Agent Behavior Suite 模板；写向量存储 ADR + 无答案规则 T0 + Dev/Holdout 协议 | RAG 规格 + Behavior Suite v0 + ADR + 数据纪律 |
| Day 9 | 设计 Chunk 模型：commit / path / line / language / contentHash | Schema + 合同测试 |
| Day 10 | 实现代码/文档 Chunk；处理空文件、二进制、超大文件、敏感路径 | Chunker + 边界测试 |
| Day 11 | 实现 Embedding Protocol + Deterministic Fake；覆盖维度/批次/错误/稳定性 | Fake 合同测试；不声称语义效果 |
| Day 12 | 基于 Fake 跑通 Top-K Vector Retrieval、Metadata 过滤、稳定排序、去重 | Retriever 工程闭环 + failure tests |
| Day 13 | 实现 Citation Validation，并转换为 EvidenceBundle | 可重定位 Citation + 集成测试 |
| Day 14 | 接 Context Builder；验证 Fake 失败回退、旧索引拒绝、敏感路径隔离；确定 Tool Risk L0–L3 映射；接 1 个真实 Embedding Provider 做 smoke test | 第二周端到端工程证据包 + safety policy v0 + real embedding smoke |

> 第二周 Gate<br>即使真实 Embedding Provider 暂时不可用，工程闭环也能用 Fake 完成；但进入第三周质量 Benchmark 前，必须至少有一个真实语义 Embedding 可稳定运行。Fake 不能进入 Recall/Hybrid 质量结论。

## 7. 第三周：Dev 调参，Holdout 只做最终验证

| 天 | 任务 | 数据纪律 / 交付 |
| --- | --- | --- |
| Day 15 | 冻结 30 条案例并拆分 20 Dev + 10 Holdout；记录 case_id 与类别；真实 Embedding smoke 通过；跑 Keyword Dev baseline | Holdout 密封；Dev baseline |
| Day 16 | 只在 Dev 上跑 Vector baseline，记录 Recall/MRR/Citation/Token/Latency | Vector Dev 指标表 |
| Day 17 | 只在 Dev 上实验 Keyword + Vector 融合；不预设 Hybrid 上线 | Hybrid Dev 对比 |
| Day 18 | 只在 Dev 上校准 Retrieval Strategy、无答案 threshold；只有排序问题明确时实验 Rerank | 方案候选 + threshold 决策 |
| Day 19 | 只在 Dev 上比较 Top-K、Chunk Size、Context Budget | 参数对照表 |
| Day 20 | 只在 Dev / 安全专用案例上做 Prompt Injection、Tool Misuse、越权、敏感文件、旧索引、无答案压力测试；跑 Behavior Suite；冻结代码/参数/Prompt/Threshold/Policy | 冻结候选版本 + 安全矩阵 + Behavior Suite 报告 |
| Day 21 | 先跑完整 Dev Benchmark；随后对冻结版本运行 Holdout 一次；不得根据 Holdout 回调参数；复跑 Behavior Suite 作为冻结版本回归；同时写 3 条简历技术事实初稿 | 第三周评测裁决 + Holdout + Behavior 报告 + 简历初稿 |

### 7.1 30 条案例固定拆分

| 类别 | Dev | Holdout | 总数 | 观察重点 |
| --- | --- | --- | --- | --- |
| 精确关键词 | 5 | 3 | 8 | Keyword 不能明显退化 |
| 语义改写 | 5 | 3 | 8 | 真实语义检索是否召回代码 |
| 多文件链路 | 4 | 2 | 6 | 入口/服务/状态/测试是否共同进入证据 |
| 无答案 | 3 | 1 | 4 | 证据不足时是否安全拒答 |
| 安全与旧索引 | 3 | 1 | 4 | 敏感路径/越权/版本失配是否拒绝 |
| 合计 | 20 | 10 | 30 | Day 21 前 Holdout 不参与调参 |

### 7.2 Agent Behavior Suite：只评行为，不扩成第二套大 Benchmark

这 8–10 条案例与 30 条 Repository RAG Dev/Holdout 分离。它们不用于检索调参，而用于固定回归 Agent 的 tool trajectory、恢复、终止和权限行为；每条至少记录“预期动作 → 实际 trajectory → 合法终态”。

| 类别 | 代表案例 | 通过标准 |
| --- | --- | --- |
| Tool Selection | 需求应先 search_code 而非盲读全仓 | 选对工具，额外调用受控 |
| Argument Validation | 路径/JSON 参数非法 | Schema 拒绝或修正，不带错执行 |
| Timeout / Retry | Tool 或 Provider 超时 | bounded retry，达到上限后 fallback/fail |
| Loop Termination | Observation 重复导致循环 | 命中 loop guard / max turns，合法终止 |
| Permission | 读取 .env / 越权路径 | hard deny；模型无覆盖权 |
| Prompt Injection | 外部文本诱导修改工具参数 | 不提升权限；危险动作拒绝/审批 |
| No Evidence | 证据不足仍被要求下结论 | 安全拒答或标 unknown |
| Handoff / Failure | required specialist 失败 | 失败传播符合契约，不伪造成功 |

> Behavior Eval 红线<br>最终答案“看起来对”不代表 Agent 行为正确。至少保留 tool name、arguments、关键 observation、retry/approval/deny、terminal state；不要为了凑指标引入 LLM-as-Judge 大工程，先做确定性可判定案例。

> 第三周 Gate<br>最终方案由质量、延迟、Token、复杂度和 Holdout 泛化共同决定。Hybrid / Rerank 没明显收益可以拒绝采用。Holdout 结果即使差，也只记录，不回头“修测试集”。无效 Citation 为 0；无答案、安全与 Behavior Suite 案例都有合法终态。

## 8. 第四周：工程收敛、cms-flow 校准、证据包装

| 天 | 任务 | 硬边界 / 交付 |
| --- | --- | --- |
| Day 22 | 上午记录 scan/chunk/embed/retrieve/filter/context/agent 阶段；下午定向读 cms-flow：TopoScheduler → FlowExecutorRegistry/NodeInvokeExecutorResolver → MdcPropagatingExecutor → NodeResilienceGuard → SideEffectRunner；ResponseCacheCoordinator 仅有余量时看 | cms-flow ≤2.5h；输出 5 张“机制→Agent映射→不迁移理由→上位参考”对照卡 |
| Day 23 | 覆盖 Provider 超时、限流、批次失败、索引不可用、重试上限；验证 bounded retry/backoff 与 fail-closed；仅在有数据时讨论有界并发/Backpressure/Reject | 可靠性测试 + ADR；无压测证据则不实现资源治理 |
| Day 24 | 上午验证重复索引幂等、新 commit、删除/重命名后的 Citation；下午做 1 次 durability 实验：SpecFlow 有现成 checkpoint hook 则原地做；没有则 LangGraph micro-lab ≤2h。完成一步后人为 crash，恢复后已完成步骤和外部副作用不得重复 | 版本一致性 + 幂等测试 + 最小 durability 证据；禁止为打勾自研完整 persistence |
| Day 25 | 真实 Embedding + 真实 LLM 跑代表性 Live E2E；保留一次 Tool Policy / Approval 决策 Trace；明确与 Benchmark/Holdout 的证据边界 | Live 验证记录 + permission trace |
| Day 26 | 让新上下文 Reviewer 审查冻结规格、Diff、Test、Benchmark、Holdout、Behavior Suite、安全矩阵和失败样例 | 独立 Review + 处置记录 |
| Day 27 | 全部旧/新测试、Ruff、格式、CI、新环境复现；保留缓冲时间 | 绿色质量门禁 |
| Day 28 | 把 Day 21 技术事实初稿压缩成 2–3 条简历 Bullet；逐个核验数字与证据路径 | 作品集证据包 + Bullet v2 |
| Day 29 | Codex 以面试官方式攻击 Bullet：数据泄露、threshold、Hybrid、30 条是否够、个人贡献；回源码补证据 | 答辩记录 + 最后必要修正 |
| Day 30 | 无笔记演示：需求 → 检索 → Citation → Tool Policy → Multi-Agent → Artifact → 故障/Resume → Trace → Dev/Holdout + Behavior 指标 | 最终验收报告 + Bullet Final |

> 第四周 Gate<br>README 可复现、Benchmark 可重跑、Holdout 未泄露、Behavior Suite 可重跑、Tool Permission 边界与失败终态明确；本人能在 5 分钟内讲清设计、数据、替代方案和贡献。OTel、MCP、A2A、SSE 的完整实现未完成不阻塞交付。

## 9. cms-flow：保留为底层工程语义供体，不作为 Agent 上位框架

| 文件 / 主题 | 只问什么 | 输出 | 禁止 |
| --- | --- | --- | --- |
| TopoScheduler.java | Kahn wave + allOf barrier：依赖何时 ready？慢 sibling 是否拖住下一波？ | DAG/Barrier + critical-path 对照卡 | 不把 wave/barrier 当成 Agent workflow 标准；不迁调度器 |
| FlowExecutorRegistry.java + NodeInvokeExecutorResolver.java | dag / normal / fast / slow / side-effect 为什么隔离？队列满时的 reject/discard 各代表什么？ | Executor isolation / backpressure 图 | 没有压测证据不复制线程池数值；无界 VT 不等于免费并发 |
| MdcPropagatingExecutor.java | 异步线程为什么会丢上下文？复制、恢复、清理的边界是什么？ | Async context 传播图 | MDC 只证明日志上下文，不等价 OTel Trace/Span |
| NodeResilienceGuard.java | CircuitBreaker 解决什么？这里缺 retry / timeout / bulkhead 的什么语义？ | Resilience boundary 卡 | 不把 CircuitBreaker 当完整 reliability stack |
| SideEffectRunner.java | 为什么 LKG/cache 写可以 drop？如果换成发邮件/删除/支付会发生什么？ | Best-effort vs irreversible side-effect 对照 | 不可逆 Agent Tool 绝不能套“拒绝即丢弃/异常吞掉”语义 |
| ExecutionContext.java | 状态只在 ConcurrentHashMap 内存里意味着什么？进程 crash 后还能恢复吗？ | Ephemeral state vs durable state 卡 | 不把它叫 Memory / Checkpoint；不从这里自研 durable engine |
| ResponseCacheCoordinator.java（可选） | SWR、single-flight、LKG 与 freshness 解决什么？是否映射到当前 RAG/Agent failure？ | Cache pattern / 不迁移 ADR | 只有当前 benchmark/failure 证据触发才深入 |

> 2.5 小时沙漏 cms-flow 不再承担“学习一个框架”的任务，只承担 6 个底层工程语义：barrier 调度、资源隔离、异步上下文、熔断边界、best-effort side-effect、ephemeral state。实际源码快照约 123 个主 Java 源文件、约 5.7k 行主源码，但几乎没有项目级行为测试，因此它只能作为设计思想供体，不能作为生产质量证据。时间到立即切回 SpecFlow。

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

1. 先砍 SSE / MCP / A2A / OTel 的实现，只保留概念、协议边界与 ADR。

2. 再砍 cms-flow / 外部供体的阅读深度；cms-flow 最低只保留 TopoScheduler + SideEffectRunner 两张对照卡。

3. 再砍 Rerank、复杂 Hybrid、额外 Provider、完整 Durable Framework 接入。

4. 不砍：Citation validity、旧 commit 拒绝、Dev/Holdout、无答案、安全案例、Tool Permission 硬边界、8–10 条 Behavior Suite、1 次 checkpoint/resume（SpecFlow 或 LangGraph micro-lab）、核心回归测试。

5. Day 7/14/21/28 允许作为缓冲/复盘日，但 Gate 标准不降低。

> 体力纪律<br>这是 30 天工程冲刺，不是连续 30 天满负荷编码。Gate 日优先复盘、修缺口和睡眠恢复；不要用熬夜换“多写一个功能”。

## 12. 证据与简历三阶段

| 时间 | 只做什么 | 产物 |
| --- | --- | --- |
| Day 21 | 写技术事实，不追求简历文风：问题、方案、Dev/Holdout、失败边界、实际数据 | 3 条技术事实初稿 |
| Day 28 | 压缩成简历 Bullet；所有数字回指 Benchmark/报告 | Bullet v2 + 证据路径 |
| Day 29–30 | 让 Codex 攻击：数据泄露？threshold 怎么来？为什么 Hybrid？Tool permission 为什么这样分层？Behavior Suite 怎么判？crash/resume 是否重复副作用？你自己写了什么？ | Bullet Final + 答辩脚本 |

## 13. 最终验收清单

- [ ] SpecFlow branch / commit / baseline 有明确记录。
- [ ] 能不看文档画出 Evidence → Context → Multi-Agent → Artifact 主链。
- [ ] agent-skeleton / diet-agent / cms-flow 都遵守硬时间盒；cms-flow ≤2.5h 且没有变成 Java 第二主线。
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
- [ ] Tool Runtime Safety 有明确 L0–L3 / allow-deny-approval 规则；敏感/不可逆动作没有仅依赖模型审批。
- [ ] Agent Behavior Suite 至少 8 条，可重复记录 Tool 选择、参数、retry、终止、permission 与合法终态。
- [ ] 至少完成 1 次 crash→checkpoint→resume；优先用 SpecFlow 现成 hook，无 hook 时允许 LangGraph micro-lab ≤2h；恢复后已完成步骤和外部副作用没有被重复执行。
- [ ] MCP / A2A / LangGraph / Temporal / Spring AI / 新框架只作为协议、架构或上位实现校准；没有因为热点扩成第二开发主线。
- [ ] Day 21 有技术事实初稿；Day 28 有证据支撑的 2–3 条 Bullet；Day 30 能无笔记答辩。
- [ ] 所有性能/质量数字都能指向实际报告，没有把计划或 Fake 结果写成已完成的 Live 效果。

> 完成判断<br>V5.3 的目标不是“功能最多”，而是“证据最干净且边界更完整”：数据没泄露、Fake/Live 边界清楚、阈值可解释、Tool 副作用受控、Agent trajectory 可回归、失败可恢复、个人贡献可定位。Day 30 面对追问时，你能从 commit、Diff、Test、Benchmark、Holdout、Behavior Suite、Trace 和设计 ADR 回答，而不是靠记忆项目介绍。

## 14. Day 1 开场指令（直接给 Codex）

> 当前任务是 SpecFlow 30 天能力战役 Day 1。只做只读基线调查，不修改代码。 1. 读取仓库规则、规格基线和当前 README。 2. 记录 branch、commit、git status 和最近 CI 状态。 3. 给出完整验证命令，但先不要替我解释架构。 4. 定位 CLI/API、EvidenceCollector、Context Builder、Coordinator、Agents、 Handoff、Workflow、Eval、Artifact 的入口文件与关键 symbol。 5. 额外定位 Tool schema / permission / approval / loop guard / checkpoint / trace 的现有 hook； 找不到就明确标记 unknown，不要为了满足路线臆造组件。 6. 只输出证据位置和待我回答的问题；不能从代码证明的内容标记 unknown。 我会先画架构图并复述，你再根据源码指出遗漏。

## 15. 外部校准雷达：每周 1–2h，不追热点

Gate 日（Day 7/14/21/28）任选 60–90 分钟扫描一次外部信号。目的不是“跟最新框架”，而是验证：当前路线是否遗漏了重复出现的生产能力。只有当一个信号同时满足“与当前失败/岗位相关 + 多个高质量来源重复 + 能在 2h 内形成可验证实验”时，才进入下一迭代。

| 来源 | 只问一个问题 | V5.3 的硬边界 |
| --- | --- | --- |
| OpenAI Agents SDK | Runtime 如何组织 Tool / Handoff / Guardrail / Session / HITL / Trace？ | Python Agent Runtime 首选对照：primitives、tool guardrail、HITL、trace；不迁框架 |
| LangGraph | State / checkpoint / resume / HITL / fault-tolerance 的失败与恢复语义是什么？ | Agent Workflow 的首选上位参考；仅做 micro-lab/源码对照，不重写 SpecFlow |
| PydanticAI | Typed Tool / Schema / Eval / Graph / durable integration 怎样工程化？ | Python typed/eval 参考；和 LangGraph 不重复做同一 workflow 实验 |
| MCP | Agent↔Tool/Resource 的协议边界当前是什么？ | 版本敏感，以官方最新 spec 为准；不做主线 |
| A2A | 何时真需要 Agent↔Agent 跨系统协作？ | 知道边界即可；无真实跨系统需求不实现 |
| mini-SWE-agent | Agent loop 最少能简单到什么程度？ | 用来反复杂化，不复制成第二项目 |
| Anthropic Eng / OWASP | Harness、Tool、Context、Sandbox、Agentic 风险出现了什么新证据？ | 只把可映射到当前 Failure/Safety 的项加入 backlog |
| 岗位 / 社区 | 最近 20 个 JD / 工程讨论重复出现什么生产能力？ | 只记重复信号；Stars、热搜、单篇帖子不能触发改计划 |
| Temporal | Workflow history、retry、crash recovery、Activity/side-effect 的可靠性语义是什么？ | Durability 的首选上位参考；只读官方 sample/文档，除非岗位或真实 failure 需要，不接入 SpecFlow |
| Spring AI 2.0 | Java ToolCallingAdvisor 如何把 tool loop 变成可拦截、可组合的 advisor？ | 仅 Java Agent 岗位触发；当前 Python/Agent 主线不实现 |
| LangGraph4j（可选） | 如果必须留在 JVM，stateful agent graph 与 Spring AI/LangChain4j 如何组合？ | 只在明确 Java 目标岗位时看；不替代 Python LangGraph 主参考 |

> 外部校准输出模板 每周只留一张差距卡：Signal → 出现在哪些官方/岗位来源 → V5.3 已覆盖/未覆盖 → 当前真实 failure/gap 是什么 → 缺什么证据 → 主参考是谁 → Action（不动作 / ≤2h 小实验 / 下一版本候选）。同一能力禁止同时启动多个供体。

## 16. cms-flow 实测裁决与“上位替代”选择

这次 V5.3 不是基于项目名称猜测，而是按上传源码快照做了定向检查。结论：cms-flow 对你的计划有帮助，但帮助集中在“传统后端执行语义”而不是 Agent Runtime 本身；最优用法是短时源码供体，不是第二个旗舰项目，也不是要迁入 SpecFlow 的框架。

### 16.1 上传项目的实际价值与边界

| 实测项 | 源码事实 | 对你计划的含义 |
| --- | --- | --- |
| 规模/测试 | 约 123 个主 Java 源文件、约 5.7k 行主源码；未发现项目级测试套件，只有 archetype 示例测试 | 适合读设计，不适合作为“生产可靠性已被验证”的证据 |
| TopoScheduler | Kahn 拓扑 + 同波并行 + allOf barrier | 可学 DAG/依赖/Barrier；要主动比较 readiness-driven / durable agent workflow |
| FlowExecutorRegistry | dag / normal / fast / slow / side-effect 多执行器、队列与拒绝计数 | 可学资源隔离、backpressure、拒绝语义；线程池参数不能无压测迁移 |
| MdcPropagatingExecutor | 跨线程 copy → set → finally restore MDC | 可学 async context propagation；不能把 MDC 当完整 distributed tracing |
| NodeResilienceGuard | Resilience4j CircuitBreaker 门面 | 可学 breaker/fail 边界；当前实现本身不覆盖 retry/backoff/timeout/bulkhead |
| SideEffectRunner | side-effect 池饱和可 drop，任务异常被记录后吞掉 | 对 cache/LKG 可合理；对发邮件/删文件/支付等不可逆 Agent Tool 是反例，必须改成审批/幂等/审计语义 |
| ExecutionContext | ConcurrentHashMap 保存单次 DAG 节点结果 | 这是 ephemeral run state，不是 durable checkpoint；进程崩溃无法据此恢复 |
| ResponseCacheCoordinator | L1/L2、SWR、空值缓存、后台刷新 | 是后端缓存设计供体；除非当前 RAG/Agent 有 freshness/热点问题，否则不进 30 天主线 |

### 16.2 是否存在“上位替代”：不是一个，而是按能力拆分

| 能力 | cms-flow 覆盖 | 上位参考 | V5.3 裁决 |
| --- | --- | --- | --- |
| Agent Runtime / Tool Loop | 弱：不是 LLM/Tool Agent runtime | OpenAI Agents SDK | 主参考。Tool、Handoff、Guardrail、Session、HITL、Tracing 与目标岗位直接同构。 |
| Stateful Agent Workflow | 只有静态 DAG wave | LangGraph | 主上位替代。适合 state、persistence、checkpoint、interrupt/HITL、fault-tolerance。 |
| Typed Python + Eval | 无 | PydanticAI / Pydantic Evals | 类型校验、工具契约、Agent eval 和 durable integration 的 Python 上位参考。 |
| Durable Execution | 无持久化 checkpoint/resume | Temporal | Durability 的上位替代：workflow history、自动恢复、retry、activity/side-effect 语义；但太重，不进 30 天主线。 |
| Java Agent Tool Loop | 无 LLM tool loop | Spring AI 2.0 | 如果目标转 Java Agent，这是更直接的上位替代；ToolCallingAdvisor 可拦截/组合 tool loop。 |
| JVM Stateful Agent Graph | 静态业务 DAG | LangGraph4j（可选） | 若明确 JVM 方向可看；当前不取代 Python LangGraph 主参考。 |
| 底层 Executor / Backpressure | 强，代码直接可见 | 没有必要用“大框架”替掉 | 这一项 cms-flow 反而有教学优势：小、透明、容易追链；保留 2.5h 定向阅读。 |

### 16.3 cms-flow 2.5h 精确阅读路线

| 时间盒 | 只读内容 | 必须输出 |
| --- | --- | --- |
| 0–35 min | TopoScheduler.java | 画 wave/barrier；写出一个“慢 sibling 拖住下一波”的反例 |
| 35–75 min | FlowExecutorRegistry.java + NodeInvokeExecutorResolver.java | 画资源隔离；列出 abort / discard / unbounded VT 的风险 |
| 75–95 min | MdcPropagatingExecutor.java | 画 copy/set/restore；说明 MDC 与 Trace Span 的差异 |
| 95–120 min | NodeResilienceGuard.java + SideEffectRunner.java | 分别写“熔断不等于完整恢复”和“best-effort 副作用不能映射不可逆 Tool” |
| 120–150 min | ExecutionContext.java；有余量再看 ResponseCacheCoordinator.java | 写 ephemeral vs durable 对照；缓存只记录可迁移/不迁移理由 |

停止条件：5 张对照卡完成即退出，不要求把 cms-flow 跑通、不逐行读 123 个 Java 文件、不做 Java Patch。若你未来转 Java Agent 岗位，再单独开 Spring AI / Temporal Java 学习线。

### 16.4 上位替代的官方/市场依据（校准日期：2026-09-06）

1. OpenAI Agents SDK：官方将其定位为 production-ready 的轻量 Agent runtime，原生包含 Agents、Tools/Handoffs、Guardrails、Sessions、HITL 与 Tracing。 https://openai.github.io/openai-agents-python/

2. LangGraph：官方定位为构建 long-running、stateful agents 的低层 orchestration framework，并明确提供 durable execution、persistence、human-in-the-loop、memory。 https://github.com/langchain-ai/langgraph

3. LangGraph Checkpointers/HITL：官方文档说明 checkpoint 可支撑 persistence、fault-tolerance、interrupt 后恢复与 HITL。 https://docs.langchain.com/oss/python/langgraph/checkpointers

4. PydanticAI：官方当前把 Pydantic Evals、Pydantic Graph、durable execution 与 typed agent engineering 放在同一栈中；durable integrations 包含 Temporal、DBOS、Prefect、Restate。 https://github.com/pydantic/pydantic-ai

5. Temporal：官方定位为 Durable Execution platform；Workflow 会在间歇故障后恢复并自动处理失败操作的 retry。Java 官方 samples 已包含 Spring AI durable agent 示例。 https://github.com/temporalio/temporal

6. Spring AI 2.0：官方 2.0 把 tool execution loop 提升为 ToolCallingAdvisor，一等可组合、可拦截，适合作为 Java Agent tool loop 的直接参考。 https://docs.spring.io/spring-ai/reference/api/tools.html

7. LangGraph4j：JVM 生态的 stateful agent graph 实现，可与 Spring AI/LangChain4j 配合；只在明确 Java 路线时作为补充。 https://github.com/langgraph4j/langgraph4j

### 16.5 V5.3 对 V5.2 的最终改动清单

| 项 | V5.2 | V5.3 |
| --- | --- | --- |
| cms-flow | ≤3h、4 张图 | ≤2.5h、6 文件、5 张对照卡；明确“有用但不是 Agent 框架” |
| Durability | 强制在主线做一次 checkpoint/resume | 优先 SpecFlow 原生 hook；没有则 LangGraph micro-lab ≤2h，禁止硬造 persistence |
| 上位参考 | 外部雷达中并列扫描 | 按能力固定主参考：Runtime=OpenAI Agents SDK；Workflow=LangGraph；Durability=Temporal；Java=Spring AI |
| 迁移纪律 | 真实 Benchmark/Failure 触发 | 再加一条：成熟上位实现存在时，默认先对照，不在 SpecFlow 重造 |
| cms-flow SideEffect | 原来只当 side-effect 线程池思想 | 明确作为安全反例：best-effort drop 仅适合 cache/LKG，不适合不可逆 Agent Tool |
| 源码证据 | 抽象的“接口契约对比” | 加入实际文件级证据与项目测试缺口，禁止把供体质量当自己的项目证据 |

版本定位：V3 是长期能力地图；V5 是 30 天主线；V5.1 增加执行纪律与数据诚信；V5.2 补强 Tool Runtime Safety、Agent Behavior Eval、最小 Durability 与外部校准雷达；V5.3 在实际 cms-flow 源码检查与 2026-09 官方生态校准后，把外部供体从“看项目”升级为“按能力选择上位参考”，并明确 cms-flow 只保留底层系统语义训练。当前建议直接执行 V5.3。
