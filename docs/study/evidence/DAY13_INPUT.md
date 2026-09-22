# Day13 Input — Observed Failure Candidates

- 来源：2026-09-22 Day12，仅消费冻结 Day10/Day11 的20组 Dev；Day13 **READY，尚未启动**。
- 主报告：[Day12 A/B Trade-off](../../reports/day-12-ab-tradeoff-report.md)。
- 逐例证据：[Case Pair Table / raw索引](day-12-case-pairs.md)、[完整机器记录](day-12-case-pairs.json)。
- 本文件是候选输入，不是完整taxonomy、根因裁决、修复方案或Retrieval ADR。
- `confirmed`：记录直接证明所述现象；`bounded`：范围/缺口有依据但不能唯一归因；`hypothesis`：仍是待证的解释。现象confirmed不表示其为task failure的因果根因。
- Dxxx均为完整ID `SF-RT-Dxxx` 的缩写；每项保留路径归属，不能把Legacy观察复制给Multi-Agent。

## A. retrieval-match

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Legacy D006、D007、D009、D010 | 各自sources.json明确matched_files=[]、selected_files=[]、excerpts=[]；冻结Dev有6个适用Gold facts。确认本次零命中，不代表仓库没有答案 | confirmed |
| Legacy D011、D012、D013 | Gold locator层面：D011缺runner_multi.py；D012缺runner_multi.py和handoff/validator.py；D013缺evidence/models.py。参见机器表gold_locator_observations | bounded：未命中指定locator；不能仅按路径断言所有等价事实也未召回 |
| Multi-Agent D006、D007、D009、D010 | EVIDENCE_NOT_FOUND、selected_file_count=0、referenced_file_count=0、完整observer零调用；未保存matched字段/搜索过程 | bounded：S1–S3起因unknown；“具体为retrieval-match”仍是hypothesis |

当前证据不足以选择Vector；缺少技术对照与收益证据。

## B. ranking-selection

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Legacy D001、D004、D005、D008、D011、D013、D014 | sources.json中Gold locator存在于matched_files但不在selected_files；D011/D013/D014为部分locator未选。D001的collector.py是最清楚实例 | confirmed：locator级选择丢失；不是完整fact recall评分 |
| Legacy D018、D019、D020 | repository_policy.py在matched但未selected；这些是safety_reject用例，相关源码支持缺口不计入23 facts的answerable coverage | confirmed：locator级现象 |
| Multi-Agent D001、D004、D005、D008、D011、D013、D014 | 请求中未完整交付所需Gold；同一通用摘录序列与Legacy相等，但没有原始matched/selected名单 | hypothesis：不能因内容相等而补写Day11的ranking trace |

## C. read/extraction

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Legacy D002、D003 | Gold文件被selected；sources.excerpts未保留完整必要条件。D002仅可见默认5等行，缺bool/正值拒绝条件；D003缺同模型幂等/frozen必要分支 | confirmed：S3保存摘录的事实条件不完整；不是已证明read_file失败 |
| Legacy D014 | selected的evidence/models.py和runner_multi.py有局部片段，未选的agents/adapter.py也参与必要事实；不能唯一归为提取或排序 | bounded：S2–S3 |
| Multi-Agent D002、D003、D014 | Analyst请求出现5个fact-level路径候选，但完整支持均0；没有独立read/extraction artifact | bounded：请求端事实不完整；具体S3丢失原因unknown |

禁止仅因truncated=true就归因“总字符预算裁剪”：Legacy12例标truncated，但搜索/文件截断等也可设置该字段；需逐条warning与内容对应，当前未作因果判定。

## D. context delivery

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Legacy D001、D002、D003、D004、D005、D008、D011、D012、D013、D014、D015、D016、D017、D018、D019、D020 | sources共80个case-file selections、744条excerpts；对应48个Worker请求均无Repository Evidence。main_failure_boundary=S4–S5 context delivery/request packing gap | confirmed |
| Multi-Agent 同上16例 | Analyst请求有744行同源同序摘录；对应Legacy sources逐项相等。这是正向交付证据，不应列为“通用Evidence完全未入request”的失败 | confirmed：此特定交付现象已改善；Gold delivery仍0/23 |

Legacy静态接线证据：runner把evidence_text放入WorkerContext.project_context，而Worker ContextBuilder使用构造时的ProjectContext；raw请求证明实际缺失。D015/D016虽然task pass，也保留交付缺口，不能只列失败样本。

## E. provider/model

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Legacy D001、D008、D013、D019 | Worker trace记录LLMResponseError，各有1次usage缺失；请求边界已出现 | bounded：客户端响应边界错误已记录；具体网络/Provider响应结构/模型原因unknown |
| Multi-Agent D001、D002、D003、D004、D005、D008、D011、D012、D013、D014、D015、D016、D017、D018、D019、D020 | 6次enrichment+1次Analyst请求，MULTI_AGENT_RUN_FAILED；缺response/error/stderr | hypothesis：Provider/model是S6–S7联合范围内的候选，不可单列confirmed根因 |

112条request observation不能视作112个已完成或计费Provider calls。Legacy56条有usage可作completion下界，其余unknown。

## F. schema/stage validation

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Multi-Agent D001、D002、D003、D004、D005、D008、D011、D012、D013、D014、D015、D016、D017、D018、D019、D020 | manifest.stages_completed=0；agent-outputs={}；workflow analyzing→failed；Analyst请求存在 | bounded：**S6–S7 unknown**；JSON/Schema/stage validation分别仍是hypothesis |
| Legacy D012 | Analyze trace ValueError、rule_baseline，且已有response usage；最终有degraded AnalyzeOutput与generation | bounded：本地输出处理/验证候选，不能仅从异常类判某个schema字段失败 |

Legacy全60条Worker trace均degraded，19条rule_baseline；degraded/fallback本身不等于60次Schema fail，也不等于Provider无response。

## G. workflow propagation

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Multi-Agent D001、D002、D003、D004、D005、D008、D011、D012、D013、D014、D015、D016、D017、D018、D019、D020 | Stage0未完成；下游Design/Test/Risk/Synthesis/Review请求均0，workflow未进入后续状态 | confirmed：阻断结果；没有已证实的S8传播bug |
| Multi-Agent D006、D007、D009、D010 | Evidence前置门停止；完整observer确认0调用 | confirmed：前置fail-closed；不是下游Agent执行失败 |

独立的“handoff/传播导致本次失败”affected IDs目前为空；不能为了taxonomy覆盖率制造一类根因。

## H. generation

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Legacy D001、D002、D003、D004、D005、D006、D007、D008、D009、D010、D011、D012、D013、D014、D017、D018、D019、D020 | generation存在，但冻结semantic review逐例缺必要expected properties；D017仅条件式方案，无本次明确结论 | confirmed：最终输出属性未满足；模型自身推理根因unknown，不能排除更早S1–S5影响 |
| Multi-Agent D001至D020（全部20例） | 4例LLM前停止；16例Stage0未形成；没有最终generation | confirmed：最终输出不可用这一结果；没有可评分的最终生成语义，不构成已证明S9生成器bug |

## I. validator/evaluator

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Legacy D017 | raw finding=secret_detected；sources包含函数名_bearer_token而非凭证值；历史semantic review明确false positive | confirmed：S10 artifact validator误报；task fail仍独立成立 |
| Legacy D015 | expected要求指定revision的报告不存在；generation以当前上下文未包含报告为理由明确unknown，历史AI仍判pass | bounded：属性严格度/评分证据分歧；Day12保留冻结2/20，不重新调分 |
| 两侧D001至D020 | raw report的task unknown占位与后续semantic review不同；Mock portfolio contract profile对Live Dataset v1不适用 | confirmed：评分来源/合同适用性差异；不是20个新产品错误 |

Citation support没有冻结claim↔citation scorer，保持unknown；source_reference_validity不是替代指标。Safe abstention的product_state_mapping未知；Multi-Agent无最终答案，不能自动safe pass。

## J. measurement gap

| affected case IDs | supporting evidence | confidence |
| --- | --- | --- |
| Multi-Agent D001、D002、D003、D004、D005、D008、D011、D012、D013、D014、D015、D016、D017、D018、D019、D020 | 无sources.json、response/error/stderr/usage；仅有request、失败manifest与有限traces | confirmed：限制上游归因和S6–S7拆分 |
| Multi-Agent D006、D007、D009、D010 | 有selected=0、零调用等完整前置停止证据；没有原始matched/read过程 | confirmed：起因观察不足；不能把确认零调用改成unknown调用，也不能补写matched=0 |
| Legacy D001、D008、D013、D019 | 每例1次usage缺失；run completeness=16/20 | confirmed：完整成本unknown |
| Multi-Agent全部20例 | metrics-only聚合有request_count=0，而observer=112；只有4个零调用run成本完整 | confirmed：metrics与request-observer口径不同；full cost not_comparable |
| Multi-Agent D002、D003、D014 | 5个fact-level path candidates分布于3个实际request；历史文字写“5个request” | confirmed：汇总文字单位问题；完整Gold仍0 |
| 两侧全部20例 | 历史P50算法不一致；Day12统一median，逐例wall time完整 | confirmed：历史口径问题已在分析层显式对齐，无需重跑 |
| 两侧全部20例 | 不同运行日期、immutable model version unknown、每侧仅1次、AI评分未独立验证 | confirmed：因果和外推限制；不能改造成topology因果实验 |

Day13应消费这些证据边界；S6–S7没有新增历史证据时继续unknown。是否新增观测、实验或Patch，须在后续任务范围中另行决定。本文件不授权重跑Day10/Day11、不读取或运行Holdout、不启动技术实现。
