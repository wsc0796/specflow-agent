# AI Agent 工程化学习路线

> 本版本已由 [ROADMAP_V5_3_2.md](ROADMAP_V5_3_2.md) 取代。历史证据仍可引用 V5.3.1，但新的学习任务以 V5.3.2 与 `CURRENT.md` 为准。

*最终执行版 · V5.3.1 Minimal Observability Patch*

*SpecFlow 单旗舰 · Evaluation First · Gap Driven · 30 天*

> 仓库采用记录（非源 Word 正文）：本 Markdown 于 2026-09-07 从用户指定的 V5.3.1 Word 转换，作为当前仓库学习路线真相源。当前采用快照为 `codex/t072-no-evidence-fail-closed@c0721ba`；若路线中的历史 commit 或实现假设与当前源码、测试、`CURRENT.md` 冲突，以当前仓库证据为准。

| 最终定位<br>这不是“30 天实现最多功能”的计划，而是“30 天把一个已有 Agent 系统做成可证明、可约束、可回归、可解释的工程项目”。所有新增功能必须由真实基线、失败或岗位证据触发。 |
| --- |

> 版本冻结原则：从开始 Day 1 起，不再因单篇文章、Stars、热点框架或别人的简历修改主线。只有“当前真实 failure/gap + 多个高质量外部信号 + ≤2h 可验证实验”同时成立，才允许进入 backlog。

> V5.3.1 补丁范围：保留 Evaluation First、Gap Driven、Dev/Holdout、Behavior Suite、Safety 与 ADR。只补齐最小运行时诊断能力，完整 OTel、Grafana、Tempo、Jaeger 平台继续 Deferred。

## 1. 最终目标合同

| 维度 | 最终约束 |
| --- | --- |
| 目标岗位 | Python 后端 / AI 应用开发 / Agent 后端工程 |
| 唯一旗舰 | SpecFlow Agent；30 天不新增第二个开发主线 |
| 训练主轴 | Understand & Correct → Measure → Improve by Evidence → Production Semantics → Portfolio Truth |
| 评测纪律 | 30 条固定 Repository Task：20 Dev + 10 Holdout；Day 21 前 Holdout 不参与调参 |
| 行为评测 | 另建 10 条 Agent Behavior Suite；不与 Retrieval/Task Benchmark 混用 |
| 安全纪律 | 硬权限/Schema/sandbox/fail-closed 优先；模型只判断模糊风险；不可逆副作用要求审批 |
| Durability | 只完成 1 次 crash→checkpoint→resume 语义实验；不为打勾自研持久化平台 |
| Repository RAG | 不再预设必须上线。必须评测现有 EvidenceCollector；仅在真实 semantic recall gap 被 Dev 数据证明后实现 Vector/Hybrid |
| 月底证据 | 代码 + Test + Trace + Benchmark + Holdout + Behavior Suite + ADR + 可复现 README + 2–3 条简历 Bullet |

| 一句话原则<br>先证明现有系统，再决定加什么。Vector、Hybrid、Rerank、Runtime Middleware、Declarative Topology、Checkpoint Store 都是候选方案，不是学习任务本身。 |
| --- |

### 1.1 绝对不变的 P0 能力

- Tool Calling / Runtime Safety：Tool Loop、Schema、permission、side-effect policy、HITL。
- Context / Evidence：证据装配、预算、provenance、no-evidence 合法终态。
- Workflow / State：Handoff、失败传播、终止、typed payload、完整性边界。
- Eval：固定任务、Dev/Holdout、baseline、regression、成本/延迟。
- Failure / Trace：timeout、retry、loop、provider failure、permission deny、traceability。
- Backend engineering：Python、typing/schema、async、HTTP、retry/backoff、idempotency、CI。
### 1.2 条件能力（只有证据触发）

| 候选能力 | 触发条件 | 未触发时 |
| --- | --- | --- |
| Vector Retrieval | Keyword/Evidence baseline 在语义改写类 Dev case 明确漏召回 | 写 ADR：不实现 |
| Hybrid Retrieval | Keyword 与 Vector 呈互补错误分布，组合后有可重复收益 | 保留单一检索 |
| Rerank | 召回正确但排序明显影响 Context/Evidence quality | 不实现 |
| Runtime Middleware | Control Coverage Audit 发现重复/漏控造成真实 correctness 问题 | 不为架构美感重构 |
| Declarative Topology | 固定 topology 明确阻碍实验/维护，有真实修改成本 | 写 deferred ADR |
| Production Checkpoint Store | 真实 long-running failure 需要恢复 | 只做 micro-lab |

## 2. 十二条执行压舱石

| 纪律 | 硬规则 | 目的 |
| --- | --- | --- |
| 单旗舰 | SpecFlow 始终是唯一开发/简历主线 | 避免上下文切换与 Feature Shopping |
| Evidence First | Day 8–14 先测现有系统，再决定第三周做什么 | 避免先写答案再找问题 |
| Dev/Holdout | 20 Dev 调整；10 Holdout 仅冻结后运行一次 | 避免测试泄露 |
| Fake/Live | Fake 只证明协议；语义质量必须真实 Embedding/LLM | 证据分层 |
| Threshold | 初值是 hypothesis；只能 Dev 校准 | 避免拍脑袋常量 |
| Control Coverage | 所有 LLM/Tool/Write 路径必须审计 budget/retry/schema/trace/permission | 防止“规则存在但被旁路” |
| Typed Handoff | Schema compatibility + integrity 必须可测试 | 把 Multi-Agent 从文本拼接提升到工程契约 |
| Runtime Safety | hard deny 不可被模型覆盖；L2 外部/不可逆副作用审批 | 限制 blast radius |
| Behavior Eval | 10 条固定 trajectory regression，与任务 benchmark 分离 | 不只看最终答案 |
| Durability | 只做 1 次 crash/resume + idempotency | 理解恢复语义，不造平台 |
| 外部供体 | 一个能力一个主参考；单次 1–2h；只回答一个问题 | 不追热点 |
| 证据前移 | Day 21 写技术事实，Day 28 Bullet，Day 29–30 攻击式答辩 | 月底不编故事 |

### 2.1 外部供体角色

| 供体 | 只看什么 | 时间盒 / 禁止 |
| --- | --- | --- |
| agent-skeleton | 开放 ReAct Tool Loop / Observation 回灌 / termination | ≤4h；1 张状态机 + 1 个故障；不复刻 |
| diet-agent | Conversation State / Session / Slots / History | ≤3h；状态边界表后退出 |
| cms-flow | barrier、executor isolation、async context、breaker、side-effect、ephemeral state | ≤2.5h；不改 Java，不当 Agent 上位框架 |
| OpenAI Agents SDK | Runtime primitives / guardrail / HITL / trace | 1–2h 对照；不迁框架 |
| LangGraph | state/checkpoint/resume/interrupt/HITL | durability micro-lab ≤2h（仅需要时） |
| Temporal | workflow history/retry/side-effect durability 语义 | 只读官方概念/sample；30 天不接入 |
| PydanticAI | typed tool / schema / eval | 只抽 validation/eval 思想 |
| MCP / A2A | 协议边界 | 知道定位；不做主线 |

## 3. 最终证据架构

| 30 天的“真相源”<br>任何简历事实必须能回到：commit / Diff / Test / Trace / Dev Benchmark / Holdout / Behavior Suite / ADR。不能从计划、Fake、单次 demo 或供体项目质量推导成你的成果。 |
| --- |

### 3.1 Repository Task Benchmark（30 条）

| 类别 | Dev | Holdout | 主要观察 |
| --- | --- | --- | --- |
| 精确关键词 | 5 | 3 | 现有 Evidence/Keyword 不能退化 |
| 语义改写 | 5 | 3 | 暴露 semantic mismatch；是否真的需要 Vector |
| 多文件链路 | 4 | 2 | 入口/服务/状态/测试能否共同进入证据 |
| 无答案 | 3 | 1 | 证据不足是否安全拒答/unknown |
| 安全/旧索引 | 3 | 1 | 敏感路径、越权、version mismatch 是否拒绝 |

> 同一批任务用于 Legacy vs Multi-Agent A/B，但 Retrieval 调参只能看 Dev；Holdout 只对冻结版本运行一次。

> Benchmark 定位：30 条 Repository Task 是固定 Golden Regression Suite，用于发现明显 regression、比较冻结版本和验证工程决策，不用于声称统计意义上的小幅生产质量提升。若要评估统计级生产效果，样本规模需根据真实流量分布、目标指标、允许误差、effect size 和置信要求另行设计。

### 3.2 A/B Eval 必须记录的指标

| 维度 | 最低指标 | 解释重点 |
| --- | --- | --- |
| Task Quality | Task success / rubric pass | 是否真正完成需求，不只写得像 |
| Evidence | Coverage / Citation validity / Unsupported reference | 事实是否有证据且可重定位 |
| Risk | Risk recall / safe abstention | 危险/缺证据场景是否合法终止 |
| Test Quality | 关键验证是否被建议/生成 | 对工程任务是否可行动 |
| Efficiency | Token / latency / LLM calls | 质量增益是否值得成本 |
| Stability | 失败率 / retry / terminal state | 失败是否可解释、可回归 |

### 3.3 Control Coverage Matrix（第一周必须产出）

| 执行路径 | Budget | Retry | Schema | Trace | Permission | DLP/敏感 |
| --- | --- | --- | --- | --- | --- | --- |
| Coordinator LLM | ? | ? | ? | ? | N/A | ? |
| Specialist LLM | ? | ? | ? | ? | N/A | ? |
| Reviewer LLM | ? | ? | ? | ? | N/A | ? |
| Evidence Tools | ? | ? | ? | ? | ? | ? |
| Artifact Write / Side-effect | ? | ? | ? | ? | ? | ? |

> 填表规则：只能写 ✓ / × / unknown，并附源码位置。第一周优先修“× 且能复现”的 correctness gap；unknown 先追链，不脑补。

## 4. 第一阶段：Understand & Correct（Day 1–7）

| Day | 任务 | 当天硬交付 |
| --- | --- | --- |
| 1 | 冻结 branch/commit/git status；读规则/README；跑 pytest/Ruff/已有 benchmark；只读追主链 | Baseline Record + 原始架构图 + 现有验证命令 |
| 2 | LLM 三组小实验：采样、Context 位置、Structured Output；只补必要概念 | 实验表 + 5 种失败解释 |
| 3 | agent-skeleton ≤4h：开放 ReAct loop；对照 SpecFlow 受控 Evidence/Tool | Tool Loop 状态机 + 1 个可复现故障 |
| 4 | 追 EvidenceCollector / EvidenceBundle / list_files/search_code/read_file；开始 Control Coverage Audit | Evidence 主链图 + Control Matrix v0 |
| 5 | 上午长上下文/冲突证据；下午 diet-agent ≤3h 对照 session/phase/slots/history | 四类 State 边界表 + 1 个污染案例 |
| 6 | 追 Coordinator→Specialists→Synthesis/Review/Artifact；重点查 typed handoff / schema compatibility / integrity | Handoff 契约图 + 2 个失败假设 |
| 7 | 关闭资料 5 分钟讲解；亲手复现一个 correctness failure 并提交最小 Patch；补 1 个 tool permission 反例 | Week 1 Evidence Pack + Control Matrix v1 + Patch/Test |

| 第一周 Gate<br>你必须能不看文档画出：Evidence → Context → Coordinator/Specialists → Handoff → Review/Artifact；说清 Conversation State / Workflow State / RAG Knowledge / Long-term Memory；指出 permission/approval 应插在哪里；并亲手修掉一个真实 correctness gap。 |
| --- |

### 4.1 Day 6 必加的 Handoff Correctness Case

| Case | 注入 | 合法终态 |
| --- | --- | --- |
| Schema incompatible | Agent A payload schema 与 Agent B input 不兼容 | 拒绝 handoff；不能让 B “凑合读文本” |
| Integrity tamper | 生成 hash 后修改 payload | 完整性校验失败；trace 记录；不伪造成功 |

## 5. 第二阶段：Measure（Day 8–14）

| 核心变化<br>第二周不预设“我要做 Vector RAG”。第二周唯一目标是建立可信 baseline，并找出当前系统真正的瓶颈。 |
| --- |

| Day | 任务 | 当天硬交付 |
| --- | --- | --- |
| 8 | 定义 Eval Contract；创建 30 条 Repository Task 模板 + 10 条 Behavior Suite；冻结非目标、Dev/Holdout 协议 | Eval Contract v1 + Case IDs + 数据纪律 |
| 9 | 补 gold evidence / expected properties；冻结 20 Dev + 10 Holdout；Holdout 密封 | Dataset v1 + Holdout manifest |
| 10 | 跑 Legacy/Baseline 路径（同模型/同仓库/同任务/同限额） | Legacy Dev Report |
| 11 | 跑 Multi-Agent 当前版本 baseline；禁止为了结果先改 Prompt/参数 | Multi-Agent Dev Report |
| 12 | A/B 对比质量、Evidence、Risk、Token、Latency、LLM Calls；列差距而不是下结论 | A/B Trade-off Table |
| 13 | 逐个分析 Evidence failure：keyword miss、semantic mismatch、context budget、version/permission、ranking | Evidence Failure Taxonomy |
| 14 | 写 Evidence Retrieval ADR：A 当前 keyword 足够；B semantic gap 明确；C 数据不足。同步确定 Tool Risk L0–L3 policy v0 | Retrieval ADR + Safety Policy v0 + Week 2 Gate |

| 第二周 Gate<br>你必须能用真实 Dev 数据回答：Multi-Agent 比 baseline 好在哪里、代价是什么；现有 EvidenceCollector 真正失败在哪里；Vector 是否有必要。如果答案是“没有证据”，合法结论就是“不实现”。 |
| --- |

## 6. 第三阶段：Improve by Evidence（Day 15–21）

Day 15 先根据 Day 14 ADR 选择分支。两个分支最终都必须在 Day 20 冻结、Day 21 跑一次 Holdout。

| Day | 分支 A：确认 Semantic Retrieval Gap | 分支 B：Retrieval 不是主要瓶颈 |
| --- | --- | --- |
| 15 | 实现真实 Embedding 最小协议/索引；Keyword baseline 再确认 | 补 Control Coverage × 项、typed handoff failure、RuntimeGuard 漏控 |
| 16 | Vector Dev baseline：Recall/MRR/Citation/Token/Latency | Tool Selection / Argument / Timeout / Retry 行为测试 |
| 17 | Keyword vs Vector；只有互补才实验 Hybrid | Loop termination / no-evidence / required-agent failure |
| 18 | 校准 strategy / no-answer threshold；只有排序问题才 Rerank | Prompt Injection / Tool Misuse / Permission / DLP |
| 19 | Top-K / Chunk / Context Budget 对照；保留 complexity/cost | 成本/延迟优化；有数据再讨论并发/backpressure |
| 20 | 跑 10 条 Behavior Suite + 安全专用 Dev；冻结 code/params/prompt/threshold/policy | 同左；冻结 code/params/prompt/policy |
| 21 | 完整 Dev → 冻结 Holdout 一次 → Behavior 回归 → 写 3 条技术事实 | 同左 |

### 6.1 Evidence Retrieval ADR 的三种合法结论

| 结论 | 证据要求 | 第三周动作 |
| --- | --- | --- |
| A. Keyword sufficient | 语义改写/多文件 Dev 没有明显、稳定的 recall gap | 不做 Vector；把时间投入 Failure/Safety/Behavior |
| B. Semantic gap exists | 多条 Dev case 能复现 keyword miss，且 gold evidence 明确 | 做 Vector baseline；再由数据裁决 Hybrid |
| C. Dataset insufficient | case/gold 不稳定，无法区分 retrieval 与任务定义问题 | 先修数据；不做技术结论 |

| 第三周红线<br>Holdout 结果差也不能回头调参数。Vector/Hybrid 没有明显收益，必须允许“拒绝采用”。这不是失败，而是工程裁决。 |
| --- |

## 7. Agent Behavior Suite（10 条固定回归）

| 类别 | 代表案例 | 通过标准 |
| --- | --- | --- |
| Tool Selection | 应先 search_code，而不是盲读全仓 | 选对 Tool；额外调用受控 |
| Argument Validation | 非法 path / JSON | Schema 拒绝或修正；不带错执行 |
| Timeout / Retry | Tool/Provider timeout | bounded retry；达到上限 fallback/fail |
| Loop Termination | Observation 重复 | loop guard / max turns；合法终止 |
| Permission | 读取 .env / 越权路径 | hard deny；模型无覆盖权 |
| Prompt Injection | 外部文本诱导修改 Tool 参数 | 不提升权限；危险动作拒绝/审批 |
| No Evidence | 证据不足仍要求结论 | unknown / safe abstention |
| Required Handoff Failure | required specialist 失败 | 失败传播符合契约，不伪造成功 |
| Handoff Schema | A→B schema 不兼容 | handoff reject；trace 可解释 |
| Handoff Integrity | payload hash 后被篡改 | integrity failure；合法终态 |

> 每条必须保留：expected action → actual trajectory → tool name/args → key observation → retry/approval/deny → terminal state。优先 deterministic grader，不把 LLM-as-Judge 扩成新项目。

### 7.1 Tool Runtime Safety / Permission Boundary

| Risk | 含义 | 默认动作 | 必须证据 |
| --- | --- | --- | --- |
| L0 | 只读 / 明确安全 | Schema + path/version 校验后自动允许 | args + result + trace |
| L1 | 可回滚 / 低副作用 | Policy allow；范围/次数/timeout 有界；Reviewer 可选 | policy reason + bounded execution |
| L2 | 不可逆 / 外部副作用 | Human Approval；dry-run/preview/idempotency | approval + side-effect result + audit |
| L3 | 敏感 / 越权 / 明确禁止 | hard deny / sandbox / fail-closed；模型无覆盖权 | deny reason + security event |

> 最小攻击案例：read_file(.env)、越权路径、删除项目目录、git push --force 或等价强制覆盖、外部文本诱导 Tool 参数升级、重复 side-effect call。

## 8. 第四阶段：Production Semantics（Day 22–27）

### 8.0 Minimal Observability Slice

| 能力定义 / Evaluation 与 Behavior Trace 回答 Agent 行为是否正确。Minimal Observability Slice 回答某一次真实请求为什么慢、为什么失败、失败发生在哪一步。它属于 Day 22 至 27 的硬交付，不等于完整 Observability Platform。 |
| --- |

| Correctness → Evaluation → Regression → Safety → Reliability<br>            → Observability → Diagnosability → Portfolio Evidence |
| --- |

| 层次 | 回答的问题 | 最低记录 |
| --- | --- | --- |
| Evaluation / Behavior Trace | Agent 行为是否正确 | expected action、actual trajectory、tool name/args、retry/approval/deny、terminal state |
| Operational Observability | 一次请求为什么慢或失败，失败在哪里 | 执行链、阶段 latency、provider/model/version、token、retry/error、terminal state、failure location |

| HTTP / CLI Request<br>        ↓<br>Run Context：conversation_id / run_id / step_id<br>        ↓<br>Instrumented Runtime：retrieve / llm / tool / review / response<br>        ↓<br>Structured Events + Trace + Runtime Record<br>        ↓<br>inspect_run.py <run_id><br>        ↓<br>Timeline + Failure Location + Terminal State + Evidence Links |
| --- |

### 8.0.1 ID Contract

| conversation_id<br>      │<br>    run_id ─────── trace_id<br>      │<br>    step_id ────── span_id<br>                    └─ provider_request_id（若 Provider 提供） |
| --- |

| ID | 语义 | 约束 |
| --- | --- | --- |
| conversation_id | 一次持续多轮会话 | 可以包含多个 run |
| run_id | 一次用户请求对应的一次 Agent execution | 排障、评测、重放和运行查询的主要业务 ID |
| step_id | 一次 run 内的逻辑步骤 | retrieve、rerank、llm、tool、review、response |
| trace_id | 一次具体 tracing execution 的技术身份 | 不得与 run_id 混用；resume 可以产生新的 trace |
| span_id | trace 内的一次执行区段 | 与 step_id 关联，但不要求二者相同 |
| provider_request_id | Provider 返回的请求身份 | 只有 Provider 提供时记录 |

### 8.0.2 Span Contract

所有 Span 公共字段：run_id、step_id、operation、status、失败时的 error.type，以及 trace/span 基础上下文。start、end 和 duration 由 tracing/runtime 记录。model 与 token 只属于相关 GenAI Span，不向所有 Span 无差别复制。

| Operation | 按类型增加的属性 |
| --- | --- |
| agent.run | conversation_id、run_id、terminal_state、step_count、loop_count |
| evidence.retrieve | strategy、top_k、result_count、index_version、latency |
| evidence.rerank（若存在） | candidate_count、model 或 strategy、latency |
| gen_ai.chat | provider、model、input_tokens、output_tokens、retry_count、provider_request_id、finish_reason；有 streaming 时记录 ttft_ms |
| tool.execute | tool_name、attempt、timeout_ms、side_effect_level、status |
| stream.response（仅有 streaming 时） | ttft_ms、stream_duration_ms、chunk_count、interrupted、terminal_reason |

| agent.run<br>  ├─ evidence.retrieve<br>  ├─ gen_ai.chat<br>  ├─ tool.execute<br>  ├─ gen_ai.chat<br>  └─ response |
| --- |

| Exporter 边界 / trace-example.json 只是当前最小 exporter / evidence format，不定义 tracing protocol。字段设计保持可映射到 OTel / OTLP，但本阶段不搭建完整平台。 |
| --- |

### 8.0.3 Privacy Contract

| 默认允许记录 | 默认禁止写入 Trace / Log | Payload Debug 前置条件 |
| --- | --- | --- |
| IDs、model/provider、latency、token count、tool_name、status、retry_count、error_type、prompt_version、KB/index version、app/commit version | API Key、Authorization Header、.env、Secret、完整敏感 Tool Result、未脱敏用户数据、默认完整 Prompt、默认完整模型 Response | redaction、sampling、access control、retention policy 必须明确 |

### 8.0.4 Online Runtime Metrics

| 类别 | 最低指标 |
| --- | --- |
| Request | request count、success、error |
| Latency | total latency；样本足够时再报告 p50、p95、p99 |
| LLM | TTFT（仅 streaming）、input/output token、provider/model、retry/error |
| Retrieval | latency、result_count、empty retrieval |
| Tool | tool latency、success、timeout、retry |
| Agent | step_count、loop_count、terminal_state |
| Version | app commit、prompt version、KB/index version |

> TTFT 定义为 request/start 到 first useful token/event；total latency 定义为 request/start 到 terminal response。当前基线没有 streaming，TTFT 记为 N/A。样本不足时不报告 p95/p99 结论。

### 8.0.5 Streaming 条件分支

| 当前基线结论 / 截至 2026-09-07，本地 commit ee4d174 使用同步 httpx.Client.post 完成 Provider 请求，代码中未发现 StreamingResponse、EventSourceResponse、SSE 或 Provider event stream。streaming-contract.md 当前 Deferred，TTFT 标记为 N/A，不新增 SSE 实现。若未来出现真实 streaming 边界，先判断 SDK 是否已完成字节流解析；只有 SpecFlow 自己拥有 HTTP byte stream 时才测试 partial chunk、multi-line data、abnormal EOF、cancel 和 provider error。 |
| --- |

### 8.0.6 Resume Observability Validation

| 检查项 | 必须回答 |
| --- | --- |
| Crash point | 崩溃前执行到哪个 step / span |
| Checkpoint | 保存了什么状态，checkpoint_id 是什么 |
| Resume point | 从哪个 checkpoint 或 step 恢复，resume_from 是什么 |
| Side effect | 恢复后已完成的外部副作用是否重复 |
| Execution link | 恢复前后 execution 能否用 run_id、checkpoint、resume metadata 或 trace link 关联 |

| Day 22 硬交付 / 冻结 observability-contract.md，包含 ID Contract、Span Contract、Privacy Contract、Online Runtime Metrics 和 Minimal Observability Architecture 图。 |
| --- |

| Day | 任务 | 硬边界 / 交付 |
| --- | --- | --- |
| 22 | cms-flow 压缩到约 1h，只看 TopoScheduler / barrier 与 SideEffectRunner；约 1.5h 冻结 Minimal Observability Slice | observability-contract.md：ID、Span、Privacy、Online Runtime Metrics、Architecture 图；cms-flow 两张机制卡；不搭完整 OTel 平台 |
| 23 | Trace-driven Reliability Test：保留 Provider timeout、rate limit、retry limit、fallback/fail-closed；每个 failure test 留下可关联运行证据 | Reliability Matrix + trace-example.json；给定 run_id 可定位失败 step、attempt、error_type、duration 和 terminal state；structured log 含 run_id/trace_id/step_id/event/status |
| 24 | 保留版本、幂等、Citation 与 crash→checkpoint→resume；新增 Resume Observability Validation，不要求恢复前后 trace_id 相同 | 用 run_id、checkpoint_id、resume_from 或 trace link 证明 A→checkpoint→resume→B；验证 side effect 不重复；无法关联时写 known limitation / ADR |
| 25 | 真实 Embedding + 真实 LLM + 代表性 Live E2E + Tool Policy/Approval Trace；新增 Runtime Metrics Record | runtime-record.json 或 runtime-report.md：total_latency、input/output_tokens、retry_count、model/provider、prompt/KB/index version、terminal_state；当前无 streaming，TTFT=N/A |
| 26 | 上午 Independent Review；下午约 2h 完成 3 类 Fault Injection：slow dependency、provider failure、tool failure | fault-injection-report.md：Injection→Expected Observation→Actual Trace→Detect→Locate→Explain→Contract Result；违反 Reliability/Safety 时必须 fix、backlog 或 ADR |
| 27 | 保留全量 Test、Ruff、格式、CI 和新环境复现；新增 Operability Gate，并实现小型 run 查询工具 | Green Quality Gate + scripts/inspect_run.py；给定随机 run_id，3 分钟内输出 conversation/run、model/provider、app/prompt/KB/index version、retrieval/LLM latency、TTFT（当前 N/A）、tool calls、retry、token、failure/error 和 terminal state |

### 8.1 cms-flow 约 1h 的唯一用途

| 机制 | 你只问什么 | 不迁移理由 / 上位参考 |
| --- | --- | --- |
| TopoScheduler / barrier（Day 22 强制） | 慢 sibling 是否拖住下一波？ | 不是 Agent workflow 标准；LangGraph 看 state/persistence |
| Executor isolation（参考） | fast/slow/side-effect 为什么隔离？队列满怎么办？ | 无压测不复制线程数；学习 backpressure 语义即可 |
| MDC context（参考） | 异步线程如何 copy/set/restore？ | MDC ≠ distributed trace/span |
| CircuitBreaker（参考） | breaker 能解决什么，不能解决什么？ | 不等于 timeout/retry/bulkhead 全栈 |
| SideEffectRunner（Day 22 强制） | 为什么 cache/LKG 可 drop，邮件/删除/支付不行？ | 不可逆 Tool 必须审批/幂等/审计 |
| ExecutionContext（参考） | 内存 map 崩溃后还能恢复吗？ | ephemeral ≠ durable；Temporal/LangGraph 看恢复语义 |

> Day 22 只强制完成 TopoScheduler / barrier 与 SideEffectRunner 两张对照卡。其余机制保留为已有笔记和后续参考，不进入当天 Gate，也不扩成 Java 第二主线。

## 9. 第五阶段：Portfolio Truth（Day 28–30）

| Day | 任务 | 交付 |
| --- | --- | --- |
| 28 | 把 Day 21 技术事实压成 2–3 条 Bullet；所有数字逐一回指报告/Trace/Test | Bullet v2 + Evidence Map |
| 29 | 攻击式面试：数据泄露？A/B 是否公平？threshold 如何来？为什么做/没做 Vector？Tool permission 为什么这样分层？Handoff integrity 怎么证？ | 答辩记录 + 最后必要修正 |
| 30 | 无笔记 Demo 保留 baseline→A/B→Evidence→Tool Policy→Multi-Agent/Handoff→Failure/Resume→Dev/Holdout/Behavior；增加 Operational Diagnosis Demo：给 run_id，执行 inspect_run.py，展示 timeline，定位最慢或失败 span，回指 retry/error/terminal state 与 fault evidence | Final Acceptance Report + Bullet Final + Operational Diagnosis Demo；同时回答‘系统做对了吗’与‘系统坏在哪里’ |

### 9.1 简历 Bullet 只能从这个结构长出来

| Bullet 结构<br>问题 → Baseline → 设计/最小改动 → Eval → 指标 → 成本/边界 → 取舍。禁止写“基于 X 实现 Y”式功能列表；禁止写无法回指报告的漂亮数字。 |
| --- |

### 9.2 Deferred Architecture ADR（必须有）

| 30 天内不实现 | 原因 |
| --- | --- |
| Declarative Topology / Workflow DSL | 没有真实修改成本/实验瓶颈就不抽象 |
| Generic RuntimeEngine / Middleware Framework | 只有 Control Coverage 证明 duplication/漏控才重构 |
| Universal EvidenceSource | 第二/第三业务不存在时不做“万能证据接口” |
| specflow-core 抽离 | 没有第二业务复用证据 |
| Production Checkpoint Store | 本阶段只需 durability semantics 证据 |
| 完整 MCP/A2A/OTel 平台化 | 完整平台仍 Deferred。Minimal Observability Slice 不 Deferred：ID、Trace、Runtime Metrics、Fault Diagnosis 与 Operability Gate 本阶段必须完成 |

## 10. 每天 6–8 小时执行节奏与砍项顺序

| 时间 | 动作 | 要求 |
| --- | --- | --- |
| 30m | 主动回忆 | 不看笔记画链路 / 回答 3 个问题 |
| 45–60m | 必要概念 | 只补当天代码要用的知识 |
| 90m | 源码追链 | 入口、对象、状态、真相源、unknown |
| 150m | 实验 / 故障 / 本人修改 | 先预测、再复现、再允许最小 Patch |
| 60m | Test / Eval / Trace | 保存命令、退出码、关键输出 |
| 30m | Review Diff | 解释关键行，拒绝额外重构 |
| 30m | 证据卡 | 问题、预测、结果、根因、改动、指标、取舍 |

### 10.1 进度落后时按这个顺序砍

1. 可砍：完整 OTel platform integration、Grafana / Tempo / Jaeger、多 Provider 扩展、当前无 streaming 时的 SSE implementation、复杂 dashboard。
1. 再砍 cms-flow / 外部供体阅读深度；cms-flow 最低只保留 TopoScheduler / barrier 与 SideEffectRunner 两张对照卡。
1. 再砍 Rerank、复杂 Hybrid、额外 Provider、完整 Durable Framework。
1. 不砍：Control Coverage、Legacy vs Multi-Agent A/B、Dev/Holdout、Citation validity、Tool Permission、10 条 Behavior Suite、1 次 crash/resume、核心 regression、observability-contract.md、最小 Trace、structured log correlation、Live runtime record、Fault Injection 与 Operability Gate。
1. 不砍睡眠来换一个新功能；Gate 日优先复盘与补证据。
## 11. 最终验收清单

- [ ] SpecFlow branch / commit / baseline 记录明确；README 可复现。
- [ ] 能不看文档画出 Evidence → Context → Multi-Agent/Handoff → Artifact 主链。
- [ ] Control Coverage Matrix 已完成，所有 × / unknown 有源码证据与处置结论。
- [ ] Legacy 与 Multi-Agent 在同模型/同任务/同限制下完成 A/B；质量、Token、Latency、LLM Calls 可比较。
- [ ] 30 条 Repository Task 固定为 20 Dev + 10 Holdout；Day 21 前 Holdout 未参与调参。
- [ ] Evidence Retrieval ADR 有明确 A/B/C 裁决；Vector/Hybrid 若上线，必须有 Dev 数据收益；若不上线，有不采用理由。
- [ ] Citation/版本/权限/敏感路径有确定性验证；无效 Citation 为 0 或有明确已知缺陷说明。
- [ ] Tool Runtime Safety 有 L0–L3 / allow-deny-approval；敏感/不可逆动作没有仅依赖模型审批。
- [ ] 10 条 Agent Behavior Suite 可重复运行，含 Tool、retry、termination、permission、Handoff schema/integrity。
- [ ] 至少完成 1 次 crash→checkpoint→resume 语义实验；恢复后已完成外部副作用不重复。
- [ ] Reliability Matrix 覆盖 timeout、rate limit、retry limit、fallback/fail-closed。
- [ ] observability-contract.md 已冻结：conversation/run/step、trace/span、Span 类型和隐私规则明确。
- [ ] 至少一条真实 Live E2E 可以从 run_id 重建 retrieval → LLM → tool → terminal execution。
- [ ] Live E2E 可以报告 latency、token、retry、terminal state；当前无 streaming，TTFT 标记为 N/A。
- [ ] structured log / trace 可以通过 run_id / trace_id 关联。
- [ ] 至少完成 3 个 Fault Injection，每个都满足 Detect → Locate → Explain。
- [ ] crash/resume execution 可以通过 run/checkpoint/resume metadata 关联；已完成 side effect 不重复。
- [ ] Trace/Log 默认不记录 secret 和原始敏感 payload。
- [ ] 给定随机 run_id，3 分钟内可以通过 scripts/inspect_run.py 输出完整执行摘要。
- [ ] cms-flow 约 1h；只有 TopoScheduler / barrier 与 SideEffectRunner 是强制对照卡；没有变成 Java 第二主线。
- [ ] Deferred Architecture ADR 明确列出未实现的 RuntimeEngine/Topology/Evidence abstraction 及原因。
- [ ] 全部测试、Ruff、格式、CI、新环境复现通过。
- [ ] Day 21 技术事实 → Day 28 Bullet → Day 30 无笔记答辩；每个数字都能回指真实报告。
| 完成判断<br>Day 30 不是看你“用了多少 Agent/RAG/框架”，而是看你能否用源码、失败、Test、Trace、A/B、Holdout、Behavior 和 ADR 证明：这个系统为什么这样设计、哪里可靠、哪里不可靠、你具体改了什么、为什么没有做某些看起来更“高级”的东西。 |
| --- |

## 12. 现在开始：Day 1 直接执行

| 今天唯一目标<br>建立可复现 baseline 和真实架构事实。今天不改代码、不讨论 Vector、不做 LangGraph、不做 cms-flow、不优化 Prompt。先知道你面对的系统到底是什么。 |
| --- |

### 12.1 给 Codex / 编码助手的开场指令

| 当前任务：SpecFlow 30 天能力战役 Day 1。只做只读基线调查，不修改代码。<br><br>1. 读取仓库规则、README、规格/设计文档；记录 branch、commit、git status、最近 CI。<br>2. 找到并列出完整验证命令：tests / lint / format / benchmark / demo；先不要替我解释架构。<br>3. 定位 CLI/API 入口，以及 EvidenceCollector、EvidenceBundle、Context Builder、Coordinator、Agents、Handoff、Review、Artifact、Eval 的入口文件和关键 symbol。<br>4. 额外定位：Tool schema / permission / approval / loop guard / RuntimeGuard / retry / checkpoint / trace / DLP 的现有 hook。找不到必须标 unknown，禁止臆造。<br>5. 定位 legacy/baseline 路径和 multi-agent 路径，说明二者入口如何切换，但今天不跑 A/B 结论。<br>6. 对每个结论只给源码证据位置；不能从代码证明的内容标 unknown。<br>7. 最后只给我“证据位置 + 待我自己回答的问题”，不要替我画最终架构图。<br><br>我会先自己画图并复述，再让你根据源码指出遗漏。 |
| --- |

### 12.2 你本人今天必须完成

1. 在任何 AI 解释之前，先自己画一版“入口 → Evidence → Context → Agent/Workflow → Tool/Artifact”的粗图。
1. 运行现有验证命令并保存：命令、退出码、关键输出、运行耗时；失败也原样保存。
1. 建立 baseline.md：branch / commit / git status / Python 版本 / 依赖安装方式 / tests / lint / benchmark。
1. 建立 architecture-v0.md：只写你能从源码证明的对象、状态、调用方向；不懂的标 unknown。
1. 建立 control-coverage-matrix-v0.md：先列执行路径，今天允许大部分是 unknown。
1. 记录 5 个“明天/本周要验证的问题”，不要今天就解决。
### 12.3 Day 1 停止条件

| 必须有 | 不要求 |
| --- | --- |
| 固定 commit + clean/known git status | 理解全部源码 |
| 至少一轮现有 Test/Lint/Benchmark 结果 | 今天修所有失败 |
| 主链粗图 v0 | 今天画“正确”架构图 |
| 关键 symbol 清单 + unknown 清单 | 今天做任何新功能 |
| Control Matrix v0 | 今天讨论 Vector/Hybrid/LangGraph |

| Day 1 结束时问自己<br>“如果明天换一个人接这个仓库，我能不能用 5 分钟告诉他：从哪里进、证据从哪里来、状态在哪里、Agent 怎么协作、结果怎么出去、哪些控制我还没证实？”能回答，Day 1 就完成。 |
| --- |
