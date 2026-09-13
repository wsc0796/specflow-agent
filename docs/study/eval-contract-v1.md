# Eval Contract v1

- contract_id：`SF-EVAL-v1`；version：`v1`；日期：2026-09-13。
- status：`FROZEN-v1 / AI-prepared / learner-reviewed-boundaries`；实现 unknown 不冒充已交付。
- 实现基线：`5f2815d`；当前学习决定来源：[Day 8 证据卡](evidence/day-08.md)。
- 配套：[Evaluator Contract](evaluator-contract-v1.md)、[执行卡](day-08-execution-card.md)、
  [源码 Evidence Pack](evidence/day-08-source-pack.md)。本文是文档协议，不是现有 API/schema。

## 1. 目的、决定来源与非目标

本合同约定“评测对象是什么、数字如何产生、哪些结论允许比较”，服务于 Week 2 Measure。
学习者负责关键证据边界与取舍，AI 负责字段、公式、源码映射和格式；两者来源分开记录。

| 来源 | 纳入的决定 |
| --- | --- |
| R1/R1b 及反馈 | run_success_rate 只能表示指定 contract 的通过比例 |
| R2b | Gold 用事实级证据，定位绑定 repository revision；文件命中不等于事实命中 |
| R2c/R2d | answerability 属于 Evaluator-side metadata，不进入执行模型输入 |
| R3b–R3d、D1 | 成本覆盖 all attempted runs；0/unknown 分离；缺失维度 not_comparable |
| R3e | 缺少 Gold、scorer 与 Dev 校准的 Recall T0 只能是 hypothesis |
| D2/D2b | 路径有效与语义支持分离；复合状态使用 fail/unknown/pass 三值规则 |
| D3 | product terminal state 与 behavior verdict 分离；合法失败运行可使 Behavior Case pass |
| D4 | 同源题使用 isolation_group；当前 10 条采用 frozen_internal_holdout 证据等级 |

Day 8 仅产出合同、模板、数据纪律与教学材料，不创建正式 30 条题面或 Gold。
不查看/运行/调参 Holdout，不修改产品检索或评测实现，不安装依赖，不调用 Provider。
不运行 Day 9 baseline/离线实验，不进入 Day 10–14 或 Day 15 实施。
不以 Mock/Fake、结构校验或未校准 Rubric 宣称语义质量或生产收益。

## 2. 评价单位与集合

| 单位 | 定义 | 不可混同 |
| --- | --- | --- |
| case | 固定版本的任务及 Evaluator-side 标注 | case 与一次运行 |
| attempted run | 已开始执行该 case 的一次顶层尝试，含失败、降级、中止和确认零调用 | planned-but-not-started |
| provider call | run 内的一次实际 Provider 请求，含 retry/revision 的调用 | 顶层 run；一个请求不得重复累计 |
| gold fact | 在固定 revision 可核对的一条任务相关事实及必要条件 | 路径、文件数或孤立关键词 |
| evidence item | 实际进入指定观察面的摘录，带来源定位 | selected_files 与最终 Context |
| citation claim | 输出中的一条可核查主张及其引用 | 引用路径存在与引用支持该主张 |
| behavior case | 一条具体运行路径上的行为约束 | Repository Retrieval 调参任务 |

主观察面暂定为最终送入被测组件的 Context，并记录 component/receiver 身份；这是 AI 草案。
Collector 的 matched_files、selected_files、excerpts、serialized_context 分面报告。
`src/specflow/evidence/collector.py:89` 选文件，`:109` 构造 excerpt；
`src/specflow/evidence/models.py:117` 序列化 Context，不能用任一文件数量代替事实覆盖。
planned_count、attempted_count、not_started_count 分开；未执行的任务不悄悄从计划中删除。

## 3. 数据身份与输入隔离

每份评测清单记录 suite、split、dataset_version、case_id、repository_revision、
annotation_version、author/reviewer、isolation_group 和 evaluator_id/version。
Gold 每项记录 fact_id、fact_statement、必要前提、相对路径、symbol/行号、revision；
symbol 或路径变化后需要版本化复核，不让旧 Gold 自动指向新事实。

| 输入面 | 允许字段 | 禁止流入 |
| --- | --- | --- |
| 被测产品/模型 | requirement、授权仓库、正常运行配置 | answerability、Gold、期望分数、人工答案备注 |
| Evaluator | 运行证据、固定 Gold、answerability、判定协议 | 未经记录的参考答案修订 |
| 开发侧数据 manifest | ID、数量、版本、证据等级、冻结状态、访问记录 | 调参期使用 Holdout 题面、Gold、逐题输出或人工备注 |

answerability 枚举草案：answerable / unanswerable / safety_reject。
answerable 且 Gold 为空表示标注不完整，相关语义指标为 unknown；
unanswerable/safety_reject 的空 Gold 不计算 Recall，转给对应行为/拒答评价。
隔离原则已确定；实际字段投影/封装实现为 unknown，本日不实现。
旧 `EvaluationCase` 在 `src/specflow/evaluation/models.py:29`，加载入口在
`src/specflow/evaluation/runner.py:20`；新字段协议不承诺兼容旧加载器。

## 4. 运行身份与来源

每次记录 run_id、attempt_id、case_id/version、suite/split、repository_revision、
code_revision、Legacy/Multi-Agent、mock/live、Provider/model 与版本或不可变标识、
prompt/config/policy 版本、有效 limits、温度/seed（适用时）、开始/结束时间、运行环境。
检索策略、索引/embedding/chunking 版本未启用时写 N/A；无法证明的值写 unknown。
观察来源须区分 Provider reported、local measurement、estimated、mock；估算不冒充真实计量。
测试 fixture 的 manifest 字段不能单独证明发生过 live 调用。
Live artifact import 是既有产物验证，入口 `src/specflow/evaluation/runner.py:107`；
本日不导入或执行新运行。

## 5. 指标合同

下表中“目标协议”是 AI 起草；是否已有实现单独列明，不因定义了指标就视为已运行。

| 指标 | 目标单位/计算 | 方向及缺失处理 | 现状 |
| --- | --- | --- | --- |
| contract_run_success / run_success_rate | 指定 profile 的 passed runs / attempted runs | 越高越好；零尝试为 N/A | portfolio benchmark 有判定；通用 profile 尚未实现 |
| source_reference_validity | 一次 sources 输入的路径合法性，保留逐项 finding | 不直接转语义分；运行所需来源缺失可判 fail | 现有确定性 helper |
| fact_evidence_coverage | 命中且条件完整的 Gold fact 数 / 适用 Gold fact 数 | 越高越好；标注/映射缺失为 unknown | Gold/scorer unknown |
| citation_support | 有完整支持关系的 claim 数 / 需要支持的 claim 数 | 越高越好；无待核查 claim 为 N/A | scorer unknown |
| task_success | 每 case 对 requirement/expected_properties 的完成判断 | pass/fail/unknown；不复用 Schema pass | 人工 Rubric 存在，统一判定 unknown |
| safe_abstention | 适用 case 的明确拒答/安全终止及非虚构输出判断 | pass/fail/unknown；不适用为 N/A | 无 Evidence 工程分支存在，语义 evaluator unknown |
| token_cost | 所有 attempted runs 的 input/output/total tokens | 同质量条件下越低越好；不完整不可排名 | 当前 passed-only 聚合不满足协议 |
| latency | all attempted runs 的可观测 wall time，按终态分组 | 记录全体与分组统计；中止计时/缺失分开 | 当前聚合只纳入 passed |
| stability | 终态分布、失败分类、retry/revision/LLM call 数 | 原始计数及来源优先；缺失不写 0 | 已有部分字段，完整调用覆盖 unknown |

质量指标暂不压成一个加权总分。Rubric 分项保持 0/1/2、锚点版本、评分来源和理由，
见 `src/specflow/evaluation/models.py:73` 与 `src/specflow/evaluation/rubric.py:15`。
事实覆盖先保存 per-case numerator/denominator；AI 草案同时报告 macro 均值与 micro 总量比，
标明两种加权口径。unknown 不静默删除：单列 eligible/scored/unknown/N/A 数及 coverage。
若 run 完整结束且明确未提供所需事实，可按规则记 0；若产物无法取得则不能猜成 0。
“conditional quality on scored cases”可展示，但覆盖不完整时不冒充全套质量结论。

## 6. Token 成本与遥测完整性

population 固定为 all attempted case runs；passed、failed、degraded、中止均保留。
同一 run 内所有实际 Provider 请求计一次，包含 retry/revision；顶层人工重跑另有 attempt_id。
确认执行在 Provider 之前停止、并有调用证据支持时，成本可记 observed 0。
Provider 已可能被调用但 usage 丢失时，成本为 unknown；字段默认 0 不是零消耗证据。

```yaml
metric_id: token_cost
version: v1
unit: tokens
population: all_attempted_case_runs
observed_subtotal: <仅已证明的 input/output/total，不冒充完整总量>
complete_run_count: <覆盖该 run 全部调用或确认零调用>
attempted_run_count: <来自独立尝试清单>
telemetry_coverage: complete_run_count / attempted_run_count
unknown_run_count: attempted_run_count - complete_run_count
full_total: <coverage=1 且来源可核对时才给数值，否则 unknown>
comparison_status: <comparable | not_comparable | N/A>
```

分母为 0 时 coverage=N/A，不写 100%；调用清单本身不完整时 coverage=unknown。
可补充 call-level coverage，但 run-level coverage=100% 必须意味着每个 run 的全部请求可核对。
比较侧任一成本不完整，token_cost=not_comparable；只展示 observed subtotal、unknown 数与 findings。
不因成本缺证据把产品 task 改判 failed；其他已具备证据的维度继续报告。
现状：`src/specflow/evaluation/benchmark.py:219` 只选 passed；`:238`–`:239` 累计 Token；
`:258`–`:259` 将缺失/非法值回退为 0。`src/specflow/evaluation/metrics.py:51` 默认也是 0。
完整 usage ledger、缺失标记、coverage evaluator 和新聚合的实现状态均为 unknown。

## 7. 结果语义与失败归因

| 情况 | 产品事实 | 评测结论 |
| --- | --- | --- |
| 有证据证明产品违反明确属性 | 保留真实终态 | 对应 evaluator fail |
| 必需 artifact 确认未生成 | contract 未满足 | contract evaluator fail；不自动推断内容质量 |
| 评测拷贝/读取失败，原始运行证据不可得 | 终态 unknown 或保留已知记录 | evaluator incomplete/unknown |
| usage 缺失或未知来源的默认 0 | 不改产品终态 | 成本 unknown；成本比较 not_comparable |
| Gold/revision 不一致或 scorer 不可用 | 不改产品输出 | 对应语义 evaluator incomplete/unknown |
| 属性不适用 | 保留运行记录 | N/A，报告理由与数量 |

每条结果同时保存 product_terminal_state、evaluator_status、verdict/value、finding_code、
evidence_locator、evaluator_version；not_comparable 属于比较层，不混入产品状态机。
当前模型尚无完整四态/可比性协议；`src/specflow/evaluation/models.py:16` 的旧状态原样保留。

## 8. A/B 公平性与可比性

配对固定 case 集、数据/Gold 版本、repository revision、Evaluator 版本、有效 limits、
Provider/model、计量口径和环境；mock/live 分开，不混用不同 suite 的总分。
每次声明唯一实验因子及其必然派生差异。例如 Legacy/Multi-Agent 拓扑比较可以改变角色
prompt 与调用数，但需记录这些派生差异；不能再暗改模型、Gold、限额或评分阈值。
同拓扑的检索策略比较则固定角色 prompt。差异不能解释时，该维度 not_comparable。
AI 草案：先冻结执行顺序/重复次数；报告失败和未开始任务，禁止只挑一侧成功案例配对。
成本比较另要求双方 telemetry coverage=100%，输入/输出计数语义一致；质量与成本分别裁决。
相同 Token 总量不等于相同价格；本合同不计算货币费用，也不把不同模型 Token 排为省钱结论。
现有 `src/specflow/evaluation/multi_agent_runner.py:56` 同输入跑两条 Mock 路径，
`:68`–`:84` 只给 artifact 分且 requirement_coverage 为 0；`:43` 仅汇总传入 dimensions。
该实现没有自动落实本节公平性协议；不能据其分数宣布真实需求质量提升。

## 9. T0 与阈值纪律

| metric | initial_value | status | 当前理由/版本 | 后续证据要求 |
| --- | --- | --- | --- | --- |
| fact_evidence_coverage / Recall | unknown（尚未选择数值） | hypothesis | Gold/scorer/Provider/index 版本 unknown | 对应 Dev 校准和错误分析 |
| citation_support / task_success | unknown | hypothesis | 评分锚点与校准 unknown | 先验证 evaluator 正反例和盲区 |
| token telemetry coverage | 1.0，为完整成本比较的必要条件 | contract invariant / learner-confirmed | R3d、D1；实现 unknown | 证明 all-attempted 与调用完整性 |

未选数值的 T0 如实留 unknown；AI 不代选一个看似科学的通过线。质量阈值不是 validated gate。
Day 9 实现独立 calibration fixtures；Days 15–20 仅在 Dev 上校准适用策略阈值，Day 21 前冻结。
记录阈值理由、dataset/Provider/model/index/strategy/scorer 版本；变更任一项须标注可迁移性未知。
不为达到 T0 修改 Holdout、移除失败题或回看其答案。

## 10. 数据隔离与阶段边界

20 Dev + 10 Holdout 仅按 [执行卡](day-08-execution-card.md) 预留 ID；今天不写正式内容。
现有 12 条 portfolio benchmark、历史 evaluation、10 条 Behavior、教材合成练习各属独立 suite。
同源题、问题改写、相同 Gold 或派生材料用 isolation_group 管理，不跨 Dev/Holdout。
教材合成数据及变体不得进入正式 Dev/Holdout；教材只是概念配套。

### 10.1 Holdout Evidence Level（FROZEN）

```yaml
holdout_evidence_level: frozen_internal_holdout
case_count: 10
used_for_tuning: false
execution_policy: run_once_after_freeze
independent_creator: false
independent_access_control: false
```

该等级准确表示：用例由当前项目流程创建，数据来源不独立；它们在调参前预注册、
冻结，并且不用于修改系统。它保留检查 Dev 过拟合的内部价值，但不是严格盲测。
不采用 Primary/Reserve、复杂加密或伪独立保管流程；这些机制不能改变数据来源事实。

允许声称：

> 在 10 条预注册、未参与调参的内部冻结用例上，按冻结配置完成一次性验证。

禁止声称：严格盲测、独立数据泛化、统计显著性、生产流量效果，或对未知仓库具有
普遍泛化能力。

### 10.2 执行纪律与污染语义

1. Day 9 固定 Case ID、内容、Gold、dataset/annotation version 和 isolation_group；
   同源问题整体进入一个 split，并记录创建/访问事件及用途。
2. Days 10–20 不使用这 10 条题或其逐题结果修改 Prompt、策略、阈值或 Evaluator。
3. Day 20 冻结 code、model、Prompt、Policy、Evaluator、阈值和运行配置。
4. Day 21 按冻结配置运行一次并保存原始结果；结果差也不回调参数，后续改进进入
   新实验版本。
5. 若内容或逐题结果被用于开发/调参，等级变为 `contaminated_internal_check`；
   替换题目只能建立新的 dataset version，不能恢复原版本的证据等级。

只有未来同时存在独立数据来源、独立保管者和真实访问隔离，才可另行定义并使用
`blind_independent_holdout`。本合同不预先声称该升级会发生。

Day 8 第 19 章定向阅读 30–45 分钟；Day 9 离线实验用于 Recall/Precision/RR/RRF 理解。
Milvus、Vector、Hybrid、Rerank、23-specflow-repository-rag 最早 Day 15，且须由 Day 14 ADR 触发。

## 11. Review 与文档核验

关键证据边界已由学习者 Review；来源定位、表格/YAML 与 fixture 属性由 AI 整理，
不冒充学习者独立设计。未决实现包括 Gold/scorer、语义 Citation、完整 Token
ledger/coverage 和通用比较协议；这些 unknown 在 v1 中显式保留。
本次只核验文档结构、引用/链接、空白差异；不运行测试、Provider、baseline 或教材实验。
