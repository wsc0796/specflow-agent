# Day12 — Legacy / Multi-Agent A/B Trade-off Analysis

- 日期：2026-09-22；状态：**DAY12 COMPLETED / DAY13 READY**。
- 唯一仓库：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`；当前本地 checkout，分析起点 `fc78e42b62a8876e65d72b979f103050aa0d7227`。
- 分析对象：Day10、Day11 已冻结的各 20 个 Dev attempts；本轮不产生新 baseline 运行。
- 完整配对：[Case Pair Table](../study/evidence/day-12-case-pairs.md)；[机器记录及逐例 raw locators](../study/evidence/day-12-case-pairs.json)。
- 后续输入：[DAY13_INPUT.md](../study/evidence/DAY13_INPUT.md)。本报告只列观察与候选边界，不作 Retrieval ADR。
- 所有任务语义评分继承历史 AI review，`v1-hypothesis / learner_verified=false`；本次整理不提升 learner ownership。

## 1. 结论与比较边界

Legacy task_success 为 **2/20**（D015、D016），Multi-Agent 为 **0/20**。Legacy 的 20 例均生成了 degraded 最终产物；Multi-Agent 的 4 例在 Evidence 边界提前停止，另外 16 例记录了 Repository Analyst 请求，却没有形成 validated Stage 0 result。失败结构不同，2 与 0 只能描述这批冻结任务，不能识别 topology 的因果效应。

最清晰的 Evidence 差异是：Legacy 在 16 例保存了 744 条 Collector 摘录，但 60 个 Worker 请求均未包含 Repository Evidence；Multi-Agent 的对应 16 个 Repository Analyst 请求包含 744 行带来源摘录，路径、行号、文本及顺序均与这些 Legacy 摘录一致。该差异确认了通用 evidence delivery；两侧完整 Gold fact delivery 仍为 **0/23**。

最重要的未知项仍是 Multi-Agent 16 例的 **S6–S7 unknown**：请求已在客户端调用边界出现，validated Stage 0 result 未形成，历史记录无法区分 Provider/model response、JSON 解析、Schema 或 stage validation。完整 Token 成本两侧均 `unknown`，比较为 `not_comparable`。

## 2. Truth Sources 与冻结身份

原始证据优先于汇总：`attempts.json` 用于集合/终态/父进程计时；`llm-requests.json` 和 `observation-status.json` 用于调用前请求观察；Legacy `sources.json` 用于 matched/selected/excerpts；各 run 的 manifest、trace 和产物用于运行进度。事实与 expected properties 仅从冻结 [Dev v1](../study/datasets/v1/dev.json) 读取。

评分来源：[Day10 Report](day-10-legacy-dev-report.md)、[Day10 Semantic Review](../study/evidence/day-10-legacy-semantic-review.json)、[Day11 Report](day-11-multi-agent-dev-report.md)、[Day11 Semantic Review](../study/evidence/day-11-multi-agent-semantic-review.json)。适用合同为 [Eval Contract v1](../study/eval-contract-v1.md) 和 [Evaluator Contract v1](../study/evaluator-contract-v1.md)。D001 预测来自 [运行前原始记录](../study/evidence/day-11-pre-run-prediction.md)，不作事后改写。

[Day11 Progress Audit](../../artifacts/progress-audit/day11-20260922-142519/DAY11_PROGRESS_REPORT.md)记录的是2026-09-22 14:25–14:37、`c802953`时的历史快照：0 attempted、公平性未裁决。随后14:45–14:49的[Blocker](../../artifacts/progress-audit/day11-20260922-142519/DAY11_COMPLETION_BLOCKER.md)记录controlled-cap需独立适配；15:41预检及15:42–16:09唯一正式运行见[Execution Log](../../artifacts/progress-audit/day11-20260922-142519/DAY11_EXECUTION_LOG.md)。其0 attempted/未ready结论已被后来的20个raw attempts取代；成本和Live contract profile缺口仍有效。本轮只消费审计的进度事实，不把旧停点当作重跑授权。

| 字段 | Legacy | Multi-Agent |
| --- | --- | --- |
| Code revision | `53287306bc1d4aaa2e1e0ff493f520c81096f0a4` | `bc75a6de3cef8bcbf3b0cbbddda00918003cfb0e` |
| Target repository / Gold revision | `08e5a66f8ea8216433c72744adab92aa07d99c45` | 相同 |
| Dataset / annotation | `v1 / v1` | 相同 |
| Dataset freeze | `bf77d19455cb989984dc4f909e6e7ca4b4f91aaf` | 相同；当前 Dev 与冻结内容 JSON 相等，字节差仅 CRLF/LF |
| Provider / model | DeepSeek / OpenAI-compatible / `deepseek-flash` | 相同；不可变模型版本均 unknown |
| 正式运行日期 | 2026-09-14 | 2026-09-22；非同步运行 |
| 输入 | `requirement` only；`authorized-source-v1` | 相同；同一目标源码快照 |
| Config identity | [day10/run-config.json](../../data/day10/legacy-dev/run-config.json) | [day11/run-config.json](../../data/day11/multi-agent-dev/run-config.json) |
| Effective max_selected_files | 5 | **benchmark=5**，`controlled-cap-at-5`；**产品默认=10** |
| Evidence 字符 / tool calls / file bytes | 80000 / 20 / 262144 | 相同 |
| 温度 / 单 Agent output cap | 0 / 3000 | 0 / 3000；Coordinator enrichment 为 1024 |
| 输入预算 | 单 Agent 10000；run input/output/total=50000/12000/62000 | policy 相同；不同路径如何消费预算不能假定等价 |
| LLM call guard | 10 | guarded Agent calls=10；6 次 enrichment 不计入 guard |
| Retry 配置与实际 | Legacy fallback max_retries=1；Provider internal=0；实际 retry=0 | Agent max_retries=0；Provider internal=0；实际 retry=0 |
| Revision / parallel | Legacy 无同构 revision stage | max_revisions=1、max_parallel_agents=3；实际 completed revision=0 |
| Timeout | Provider=60s；policy wall=300s；harness subprocess=330s | 相同；没有顶层 timeout |
| Python / runtime worktree | 3.12.10 / 历史记录为 clean | 相同 |
| Prompt/topology | Analyze → Generate → Review | Coordinator enrichment → Repository Analyst → Design/Test/Risk → Synthesis → Review；实际只到首个 Agent 请求 |
| Case IDs | `SF-RT-D001` 至 `SF-RT-D020`，20 个唯一 ID | 完全相同，按 ID 配对，无重跑或删样本 |

`policy.repository.max_selected_files=80` 是两份 policy 中的上界，不能代替 runner 的有效值。Day10 config 中“Multi-Agent=10 尚未裁决”和 Day11 `comparison_protocol.known_limit_difference` 中的 10 是历史差异记录；Day11 冻结的 `effective_multi_agent_limits.max_selected_files=5` 与 fairness decision 才是正式实验值。请求里被检索到的目标源码 `min(10, ...)` 属于旧目标 revision 的代码事实，也不能反推本次 benchmark 使用 10。

Legacy prompts 均为 1.0.0：`analyze_requirement` hash `b8f42108…ce4c03`；`generate_spec` hash `8a8c00f9…66f7c2`；`review_generation` hash `7d013ab3…18f6da`。Multi-Agent 的 enrichment 模板为 `enrichment/{role}/v1`、version 1.0.0，builder hash `9a92a664…7fbe8`；Agent user-message builder 为 `0dc772f5…6a74`；Repository Analyst system prompt 为 `67ea0797…da9a`，prompt ID `prompts/repository-analyst/v1`。所有完整 hashes、6 个 Agent prompt/schema 身份和 policy 原值已保存在配对 JSON 的 `identity` 中。

Prompt、typed output、fallback 和 topology 的差异属于被比较系统本身。不同 code revisions、不同日期、未知的不可变 Provider 模型版本及缺失的 response 遥测，使本轮不具备单因素因果识别能力。不能改写历史配置来制造“完全相同”。

## 3. 统一 Failure Boundary

| 层 | 观察面 |
| --- | --- |
| S0 | source / Gold：固定 revision 的原始事实与标注 |
| S1 | retrieval-match：候选命中 |
| S2 | ranking-selection：命中候选进入选择集 |
| S3 | read-extraction：读取、摘录与保留事实条件 |
| S4 | context-projection：Evidence 投影到 receiver context |
| S5 | actual-request-packing：实际 LLMRequest 中的消息 |
| S6 | provider/model response：交付、响应、生成内容 |
| S7 | schema/stage-validation：解析、Schema 与 stage 接受 |
| S8 | downstream-agent/workflow：下游进入及传播 |
| S9 | final-generation：最终任务响应/产物 |
| S10 | final-validator/evaluator：最终评分及校验 |

`main_failure_boundary` 与“最早 Gold 缺口”分开：Legacy 有 selected evidence 的 16 例统一记录 **S4–S5 context delivery / request packing gap**，并在逐例 notes 保留 S1/S2/S3 的更早 Gold 问题。不能因为末端接线普遍缺失，就声称此前各层都正确。

Legacy D006/D007/D009/D010 的 sources 明确 matched=selected=excerpts=0，故其最早候选在 S1。Multi-Agent 对应 4 例的 manifest 明确 selected=referenced=0、错误为 `EVIDENCE_NOT_FOUND`，observer 确认 0 调用；本次只确认 **LLM 前 fail closed**，其缺少原始 matched/read 记录，起因范围保留 S1–S3 unknown。

其余 Multi-Agent 16 例保持 **S6–S7 unknown**。`stages_completed=0`、空 `agent-outputs.json`、workflow 从 analyzing 到 failed、只有 enrichment/Repository Analyst 请求共同限定边界。它们不证明 Provider 成功或 JSON/Schema 单独失败。

## 4. A/B Trade-off Table

解释标签仅使用 `observed advantage`、`observed disadvantage`、`not comparable`、`unknown`；标签适用于表中单个观察维度。

| Dimension | Legacy | Multi-Agent | Comparable? | Interpretation |
| --- | --- | --- | --- | --- |
| Task success | 2/20：D015、D016 | 0/20 | 描述性可比；因果不可比 | Legacy observed advantage；成功均为无答案任务，不能推断 topology 胜负 |
| Evidence delivered to actual request | 0/20 cases；0/60 requests | 16/20 cases；16/16 Analyst requests；16/112 全请求 | 可比，但必须标 receiver/分母 | Multi-Agent observed advantage：通用证据进入请求 |
| Gold fact coverage | delivered 0/23，14 eligible cases | delivered 0/23，14 eligible cases | delivery 可比；无请求的4例不能作 Context 语义评分 | 改善优势 unknown；同路径或通用摘录不等于 Gold 支持 |
| Final answer availability | 20/20 degraded generation | 0/20 | 可比于产物可用性 | Legacy observed advantage；质量由独立 task verdict 决定 |
| Fail-closed behavior | 4 个零摘录 case 继续完成 12 次 Worker 请求 | 同4例 LLM 前停止，0 请求 | 可比于行为；safe_abstention 不可比 | Multi-Agent observed advantage 仅限零证据阻断；语义安全 unknown |
| Workflow completion | 20 completed / degraded | 0 completed；20 failed | 终态描述可比；不同合同不能等同结构 pass | Legacy observed advantage；与 Gold/任务正确性分开 |
| Latency | mean 41.788s；median 41.767s | mean 82.465s；median 92.849s | all-attempted wall time 可比；非同终态性能实验 | Multi-Agent observed disadvantage 于整体耗时；4例提前停止较短 |
| LLM/request observations | 60 个调用前记录；56 个有 Provider response usage | 112 个调用前记录；96 enrichment + 16 Analyst；response completion 总数 unknown | 请求数可比；完整 Provider completion not comparable | Multi-Agent observed disadvantage 于请求边界次数；不能推导计费次数 |
| Token completeness | 16/20 complete，56/60 calls 有 usage；full total unknown | 4/20 确认零调用 complete；16/20 usage unknown | **not_comparable** | 不比较完整 Token 或货币成本，不把缺失填 0 |
| Citation support | unknown；source validity 16 pass / 4 fail 不是语义支持 | unknown；无最终 claims/citations | **not_comparable** | scorer/mapping unknown；无答案不能算满分 |
| Measurement quality | 有 sources、Worker trace、最终产物；4次 usage 缺失 | 请求与终态明确；上游完整 sources、response/error、stderr/usage 缺失 | 按观察面比较，不能压成评分 | Multi-Agent observed disadvantage 于事后归因；首次请求证据更完整 |

## 5. Evidence Delivery 分面核对

| 观察面 | Legacy | Multi-Agent | 可知范围 |
| --- | --- | --- | --- |
| Collector produced evidence | 16/20 非空；4/20 空；744 条保存摘录 | 16/20 可由实际请求中的摘录证明非空；4/20 明确零摘录 | Multi-Agent 16例原始 Collector 完整计数 unknown |
| matched files | 20例有列表；case-file 计数合计347（非全局去重） | 16例请求的 `Matched files` 数值可观察，合计347；4例没有该字段 | Multi-Agent 原始 matched 名单20例均 unknown；不得复制 Legacy 名单 |
| evidence selected | 16例各5、4例0；合计80个 case-file selections | 4例 manifest selected=0；16例原始 selected 数/list unknown | 16例各有5个 delivered excerpt 路径，只是下游可见来源，不能冒充原始 selection trace |
| evidence projected | Worker 最终消息中0；独立中间运行快照 unknown | 16个 Analyst 请求有证据，合计744行；4例未调用 | 以最终请求证明投影结果，不虚构中间快照 |
| evidence entered actual request | 0/60；主 receiver Generate 为0/20 | Analyst 16/16；全部请求16/112；case层16/20 | enrichment 的96次不是 Agent 证据请求 |
| complete Gold delivery | 0/23 | 0/23 | 14个 eligible case；6个 unanswerable/safety_reject 的 coverage=N/A |

Multi-Agent 的 16 个 `llm-requests.json` 都保存了 `Matched files: N` 以及带路径/行号的摘录。因此 Day11 报告中“完整上游计数 unknown”仍成立，但 Day12 能从下游重新提取上述 **部分可观测字段**。16个请求的744行摘录与各自 Legacy sources 中的序列逐项相等；这不恢复完整 matched/selected/read traces，也不证明所有事实必要条件被提取。

Gold coverage 的分母细分：14例共23 facts，其中10个实际有 Analyst 请求的 answerable case 含17 facts，完整支持0/17；4个确认零调用的 answerable case 含6 facts，确认 delivered=0/6。因此按全体 delivery 计0/23；若只评价实际存在的 Analyst Context，报告0/17、另列6个 pre-request 未交付事实。没有把丢日志当成0。Macro delivered coverage=14例平均0；eligibility=14，delivery可判定=14，unknown=0，N/A=6。

同路径候选共有5个 **fact-level candidates**，实际分布在 **D002、D003、D014三个请求**：D002 的默认5可见，但拒绝 bool/非正数所需代码条件未进入请求；D003 有 register 等片段，却缺同模型幂等及 frozen 分支条件；D014 有 DLP/投影片段，却缺支撑完整两条 facts 的必要代码。不得将历史报告的“5个 request”文字直接当作5个不同 case。

## 6. Runtime Progress（Day12 描述统计，非产品评分）

| 机械观察 | Legacy | Multi-Agent | 解释 |
| --- | --- | --- | --- |
| stopped before LLM | 0/20 | 4/20：D006、D007、D009、D010 | 有完整 observer 零调用状态支持 |
| actual request observed | 20/20 cases，60 requests | 16/20 cases，112 requests | 调用前 observation，不代表 HTTP 成功 |
| validated first-stage output | 20个本地接受并持久化的 AnalyzeOutput，均 degraded；原始模型输出验证情况 unknown | 0/20 validated Stage0 | Legacy typed Worker/fallback 与 Multi-Agent Stage0 合同不同，此行 not_comparable |
| downstream agent entered | Generate/Review Worker：20/20；同构多 Agent stage=N/A | Design/Test/Risk/Synthesis/Review：0/20 | Legacy 每例3个 receiver 请求；Multi-Agent workflow 未越过 analyzing |
| final response produced | 20/20 degraded generation | 0/20 | artifact存在与语义成功独立 |

所以“哪条路径走得更远”必须分轴回答：Legacy 全20例都走到了最终产物；Multi-Agent 的16例在通用证据交付上到达了 Legacy 没有到达的 S5 状态。S0–S10 是归因观察层，不是可相加的进度分数。

## 7. Risk、Efficiency 与测量限制

### Risk

只消费冻结 evaluator 的已有输出：Legacy D015–D020 的 safe-abstention semantic subcheck 为5 pass / 1 fail（D017），统一 verdict 仍 unknown，因为 product_state_mapping 未冻结。Multi-Agent 没有最终答案，semantic subcheck 与统一 verdict 均 unknown。Day11 failed 不是 safe abstention；4个 EVIDENCE_NOT_FOUND 也不证明仓库没有答案。

Legacy source_reference_validity=16 pass / 4 fail，仅证明路径/存在性；Multi-Agent 没有适用 sources，unknown。Citation support 两侧均 unknown。不存在本轮可比较的 risk recall 或最终回答安全分数，故不新增此类指标。

### Latency 与 Calls

全20个原始 `wall_time_ms` 均纳入，逐例值保存在配对表；不删除失败、降级、零调用。P50 统一用两个中间值的算术平均（median），P95 用 nearest-rank；小样本分位数仅作描述。

| all-attempted | Legacy | Multi-Agent |
| --- | ---: | ---: |
| n | 20 | 20 |
| total ms | 835760.439 | 1649304.614 |
| mean ms | 41788.021950 | 82465.230700 |
| median / P50 ms | 41767.167500 | 92848.946500 |
| P95 ms | 48481.543 | 122133.696 |
| min / max ms | 24441.828 / 52886.011 | 3207.965 / 131638.483 |

同一4个零摘录 case：Legacy mean=44840.604750ms，Multi-Agent mean=3298.737000ms。其余16例：Legacy mean=41024.876250ms，Multi-Agent mean=102256.854125ms。Multi-Agent 16个通用失败与4个提前停止分别报告，不能用提前停止的短时长声称完成任务更快。Legacy 20例终态均 completed/degraded，Multi-Agent 20例均 failed；不存在同成功质量下的性能比较。

Day11 历史报告 P50=92801.186ms 是排序后的第10个值；第11个为92896.707ms。Day12 的统一 median=92848.9465ms，保留历史原值，不回写旧报告。Legacy 历史 P50 本已使用两值平均。

Legacy 60条请求记录、retry=0，其中56个 Worker trace 有响应 usage，故**至少56次客户端已取得 Provider response**；余4次 completion 状态unknown，不能把60全部当成功完成。Multi-Agent 112条观察只证明进入 `complete` 调用边界，成功 response 总数unknown；“有0条已保存 response usage”不等于“Provider完成0次”。

### Token 与其余限制

Legacy 已知小计 input=77787、output=119992、total=197779，仅覆盖56条请求；D001/D008/D013/D019 各缺1次 usage。D012 的 ValueError 出现在已取得 usage 的路径，其计量已包含，不因错误剔除。Multi-Agent 只有4个确认零调用 run 可记成本0，另16个run的usage unknown。双方 full_total=unknown、full_token_cost=not_comparable；不作价格推算。

失败后的 Multi-Agent artifacts 没有 Provider response/error、未提交 Stage0 result 或 worker stderr，`sources.json` 也未持久化。原始 report JSON 的 unknown 占位与后续 semantic review 必须分层读取：占位 task_success 不是“20个真实未知任务”的最终审查，metrics-only request_count=0 不是零请求。观测来源、artifact完整性和语义评分不能互相替代。

两侧只有一次固定小样本运行，无独立人工二次评分、重复实验或不可变模型快照；不作统计显著性、生产收益或未知仓库泛化结论。本轮未读取 Holdout 题面、Gold、输出或运行 Holdout；Day11 报告已记录历史 `audit-access-exception`，所以也不声称整个历史流程严格 blind。

## 8. 五个诊断 Case

以下 Dxxx 均指 `SF-RT-Dxxx`；完整 attempt/run ID 和可点击 raw 文件见 Case Pair Table 的索引。

### D001 — 已命中 Gold 文件，但未被选择

**Expected：** `F-D-EVIDENCE-RANK`，`src/specflow/evidence/collector.py:194–218` / `EvidenceCollector._rank_files`：排序依次比较路径优先级、累计 match_count 的负值、路径字典序；“命中多必定第一”不成立，条件限定在传入候选集。

**Legacy trajectory：** matched=21，Gold 文件在 matched；selected=5却没有 collector.py；44条摘录被保存，三个请求没有 Repository Evidence；生成条件化候选排序方案，未确认实际源码顺序，task fail。

**Multi-Agent trajectory：** Analyst 请求含44行相同通用摘录，包含 matched-count=21，不含 Gold path/_rank_files实现或完整排序条件；6次 enrichment + 1次 Analyst 请求，stages_completed=0、最终答案不存在，task fail。

**Earliest divergence：** 两侧可直接对比的最早差异在 S4–S5 通用 evidence delivery。Legacy 更早的 Gold 缺口是 S2；Multi-Agent 原始 matched/selected 名单unknown，不能照搬 Legacy 的 S2 定位。

**Observed fact：** Legacy Gold locator 已命中但未选；两侧 Gold 完整支持0/1；Multi-Agent 产品失败边界S6–S7。学习者的 Repository Analyst receiver 预测正确，“理由不清楚”保持 incomplete；Gold 已进入请求的前提不成立，不能验证“业务结果校验层”预测。

**Still unknown：** Multi-Agent Gold 在S1–S4何处首次缺失，以及S6与S7何者阻止Stage0形成。

**What Day13 should inspect：** 分开记录 Legacy S2 Gold候选丢失、S4–S5公共接线问题、Multi-Agent S6–S7与上游测量缺口；不把三个问题合成 retrieval failed。

### D002 — selected source 与实际完整事实分离

**Expected：** `F-D-EVIDENCE-CONFIG`，`src/specflow/evidence/models.py` / `EvidenceCollectionConfig`：默认max_selected_files=5，配置必须是正整数、显式拒绝bool；runner可覆盖，不能写每次固定选5。

**Legacy trajectory：** matched=10、selected=5、excerpts=25；Gold所在models.py已被选择，摘录含默认5，却不包含完整类型/正值拒绝条件；三个请求仍无这些摘录，最终未回答必要属性，task fail。

**Multi-Agent trajectory：** 25行摘录进入Analyst请求，包括默认5与runner覆盖片段，但无bool拒绝与完整正值约束；1个Gold路径候选不构成完整fact，0/1；请求后S6–S7失败、无下游。

**Earliest divergence：** S4–S5。Legacy sources 已暴露更早的S3事实条件不完整；Multi-Agent只证明请求中仍不完整，原始读取/提取过程unknown。

**Observed fact：** 本例确实存在“selected evidence → request无evidence”的Legacy交付缺口；Multi-Agent送入了同一摘录序列，但并未送入完整Gold。

**Still unknown：** Multi-Agent的S6–S7原因；仅靠产物不能将不完整事实归为一次具体read失败或预算裁剪。

**What Day13 should inspect：** 对照Gold必要条件与保存的摘录正文，分别登记extraction条件缺失和context交付问题；将目标源码默认10与本次benchmark=5分开。

### D006 — 两侧零 Evidence，后续策略不同

**Expected：** `F-D-EVIDENCE-TRIM` 与 `F-D-EVIDENCE-CONTEXT`：超总字符预算时保留能装下的完整摘录，放不下某项后仍检查后续项；serialized_context只遍历保留的excerpts，selected_files不保证事实可见。事实位于固定revision的collector.py/models.py，任务是answerable。

**Legacy trajectory：** sources明确matched=selected=excerpts=0；仍产生3次Worker请求和degraded生成，输出通用设计而缺实际行为，task fail。

**Multi-Agent trajectory：** manifest为EVIDENCE_NOT_FOUND、selected=referenced=0，observation-status为complete且observed_call_count=0；未进入Coordinator/Agent，无最终答案，task fail。

**Earliest divergence：** 同样零摘录后的LLM前分支：Legacy继续，Multi-Agent阻断。Legacy S1零命中有直接记录；Multi-Agent S1–S3起因unknown。

**Observed fact：** Multi-Agent fail closed；这不是“仓库无答案”，更不是Vector必要性的证明。

**Still unknown：** Day11没有matched名单与搜索/读取全过程；不能直接证明某个关键词、排序或预算因素的因果责任。

**What Day13 should inspect：** 把已知零命中与正确执行fail-closed分开；把“有Gold的任务未交付证据”作为候选检索问题，保留技术选择证据不足。

### D015 — Legacy task pass / Multi-Agent failure

**Expected：** 固定revision没有指定`reports/production/2026-09-12.json`；应明确线上p95和样本数无法确定，不编造数字或用源码默认值/Mock代替。unanswerable，Gold recall=N/A。

**Legacy trajectory：** selected=5、excerpts=44，请求无Evidence；generation.proposed_solution明确当前上下文没有所需报告，应答“无法确定”，历史AI判pass。存在无证据交付缺口并不必然让无答案任务的最终语义失败。

**Multi-Agent trajectory：** 44行通用源码摘录送入Analyst请求；Stage0未形成，最终无拒答文本，task fail，safe-abstention semantic unknown。

**Earliest divergence：** S4–S5通用交付，其后最终输出可用性不同。

**Observed fact：** paired outcome=pass/fail；Multi-Agent failed不能算成功拒答；Legacy的pass是历史AI判定，不是已证明读取指定报告目录。

**Still unknown：** Day11 Stage0原因；Legacy“上下文未提供”与expected的“revision不存在”之间有评分严格度疑点，详见分歧记录，Day12不改冻结分数。

**What Day13 should inspect：** 分开分析task输出缺失、终态、安全拒答与evaluator属性满足证据，不用2/20宣称Legacy拓扑普遍优越。

### D017 — artifact validator 误报与任务失败并存

**Expected：** 缺少`reports/providers/tokenizer-compatibility.json`时明确本次跨Provider缓存/推理Token口径不可确定，不因字段同名声称计量相同。unanswerable，coverage=N/A。

**Legacy trajectory：** selected=5、excerpts=31，实际请求无Evidence；generation仅写“若缺失则不可确定”的方案，没有明确本次结论，历史task fail。artifact validator对sources中的函数名`_bearer_token`报secret_detected，属于已记录误报。

**Multi-Agent trajectory：** 31行通用摘录送入Analyst，Stage0未形成；无最终输出可供Citation/abstention语义判断，task fail。

**Earliest divergence：** S4–S5 evidence delivery；Legacy独立的S10 evaluator误报不是Multi-Agent S6–S7失败原因。

**Observed fact：** source-reference validity可pass、artifact validator可fail、task_success也可独立fail；修正误报认知不能把task改成pass。

**Still unknown：** Multi-Agent S6–S7原因；其缺失答案的语义安全。

**What Day13 should inspect：** 将evaluator false positive单独登记I类，同时保留D类接线与H类未满足输出属性，不能用误报解释全部失败。

## 9. Evaluator Disagreement / Measurement Log

| ID | 观察冲突 | Day12处置 |
| --- | --- | --- |
| E01 / D017 | artifact validator的secret_detected命中源码符号`_bearer_token`；路径校验仍pass | confirmed S10 false positive；保存原finding，不修改evaluator、不改变task fail |
| E02 / D015 | 历史task pass；输出明确不可确定但以“当前上下文未包含”为依据，expected更严格要求指定revision不存在 | 评分严格度争议bounded；保留冻结2/20，标出AI review限制，不假装新增独立人工裁决 |
| E03 / 全20例 | raw report中的task_success unknown是待语义复核占位；后续AI review给出L 2pass/M 0pass | 两种来源并列；最终task计数采用已冻结semantic review，机械产物分不代替任务分 |
| E04 / Multi-Agent全20例 | 原始metrics聚合request_count=0、token complete=0；实际observer有112请求及4个确认零调用 | 请求数采用observer；完整usage仍unknown；4/20仅零调用complete |
| E05 / Day11 latency | 历史P50用第10个值；Legacy使用median | Day12统一median，两侧均重算原始20值，旧文件不改 |
| E06 / D002/D003/D014 | 历史文字“5个request出现Gold路径”与实际3个request不符 | 5指fact-level path candidates，跨3个cases；完整fact仍0 |

这些是AI基于现有证据的复核，不冒充独立人工一致性研究或重新校准后的evaluator版本。

## 10. 四个必须回答的问题

**Q1：Legacy主要已知failure是否发生在Evidence→actual request之间？**

该处是覆盖最广的已确认共同缺口：16/20有摘录却不进入请求，60/60请求均无Evidence。因此它是主要的已知交付问题。不能进一步断言它是18个task fail的唯一/占比最大的因果根因：4例已经S1零命中，D001等有S2遗漏，D002/D003有S3条件缺失；D015/D016在相同接线缺口下仍被历史review判pass。

**Q2：Multi-Agent是否至少消除了本次Legacy“通用Evidence完全不进request”的现象？**

**是，就观察到的交付行为而言。** 16例Analyst请求含对应744行通用摘录，Legacy请求0行；其余4例在LLM前明确停止。该结论不外推为所有路径已修复，也不等于Gold evidence delivery改善：完整Gold仍0/23。

**Q3：为什么Multi-Agent仍0/20？**

Observed：4例EVIDENCE_NOT_FOUND在LLM前fail closed；16例有Analyst请求却没有validated Stage0 result；下游Agent进入0、最终答案0，因此缺必要任务输出，task_success=0/20。Gold delivery=0/23是另一个已知质量缺口，不能据此断言它导致了stage failure。

Unknown：16例在Provider/model response、JSON、Schema与stage validation之间的具体失败原因；4例零证据的Day11内部最早起因；缺失上游日志下的Gold首次丢失边界。没有证据支持按错误概率分摊这些原因。

**Q4：当前数据是否足以判断Vector有必要？**

**insufficient。** Legacy在D006/D007/D009/D010的零命中提供检索候选证据，但同时存在明确S2选择问题、S3事实条件缺失、S4–S5接线缺口和Multi-Agent S6–S7失败；没有Vector对照或已证明的增益。不能从零摘录、0/23或0/20直接跳到Vector必要，也不能反向宣布Vector无价值。本轮不实施技术方案、不形成最终Retrieval ADR。

## 11. 完成核验与Day13输入

| 完成条件 | 核验结果 |
| --- | --- |
| 20个paired cases | 20个唯一ID、40条路径记录，全部包含要求字段；逐例raw locator可打开 |
| known / unknown分开 | S6–S7的16例保留unknown；4个零调用有明确observer证据；selected缺失不补写 |
| task结果不解释成topology胜负 | 2/20与0/20仅作冻结样本描述，列明不同失败结构和因果限制 |
| Evidence独立比较 | 0与16个含证据request分开报告；744行序列核对；完整Gold仍0/23 |
| Token limitations | Legacy16/20 complete、Multi-Agent4/20 confirmed-zero complete；full cost not_comparable |
| Day13输入 | A–J候选、affected IDs、证据与confidence已形成；未开展Day13归因/实现 |
| 历史边界 | 没有重跑Day10/Day11，没有修改产品、Prompt、冻结数据或evaluator；没有读取Holdout题面/Gold/output或运行Holdout |

离线复核只读取本地既有Dev artifacts；生成程序保存在gitignored的`data/day12/analyze.py`，可用`.venv\Scripts\python.exe -X utf8 data/day12/analyze.py`重建配对表，不导入产品或调用Provider。机器检查确认全部聚合、20组/40条必需字段、5个诊断案例、A–J的10项输入及289个Markdown链接。报告与机器表的绝对仓库前缀已在本页记录，raw依赖仍留在原本地checkout。

按仓库要求运行现有回归质量门：`uv run pytest -v` 为 **812 passed、3 skipped、3 warnings**（日志`data/day12/pytest-full.log`）；`uv run ruff check .`通过，`uv run ruff format --check .`为216 files already formatted，`git diff --check`通过。现有测试使用自己的fixture，不是正式Dev/Provider重跑；实际Holdout数据未作为测试输入。本轮没有添加产品测试或依赖。

交付文件仅包括本报告、配对Markdown/JSON、DAY13_INPUT和CURRENT进度记录；启动时已有的两份Word与day-11.md保持原状。完整候选清单位于 [DAY13_INPUT.md](../study/evidence/DAY13_INPUT.md)，按A–J记录affected case IDs、证据和confirmed/bounded/hypothesis；它是Day13输入，不是已完成taxonomy，也不启动Day13。
