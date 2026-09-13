# 第 08 天证据卡

- 日期：2026-09-13；阶段：Measure；模式：TUTOR。
- 状态：已收束；Eval/Evaluator Contract v1 与 frozen_internal_holdout 已冻结。
- 规划提交：`5f2815d`；执行卡：`../day-08-execution-card.md`。
- 后台源码准备由 AI 完成，不计为学习者已掌握。

## R1 — run_success_rate 的证明范围

题目：现有 benchmark 的 run_success_rate=1.0，能否代表真实需求完成率 100%？

学习者原答：

> 可以，status = "passed" if manifest.get("workflow_state") == "completed" and schema_ok else "failed"

【正确答案】不能。该路径以 artifact 文件检查、manifest workflow_state 和 Schema
计数作为通过条件，没有据此证明输出内容满足 requirement。run_success_rate 是这些
判定下的通过比例，不能直接解释为真实需求完成率。

源码证据：

- `src/specflow/evaluation/benchmark.py:164`：所需 artifact 文件存在/非符号链接检查，
  并读取 manifest 与 metrics。
- `src/specflow/evaluation/benchmark.py:188`：schema_unvalidated_count=0 且
  schema_validated_count=6；workflow_state=completed 时标记 passed。
- `src/specflow/evaluation/benchmark.py:208`、`:235`：计算 passed 数与总数的比例。
- `tests/test_benchmark.py:118`：检查报告 case_count=12、status=passed。

差异：定位判定行正确，但把程序的通过条件外推成了需求内容正确。
当前 readiness：`practicing`；AI 已解释，尚无学习者纠正后的独立证据。

## R1b — 内容偏题的口头反例

题面：文件检查已通过、workflow_state=completed、Schema 计数为 0/6，
但生成方案与原需求完全无关；预测该条结果的 passed/failed。

学习者原答：`passed`。

【正确答案】passed。条件仍满足，内容是否符合需求没有参与该判定。
本次判断正确，已完成提示后的同一判定条件变体；尚不据此宣称跨题面稳定掌握。
这只是口头反例，没有创建正式 Repository Task 或运行评测。

下一步 R2：展示 `src/specflow/evaluation/runner.py:51–53`，判断预期文件在磁盘
存在、但没有进入本次 Evidence 时，missing_files 能否发现这一遗漏。

## R2 — 磁盘存在与 Evidence 命中

题面：`expected_file_patterns` 中的文件在仓库磁盘上存在，但本次
EvidenceCollector 没有选中它；`missing_files` 能否发现漏选？

学习者原答：

> 不能，这个文件不在本地，那么无法找到其路径

【正确答案】不能发现，但文件“在本地不存在”的理由不符合题设。题设中该文件
存在，所以 `(repository_root / path).is_file()` 为 True，文件不会进入
`missing_files`。这段检查没有读取 `EvidenceBundle.selected_files` 或 `excerpts`，
无法发现“磁盘存在但证据漏选”。

源码证据：

- `src/specflow/evaluation/runner.py:51–53`：只消费 `expected_file_patterns`、
  `repository_root` 与 `Path.is_file()`。
- `src/specflow/evidence/collector.py:89–100`：另一路径生成 `selected_files` 并读取。
- `src/specflow/evidence/models.py:84–90`：`matched_files`、`selected_files`、
  `excerpts` 是 EvidenceBundle 的独立字段。

差异：结论正确，但混淆了“仓库没有这个文件”和“检索没有选中这个文件”。
当前 readiness：`practicing`，需用 gold evidence 新题面继续区分评价单位。

下一步 R2b：根据 EvaluationCase 与 EvidenceBundle 字段，判断 Evidence Coverage
的 gold 最少应只记录文件路径，还是还需记录待证明的事实及可重定位位置。

## R2b — Gold Evidence 的评价粒度

学习者原答：

> 后者，仅仅是记录文件路径，文件后续可能会出现移动的情况，那么这就可能导致误判为文件丢失

【正确答案】应记录待证明的事实及可重定位位置，并绑定 `repository_revision`。
学习者选择正确；文件移动确实会造成版本漂移，但更核心的理由是：即使路径完全
没变，命中文件也不证明所需事实、条件或跨文件关系已经进入 Evidence。

建议的 Gold 定位信息包括：固定仓库 revision、相对路径、符号/事实描述、必要的
行或片段定位，以及用于核对版本一致性的来源身份。行号可能漂移，hash 只能证明
内容一致，二者都不能单独证明语义正确。

源码证据：

- `src/specflow/evaluation/models.py:34–39`：现有 EvaluationCase 有预期文件等字段，
  没有可执行的事实级 Gold 字段。
- `src/specflow/evidence/models.py:16–22`：EvidenceExcerpt 保留 relative_path、
  line_number、excerpt 与 match_count。
- `src/specflow/evidence/models.py:84–90`：EvidenceBundle 分开保存 matched_files、
  selected_files、excerpts 与 source_hashes。

差异：判断正确；理由目前侧重文件移动，还需稳定区分“文件命中”和“事实命中”。
当前 readiness：`practicing / improving`。

下一步 R2c：现有 EvaluationCase 强制 expected_file_patterns 非空；对于无答案用例，
判断空 Gold 能否单独表示“正确答案就是无答案”，还是必须有显式 answerability 标签。

## R2c — 无答案标签与评测泄露

学习者原答：

> 必须另设显式的 `answerability` 标签。大模型需要标签，才能识别数据类型。

【正确答案】必须另设显式 answerability 标签。它首先供数据集与 Evaluator 区分
`unanswerable`、标注缺失和 `safety_reject`；空 Gold 本身无法区分这些语义。

差异：选择正确，但“给大模型识别”的理由不准确。执行任务的模型通常不应看到
Gold 侧 answerability；否则 `unanswerable` 会泄露参考结论。现有 runner 加载全部
Case 字段，但调用产品路径时只传 `case.requirement`，这展示了输入与评测元数据
应当分离的边界。

源码证据：

- `src/specflow/evaluation/runner.py:20–37`：加载 requirement 和各 expected 字段。
- `src/specflow/evaluation/runner.py:57–63`：运行产品路径时只把 requirement 作为
  任务内容传入，没有把 expected 字段传给模型执行路径。
- `src/specflow/evaluation/models.py:47–56`：现有模型强制 expected 集合非空，不能
  用空集合可靠表达规划中的无答案类型。

当前 readiness：`practicing / improving`。已识别显式类型的必要性，仍需稳定掌握
Gold 评测元数据与模型输入隔离。

下一步 R2d：判断 answerability 标签应否进入执行任务的大模型输入，并解释这样做
对 Dev/Holdout 评测有效性的影响。

## R2d — Gold 元数据与模型输入隔离

学习者原答：

> 不应该，防止大模型因为标签而出现一下非客观的描述

【正确答案】不应把 answerability 传给执行任务的模型。该标签属于 Gold/Evaluator
一侧；暴露 `unanswerable` 会让模型无需根据仓库证据就选择拒答，暴露
`answerable` 也会诱导模型强行作答，形成标签泄露。

差异：判断正确；“描述不客观”仍偏模糊。主要影响是模型不再独立完成题目，导致
safe abstention、Task success 等指标失去测量效度，即使最终措辞看起来客观也一样。
当前 readiness：`improving`；已能识别显式标签并进一步说明输入隔离。

本轮冻结的模板原则：answerability 是 Evaluator-side metadata；产品执行只接收
正常 requirement 与允许的仓库上下文，报告可在执行完成后用标签评分。

下一步 R3：现有 benchmark 的成本和 latency 只聚合 passed runs。判断能否直接用
报告中的 total tokens 比较含失败运行的两种方案成本。

## R3 — 失败运行与成本统计范围

学习者原答：

> 不能，成本低。不代表效果好

【正确答案】不能。学习者正确指出成本不能代替效果，但本题还存在更早的统计问题：
`metric_runs` 只包含 passed runs，失败运行在失败前消耗的 Token 和 latency 被排除，
因此报告甚至不足以证明 B 的实际总成本更低。

源码证据：

- `src/specflow/evaluation/benchmark.py:219–221`：成本和 latency 的集合先筛为 passed。
- `src/specflow/evaluation/benchmark.py:238–243`：Token 总数与 latency 只聚合该集合。
- `src/specflow/evaluation/benchmark.py:229–231`：失败数另有计数，但没有补回其成本。

差异：结论正确；理由抓住质量/成本不可互相替代，但未指出失败样本被排除导致
成本指标本身有选择偏差。当前 readiness：`practicing / improving`。

下一步 R3b：定义公平成本口径的纳入集合——所有 attempted runs，还是仅 passed
runs；先只判断集合，不处理缺失遥测。

## R3b — 成本指标的纳入集合

学习者原答：

> 前者，原因是其他的runs 也会消化token

【正确答案】总 Token 等资源成本应包含所有 attempted runs。失败、降级或中途终止
也可能在终止前完成 Provider 调用并产生费用；只纳入 passed runs 会奖励失败较多的
方案并造成选择偏差。

差异：判断与核心理由均正确。措辞中的“消化”按“消耗”理解。质量指标与成本指标
仍需分开报告；这里冻结的是资源成本的纳入集合。当前 readiness：`improving`。

下一步 R3c：当前 `_as_non_negative_int` 把缺失/非法 Token 遥测转成 0；判断已经
尝试并可能调用 Provider、但遥测缺失的运行应记 0，还是记 unknown/incomplete。

## R3c — 零值与缺失遥测

学习者原答：

> `unknown/incomplete`，`input_tokens` 遥测缺失，这段代码会把它记为 `0`

【正确答案】应标记 `unknown/incomplete`。0 是一个已观测数值，表示没有 Token
消耗；遥测缺失表示消耗量未知。二者合并会低估总成本并隐藏证据不完整。

源码证据：

- `src/specflow/evaluation/benchmark.py:200–202`：读取 Token/latency 时调用
  `_as_non_negative_int`。
- `src/specflow/evaluation/benchmark.py:258–259`：缺失、类型错误或负数统一转成 0。

差异：判断和源码解释均正确。当前实现事实仍是写入 0；Day 8 合同将其登记为
Evaluator 盲区和不完整证据，不在本日修改产品。当前 readiness：`improving`。

下一步 R3d：当 A 的 Token 遥测完整、B 有一条 unknown 时，判断 Eval 报告能否继续
给出“A/B 谁更省 Token”的排序结论，还是必须标记该成本比较不可裁决。

## R3d — 遥测不完整时的 A/B 可比性

学习者原答：

> 后者，两者的token消耗量不能比较

【正确答案】该成本维度必须标记为不可裁决。A 有完整总量，B 只有部分总量，二者
不是同一统计口径，不能继续排序谁更省 Token。

差异：判断与理由正确。报告仍可展示 B 的 observed subtotal、unknown run count
和 telemetry coverage，但必须阻止完整成本排名。当前 readiness：`improving`。

本轮冻结的成本合同：统计全部 attempted runs；0 与 unknown 分开；记录遥测覆盖率；
任何比较侧不完整时，该维度为 `not_comparable`，不输出胜负结论。

下一步 R3e：当前 RunMetrics 只有文件计数，没有 Recall scorer。判断 Day 8 写下的
数值 Recall T0 能否作为 validated gate，还是只能标记为 hypothesis。

## R3e — Recall T0 的证据等级

学习者原答：

> 后者，目前没有事实级 Gold Recall scorer，也没有 Dev 校准结果。

【正确答案】数值 T0 目前只能标记为 `hypothesis`，不能作为 validated gate。
判断与理由均正确：当前 RunMetrics 只记录 discovered/selected/referenced file count，
没有事实级 Recall；Day 9 Gold 和后续 Dev 校准证据也尚未产生。

源码证据：

- `src/specflow/evaluation/metrics.py:61–63`：只有文件数量字段，没有 Gold Recall。
- `src/specflow/evaluation/benchmark.py:228–245`：现有聚合指标没有事实级 Recall。

当前 readiness：`improving`。这证明学习者能给阈值标注证据等级，但尚未亲自
设计一个完整合同或比较方案，因此不提升为架构能力 verified。

## 教学方式校准

学习者反馈：连续判断题缺少工程与架构能力的获得感，并询问 Day 8 是否只是概念课。

校准结论：Day 8 的对象是评测架构与数据合同，本身属于工程设计；但此前的微型
判断主要用于诊断误区，不能单独构成 C3/C4 证据。后续停止连续二选一，改为每轮
由学习者亲自提交一个小型工程产物，AI 只做源码审查、反例攻击和格式整理。

调整后的剩余闭环：

1. D1：学习者闭卷整合 `token_cost` Metric Contract。
2. D2：学习者设计一个 Evaluator Contract，包含正例、反例、盲区和人工复核。
3. D3：学习者基于真实路径设计一个 Behavior Case 的四项断言。
4. D4：学习者解释 Dev/Holdout 泄露场景并冻结数据纪律和非目标。

AI 已完成的 30/10 模板与源码导航继续作为脚手架，不算学习者 ownership。
Day 9 才创建数据与 Evaluator fixtures；Day 10–12 运行并解释 A/B；Day 13 做失败
归因；Day 14 形成 ADR；Day 15 以后才按 ADR 进入有证据触发的实现分支。

学习者进一步指出 YAML、字段整理和模板可以由 AI 完成。该判断采纳：AI 在后台
起草正式 Eval/Evaluator Contract 文档，学习者不再手填机械字段。学习者只审查
会改变结论可信度的边界、盲区和取舍。若这些判断也完全交给 AI，文档仍可交付，
但只能记录为 AI-authored，不能作为学习者的 C3/C4 ownership。

下一步 D2 Review：AI 建议把确定性的 source path validity 与语义 citation support
拆成两个 Evaluator；学习者只需审查是否接受该边界并说明一个理由。

## D1 — 学习者设计 token_cost Metric Contract

学习者原始产物：

```yaml
metric: token_cost
population: passed、failed、degraded、中途终止但已经调用过 Provider 的运行
missing_data: 抛出失败
ab_comparability: A/B 完整的 token 消耗量完全透明清楚
```

【正确答案】合同应至少明确为：

```yaml
metric: token_cost
population: all attempted case runs；确认未调用 Provider 的运行保留观测值 0
missing_data: 该运行的成本为 unknown，记录 finding 和 telemetry coverage；不把产品任务改判失败，不强制转 0
ab_comparability: 同 Case 集、仓库 revision、Provider/model、限制与 Token 计数口径，且双方 telemetry coverage=100%；否则 not_comparable
```

审查结果：

- population 基本正确，已覆盖 passed/failed/degraded/中途终止；需用 all attempted
  收敛，避免遗漏确认零调用的尝试。
- missing_data 的“抛出失败”混淆产品执行失败和成本 Evaluator 证据缺失；其他质量
  结果仍可保留，只有成本维度不可裁决。
- A/B 方向正确，但“透明清楚”不可执行；必须列出可核对的相同变量和 100% 覆盖率。

学习证据：这是第一份学习者亲自提交的 Day 8 集成合同。当前为 `practicing`：已能
列举对象和提出可比性要求，但失败语义和可执行不变量仍需提示。

后续已按教学校准改为 AI 起草合同、学习者 Review 架构边界，见下节。

## D2 Review — 路径有效与语义支持的 Evaluator 边界

AI 建议：拆为 deterministic `source_reference_validity_v1` 与 semantic
`citation_support_v1` 两个 Evaluator。

学习者原答：

> 可以，结构安全和业务语义正确都保证了，所以我认为是可以这么拆分的

【正确答案】接受拆分；但拆分不保证两者都正确。当前实现只证明路径非越界、位于
仓库且文件存在。语义 Citation 是否支持生成事实仍为 `unknown / contract-only`。

拆分理由：二者输入、判定方法、证据等级和盲区不同；独立状态可以阻止确定性路径
检查通过被扩大成业务语义正确。

源码证据：

- `src/specflow/evaluation/validators.py:200–231`：只验证 sources 结构、候选非空、
  相对路径、仓库 containment 与文件存在。
- 当前 evaluation 包未找到事实级 Citation 支持判定实现，保持 unknown。

差异：拆分决策正确；“都保证了”属于过度声明。当前只能说第一个 Evaluator 有
现成实现证据，第二个仍需 Gold/校准与人工复核。当前 readiness：`practicing`。

下一步 D2b：Review 复合 evidence_validity 的三值聚合规则：path fail、path pass +
citation unknown、两者 pass 分别应输出什么状态。

## D2b Review — 复合 Evidence 状态

AI 提案：path fail → fail；path pass + citation unknown → unknown/incomplete；
path pass + citation fail → fail；两者 pass → pass。

学习者原答：`可以`。

【正确答案】接受。路径 invalid 是确定性失败；语义未验证不能冒充通过；语义明确
不支持时失败；只有两个独立合同都通过才允许 composite pass。

差异：无。该回答是对 AI 提案的 Review 接受，属于 learner-reviewed boundary，
但不是学习者独立从零设计。当前 readiness：`improving`。

下一步 D3 Review：审查 SF-AB-007 No Evidence 的双层状态——运行以
failed/EVIDENCE_NOT_FOUND 合法终止时，Behavior Case 自身应判 pass 还是 fail。

## D3 Review — No Evidence 的运行终态与评测状态

AI 草案：无 excerpts 时必须持久化 failed/EVIDENCE_NOT_FOUND、stages_completed=0、
返回 3；不得调用 Coordinator.plan 或 Agent。该 failed 是预声明的合法运行终态。

学习者首次回答：`failed`。

【正确答案】Behavior Case 应判 `pass`。产品运行的实际终态是 failed，但它完整
满足了 No Evidence Case 的 must_happen、must_not_happen 和 legal_terminal_state。

源码证据：

- `src/specflow/runner_multi.py:130–142`：零 excerpts 持久化分类失败并返回 3。
- `tests/test_cli_multi_agent.py:116–126`：测试期望 exit 3、Agent/Coordinator 未调用、
  workflow_state=failed、error=EVIDENCE_NOT_FOUND、stages_completed=0；断言满足时测试 pass。

差异：首次混淆 product_terminal_state 与 behavior_case_verdict。经解释后学习者再次
回答 `pass`，完成纠正。当前 readiness：`improving`，但需在新失败类型中重测。

冻结字段边界：`product_terminal_state=failed` 与 `behavior_verdict=pass` 分开保存；
否则无法验证 fail-closed、权限拒绝、超时终止等正确失败行为。

下一步 D4 Review：审查同源题/改写题能否跨 Dev/Holdout，以及这样做是否构成泄露。

## D4 Review — 同源改写与 Split 泄露

题面：Dev 与 Holdout 使用同一仓库、同一 Gold 事实和语义等价问题，仅改变措辞。

学习者原答：

> 不能，两题使用同一仓库代码、同一组 Gold 事实，只是换了说法。这属于自圆其说，没有说服力。

【正确答案】该 Holdout 无效。核心原因不是“同一仓库”，而是两题共享同一基础
问题与 Gold 事实，属于同源近重复。Dev 上已经暴露的解题线索可直接迁移到改写题，
Holdout 因而不能独立测量对未见问题的泛化能力。

标准表述：

> 该 Holdout 与 Dev 题语义等价并共享 Gold 事实，构成同源样本泄露。二者必须使用
> 同一 isolation_group 并整体分配到同一 split；Holdout 应换成未暴露的独立问题组。

差异：结论正确；“自圆其说、没有说服力”描述了观感，没有指出可执行的数据问题。
同一仓库本身允许，语义等价与 Gold 重叠才造成污染。当前 readiness：`improving`。

下一步 D4b：Review Holdout 意外暴露后的处置：是否仍可保留并声明未调参，还是
必须标记污染、取消其 Holdout 证据资格并使用未暴露的独立替代组。

## D4b Review — 重复泄露与替代流程

AI 初始提案：记录污染、取消样本资格、不利用泄露答案、换未暴露独立组。

学习者原答：

> 不接受，如果选择的新内容又暴露了怎么办

【正确答案】反对成立。替换样本不是充分控制；必须先定位并关闭泄露通道，再通过
独立保管流程准备替代组。替代组再次进入开发/调参参与者或被测模型视野时同样失效。

标准表述：

> Holdout 泄露后应停止流程、记录污染范围和泄露路径、取消受影响组的证据资格；
> 只有关闭并验证泄露路径后，才能由独立保管流程建立未暴露替代组。若原因未关闭
> 或替代组再次暴露，Holdout 标记为 UNSEALED/BLOCKED，不运行或声称盲测有效。

补充边界：独立标注者/保管者履职访问不是污染；暴露给开发/调参参与者或被测模型
才破坏盲测。实际保管者和密封验证目前仍是 unknown，Day 9 建数据前必须落实。

差异：学习者没有接受表面补救，并指出相同失败模式可重复发生。这是从单次样本处理
上升到泄露通道/流程控制的有效架构反例。当前 readiness：`improving`，是本日较强的
learner-owned C4 练习证据，但仍需 Review 修订后的闭环。

下一步 D4c：Review 修订后的 stop → locate → close/verify → independent replace →
manifest-only 流程，以及无法证明隔离时 UNSEALED/BLOCKED 的终态。

## D4c — Holdout Evidence Level 最终裁决

学习者拒绝继续为单人项目设计伪独立隔离，最终选择：

```yaml
holdout_evidence_level: frozen_internal_holdout
case_count: 10
used_for_tuning: false
execution_policy: run_once_after_freeze
independent_creator: false
independent_access_control: false
```

【正确答案】采用 `frozen_internal_holdout`。它准确表达同一项目流程创建数据、提前
冻结、不参与调参和冻结后运行一次的事实，同时不冒充独立盲测。

学习者明确给出：

- 允许声称：在 10 条预注册、未参与调参的内部冻结用例上，按冻结配置完成一次验证。
- 禁止声称：严格盲测、独立数据泛化、统计显著性、生产流量效果、未知仓库普遍泛化。
- Days 10–20 禁止使用内部冻结题调整系统；Day 20 冻结全部比较变量；Day 21 运行一次。
- 使用其内容开发/调参后降级为 `contaminated_internal_check`；换题只能创建新版本，
  不能恢复原证据等级。
- 不采用 Primary/Reserve；未来只有独立来源、独立保管者和真实访问隔离同时成立，
  才升级为 `blind_independent_holdout`。

差异：学习者先后识别了“替换不能关闭泄露通道”和“密封不等于数据独立”，最终
主动给出证据等级、可声称范围、污染语义、阶段纪律与升级条件。对于这个有界的
Holdout 证据等级决策，C4 证据标为 `verified`；不外推为整体架构能力已 verified。

下一步：完成第 19 章定向教学，将文件命中、事实摘录与最终 Context 分面观察，
再收束 Day 8。

## L19-1 — Retrieval 与 Context Assembly 的最早失败层

题面：search_code 已匹配目标事实，文件已进入 selected_files 并被读取；随后
max_total_evidence_chars 裁剪删除了该 excerpt，serialized_context 不再包含事实，
模型最终不可见。

学习者原答：

> 后者，文件已经被读取，仅仅是因为context的原因导致结果失败

【正确答案】最早失败层是 Context Assembly。Retrieval 已找到目标事实并形成候选，
错误第一次出现在字符预算裁剪；最终 Context 只序列化保留下来的 excerpts。

源码证据：

- `src/specflow/evidence/collector.py:89–118`：选择文件、读取并形成 EvidenceExcerpt。
- `src/specflow/evidence/collector.py:120–130`：按总字符预算裁剪 excerpts。
- `src/specflow/evidence/models.py:117–132`：只把当前 excerpts 序列化进 Context。
- `src/specflow/runner_multi.py:117`、`:193–197`：DLP 后的 evidence_text 进入 base_context。

差异：判断正确；理由中的“文件被读取”本身还不足以证明目标事实已召回。本题同时
给定目标事实已匹配并形成候选，才能把最早错误稳定归到 Context Assembly。
当前 readiness：`improving`。

下一步 L19 Teach-back：学习者用自然语言区分文件命中、事实进入 Evidence、事实进入
LLM Context、最终主张获得引用支持四个条件；AI 随后给标准答案并收束 Day 8。

## 最终闭卷复述（侧对话同步）

学习者随后在同一 Day 8 任务的侧对话中完成四项核心边界复述：

1. 结构通过只证明 JSON/Schema 等形式合同，不证明业务语义正确。
2. Gold/answerability 不能进入被测模型输入，否则模型可利用参考结论，形成标签泄露，
   无法测量原有 Retrieval 与推理过程。
3. 失败运行也进入资源成本集合，因为失败前仍可能消耗 Token、latency、LLM Calls
   和 Tool Calls。
4. `frozen_internal_holdout` 中：frozen 表示内容、Gold、版本在评测前按合同固定；
   internal 表示数据来源、认知和访问边界不独立；holdout 表示不用于 Prompt、策略、
   阈值和 Evaluator 调整，并在冻结配置后运行一次。

【正确答案】四项核心判断均正确。标准措辞补充：

- Internal Holdout 能提供有限的内部未调参/回归证据；不能写成“完全没有可靠性”。
- Frozen 是“按合同不允许覆盖修改；修改产生新 dataset version”，不是物理上无法修改。
- Internal 的耦合具体指数据来源、开发认知与访问控制不独立；不用于调参本身是正确纪律。
- `blind_independent_holdout` 还需要独立来源/保管者、真实访问隔离、事前未知和冻结后
  一次揭示；结果不得用于回调当前版本。

这组复述与 L19-1 共同证明学习者能区分：文件/Schema 结构证据、事实级 Gold、模型
可见 Context、语义 Citation，以及产品终态与 Evaluator verdict。无需重复填写 AI
已准备的四行模板。

Readiness：

- 指标与证据范围：`improving`；早期多次需纠正过度声明，最终能闭卷给出边界。
- 成本缺失/可比性：`improving`；能说明 all-attempted、0/unknown 与 not_comparable。
- Failure Attribution：`improving`；Context Assembly 新题判断正确，理由需提示补全。
- Holdout 证据等级：对本次有界架构决策为 `verified`；学习者比较了复杂隔离与内部
  冻结方案，给出约束、ROI、污染路径、版本语义和升级条件。
- 整体 Day 8 ownership：`improving / partial`。AI 编写合同、模板、正反例规格和
  源码 Evidence Pack；学习者完成关键语义 Review、反例挑战、证据等级裁决与闭卷复述。

## Day 8 正确答案总表

| 主题 | 冻结答案 |
| --- | --- |
| run_success_rate | 只表示指定结构/运行合同通过率，不等于真实需求成功率 |
| Gold | 事实级、保留必要条件与可重定位来源，并绑定 repository revision |
| answerability | Evaluator-side metadata；不进入被测模型 |
| Token 成本 | all attempted runs；0 与 unknown 分开；缺失时比较 not_comparable |
| Recall T0 | 无 Gold/scorer/Dev 校准时只能是 hypothesis/unknown |
| Source/Citation | 路径有效与语义支持分成独立 Evaluator；两者均 pass 才能 composite pass |
| Behavior | 合法失败运行可以让 Behavior Case pass；两个状态字段分开 |
| Holdout | 10 条 frozen_internal_holdout；一次运行、不调参、污染降级、不冒充独立盲测 |
| L19 归因 | 已召回事实但 Context 裁剪丢失时，最早失败层是 Context Assembly |

## Day 8 完成边界

- 已交付合同、模板、ID 规划、源码盘点、数据纪律、教材映射和学习证据。
- 未实现/校准项继续保持 unknown/contract-only；冻结合同不等于实现完成。
- 未创建正式 30 条内容、Evaluator fixtures 或 Holdout 题面；未运行 baseline/Provider。
- 不进入 Day 9、Day 10–15、Milvus、Vector、Hybrid、Rerank 或产品检索修改。
- 下一步必须由用户在独立任务中显式启动 Day 9。

## 合同与数据状态

- Eval Contract / Evaluator Contract：FROZEN-v1；AI 起草，学习者 Review 关键边界，
  contract-only/unknown 项不冒充实现或校准完成。
- 20 Dev + 10 frozen_internal_holdout / 10 Behavior：只有模板与 ID，无正式新数据。
- 不打开 Holdout；不提前进入 Day 9；不因本题回答变更产品实现。
