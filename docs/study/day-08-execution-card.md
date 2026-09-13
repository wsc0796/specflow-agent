# Day 8 执行卡 — Measure：定义怎样评测

- 日期：2026-09-13；唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 模式：`TUTOR`；用户明确授权本日规划更新后直接教学。
- 状态：DAY 8 COMPLETE；合同、模板、数据纪律和 Teach-back 已收束。

## 1. 启动证据与边界

- 分支：`codex/t072-no-evidence-fail-closed`。
- 启动 HEAD：`ee196078c1df18442f91956f420fb76ff323353e`。
- 最近提交：`ee19607 docs: close Day 7 ownership gate`；前一提交为
  `952a952 fix: wire repository file limits into runners`。
- 启动 `git status --short` 无输出，工作区干净。
- 已读 AGENTS、SPEC-BASELINE、V5.3.2 ROADMAP、CURRENT、Day 7 证据卡、
  Control Coverage Backlog、evaluation/benchmark 源码、相关测试和 12 条现有案例。
- Day 7 保持 `WEEK 1 OWNERSHIP GATE (IMPROVING)`；T-074 已完成，不重做。
- Day 7 历史测试为 `777 passed, 3 skipped, 3 known warnings`；根 AGENTS 的
  `773 passing tests` 是较早的 T-072 记录，不冒充本日测试结果。

本日只做合同、模板、ID、数据纪律、源码盘点和教学。行政记录可更新；不修改产品
检索、评测实现、测试、Prompt、参数或现有数据；不安装 Milvus、向量库或新依赖。
不创建正式 30 条任务内容，不打开/执行/调参 Holdout，不运行新的 Dev baseline，
不进入 Day 9、Day 10–14 或 Day 15 工作。Backlog 不在本日修复范围。

AI 负责检索、Evidence Pack 和格式；学习者负责指标含义、正反样本判断、Evaluator
盲区与数据纪律。每轮只问一个主要判断，同时展示对应源码与路径/行号。
学习者回答后，无论对错，都明确给出 **【正确答案】** 并解释差异。
AI 产物不计为学习者已掌握，缺少实现证据写 `unknown`。

## 2. Evidence Pack：现有能力盘点

以下是源码/测试阅读证据，测试存在不等于今天已执行。
表中源码简写相对 `src/specflow/`。

| 对象 | 已确认事实与证据 | 本日接续 |
| --- | --- | --- |
| EvaluationCase | `evaluation/models.py:27`：requirement、expected domains/files/risks/acceptance、forbidden claims、human notes；`evaluation/runner.py:20` 只加载 JSON；`tests/test_evaluation.py:55` 固定加载 3 条历史案例 | 规划新的 split、版本、gold、期望属性；不直接扩写历史案例 |
| Legacy evaluation | `evaluation/runner.py:42`：期望文件存在检查 → mock Legacy → artifact validator；`tests/test_evaluation.py:65` 分开 Mock 与空 human scores | 学习者判断结构、质量与 Live 证据的边界 |
| BenchmarkCase | `evaluation/benchmark.py:15`：5 个字段；`:41` 加载器固定 12 条、3 类各 4 条；`tests/test_benchmark.py:18` 对应数量约束 | 新的 30 条规划不能直接交给此加载器；今天不改实现 |
| 现有 benchmark 数据 | `benchmarks/cases/01-authentication-flow.json` 至 `12-api-contract-risk.json`；repository_understanding/change_planning/review_risk 各 4 条；`benchmark.py:75` 固定 mock Multi-Agent | 保持 portfolio fixture suite 身份，不自动并入 Dev/Holdout |
| benchmark 判定/统计 | `evaluation/benchmark.py:164` 检查 artifact 文件、manifest、schema counters；`:207` 聚合；Token/latency 只累加 status=passed 的 runs；`:120` 规范化时去掉 latency/artifact 路径 | R1 定义 passed 能支持的结论；后续定义成本统计范围 |
| Rubric | `evaluation/rubric.py:15` 有 10 个人工维度；`evaluation/models.py:73` 的 EvaluationScore 限制 0/1/2 并记录来源；`tests/test_evaluation.py:45` 覆盖范围 | 评分锚点、正反例和人工复核待学习者定义 |
| Validators | `evaluation/validators.py:33` 检查 Legacy 10-artifact、JSON、hash lineage、worker roles、只读 Tool 记录、来源路径、敏感模式；`tests/test_live_validation_import.py:60` 起有通过与拒绝测试 | 分开路径存在、payload hash、引用支持事实；本模块未找到完整语义 Citation 评估，记 unknown |
| Live import | `evaluation/runner.py:107` 验证已有 artifact，未调用 Provider；`tests/test_live_validation_import.py:60` 用手工 fixture 测试导入 | 由学习者解释其证明范围 |
| A/B | `evaluation/multi_agent_runner.py:8` 声明另一组 10 维；`:43` 汇总传入分数；`:56` 同 repo/requirement 跑两条 mock 路径；`tests/test_evaluation_multi_agent.py:81` 断言两侧 artifact 分数 | 不把维度声明当自动评分实现；定义完整公平比较协议 |
| 报告 | `evaluation/report.py:11` 仅序列化 mode/status/notes 与 case finding codes | 所需质量/成本/版本字段先写合同，今天不扩 reporter |
| Evidence 观察点 | `evidence/collector.py:89` 选文件、`:100` 读取、`:109` 构造摘录、`:120` 裁剪；`evidence/models.py:117` 序列化 Context | 定义 file、fact、最终 Context 的不同评价单位 |

不一致记录：`evaluation/cases/multi_agent_case.py:5` 使用当前 EvaluationCase 没有的
`description/repo_path/expected_artifacts_count/min_dimension_score`；现有加载器只读
`*.json`。它不是可直接使用的模板；其他调用是否可达为 unknown。本日不修复，
不访问其中引用的其他项目。

本次未找到完整的 20 Dev + 10 Holdout 机器协议、正式 gold 检索评分器或统一的
10 条 Behavior Suite 执行入口，均记 unknown。现有测试不自动等于正式套件已完成。

## 3. 教学顺序与第 19 章配套

各项可以拆为多轮，但一轮只问一个主要判断；以下不是一次性问卷。

2026-09-13 教学调整：R1–R3 的微型判断只用于暴露证据边界，学习者反馈其工程和
架构获得感不足。后续不再连续做二选一；每轮由学习者提交一个可审查的小型合同或
设计，AI 以源码和反例审查。完成顺序为 D1 Metric Contract → D2 Evaluator
Contract → D3 Behavior Case → D4 数据纪律；仍保持每轮一个主要产物。

再次校准：学习者指出 YAML、字段整理、模板和源码映射可由 AI 完成。后续由 AI
直接起草这些材料，学习者只 Review 会改变结论可信度的边界、盲区与取舍；不要求
手填机械字段。AI-authored 内容仍不冒充 learner ownership。

| 顺序 | 判断主题 | 对应源码（相对 src/specflow） | 学习者产出 |
| --- | --- | --- | --- |
| R1 | benchmark passed 的含义 | `evaluation/benchmark.py:188`、`:235`；`tests/test_benchmark.py:118` | 用源码界定一个指标 |
| R2 | 文件存在、gold 与证据充分 | `evaluation/models.py:27`；`evaluation/runner.py:51`；`evidence/collector.py:89` | Task 字段与评价单位 |
| R3 | 计数、聚合、空 gold/缺失/失败 | `evaluation/benchmark.py:207`；`evaluation/metrics.py:39` | Eval Contract v1 与 T0 |
| R4 | Evaluator 正反例与盲区 | `evaluation/validators.py:33`、`:200`；`tests/test_live_validation_import.py:60` | Evaluator Contract v1；Day 9 再做机器 fixtures |
| R5 | A/B 的条件与不可比较项 | `evaluation/multi_agent_runner.py:43`、`:56`；`tests/test_evaluation_multi_agent.py:81` | 冻结比较协议 |
| R6 | Behavior 观察边界 | `evidence/models.py:32`；Tool/Runner/Handoff 测试按题定向展示 | 10 个槽位的四项行为断言 |
| R7 | Dev/Holdout 隔离与泄露 | `evaluation/benchmark.py:41`；`evaluation/runner.py:20` | 本人解释并冻结数据纪律 |

教材根目录（只读）：
`C:\Users\50469\python-learning\AI-Agent\22-llm-system-course-handbook`。

- `README.md`：确认知识手册与概念实验的边界。
- Day 8 定向读 `01-知识手册/19-RAG基础.md`，总计 30–45 分钟：19-1 的三阶段
  约 10 分钟；19-2 Chunk/Metadata 与“找到片段以后，条件还在不在”约 15–20 分钟；
  19-3 相似度与语义正确性的边界约 5–15 分钟。对照 selected_files/excerpts/Context。
- Day 9 使用 `02-实验手册/19-21-RAG离线对照实验.md` 理解 Recall、Precision、
  RR、RRF；RRF 是融合方法，不是质量评分。Day 8 不执行实验。
- 教材合成数据及其变体不得进入 SpecFlow Dev/Holdout。
- Milvus、Vector、Hybrid、Rerank 与相邻 `23-specflow-repository-rag` 最早 Day 15，
  且必须由 Day 14 ADR 触发；不是到日期就自动实施。

## 4. Eval Contract v1 待填骨架

当前 `draft / learner_pending`。逐轮由学习者定义，AI 整理定稿。

| 必填项 | 冻结时必须说清 |
| --- | --- |
| 身份与目的 | contract ID/version、状态、评测目标与不能支持的结论 |
| 评价单位 | case/run/evidence item；file、symbol、fact、citation 不默认为同一单位 |
| 数据身份 | suite/split/case IDs/dataset version、repository revision、标注与复核者 |
| 运行身份 | Legacy/Multi-Agent、mock/live、Provider/model、prompt、policy/limits、代码版本；不可得写 unknown，不适用写 N/A |
| 质量维度 | Task success/rubric、Evidence coverage/citation/unsupported reference、Risk/safe abstention、Test quality；含义由学习者定义 |
| 成本与稳定性 | Token/latency/LLM calls、failure/retry/terminal；注明采集来源和范围 |
| 每项计算协议 | 输入、分子/分母、单位、方向、聚合、空集合/缺失/失败处理、版本 |
| A/B 条件 | 相同任务、仓库、模型、限额、Evaluator 版本；有意改变的因素与不可比项 |
| T0 | metric、初值/理由、Provider/index/策略版本、status=hypothesis、校准计划；未选择相关 Provider/index 时记 unknown 及原因 |
| 阈值纪律 | Day 8 记录 T0；只在 Days 15–20 用 Dev 校准，Day 21 前冻结；不用 Holdout 回调 |
| 解释边界 | findings 与分数分开；标出失败/缺证据/不可比较；小型 Golden Regression Suite 不支持统计级微小生产提升结论 |

## 5. Evaluator Contract v1 模板

文档模板，不是 Python schema；正反例待本人判断，不是正式 Repository Task。

```yaml
evaluator_id: <稳定 ID>
version: v1
status: hypothesis
evaluates: <一个明确属性>
input_fields: <字段、来源、版本、前置条件>
method: <deterministic | human | llm_judge>
implementation_evidence: <源码/测试，找不到写 unknown>
output_contract: <pass/fail/unknown/N/A、分数/单位、finding、证据定位>
decision_rule: <阈值、缺失、异常和聚合>
should_pass: <学习者定义的最小正例及理由>
should_fail: <学习者定义的最小反例及理由>
known_blind_spots: <漏判或误判>
human_review: <复核内容、证据、分歧记录和处理>
calibration_evidence: <Day 9 fixtures 待执行>
```

Day 8 定义正反例的属性，Day 9 创建并验证机器 fixtures。未校准 Rubric 保持
hypothesis，不直接触发架构修改。确定性 Test/Artifact/Span 优先，语义部分才考虑
LLM judge；今天不接入模型或评分平台。

## 6. Repository Task 模板与 30 个 ID

只预留编号和 ROADMAP §3.1 配额，不写正式题面、gold 或逐题期望。

| 类别 | Dev ID | 数量 | Holdout ID | 数量 |
| --- | --- | --- | --- | --- |
| 精确关键词 | SF-RT-D001–D005 | 5 | SF-RT-H001–H003 | 3 |
| 语义改写 | SF-RT-D006–D010 | 5 | SF-RT-H004–H006 | 3 |
| 多文件链路 | SF-RT-D011–D014 | 4 | SF-RT-H007–H008 | 2 |
| 无答案 | SF-RT-D015–D017 | 3 | SF-RT-H009 | 1 |
| 安全/旧索引 | SF-RT-D018–D020 | 3 | SF-RT-H010 | 1 |
| 合计 | 20 个独立 Dev ID | 20 | 10 个独立 Holdout ID | 10 |

```yaml
case_id: <预留 ID>
suite: specflow_repository_tasks
dataset_version: <冻结时填写>
split: <dev | holdout>
holdout_evidence_level: <dev=N/A | holdout=frozen_internal_holdout>
category: <五类之一>
repository_revision: <固定提交>
requirement: <Day 8 留空>
answerability: <answerable | unanswerable | safety_reject；待本人定义>
gold_evidence: <相对路径、符号/事实、行号及 revision；Day 8 留空>
expected_properties: <必须满足的可观察属性；Day 8 留空>
forbidden_claims: <禁止声称的内容；Day 8 留空>
legal_terminal_state: <与预期行为绑定；Day 8 留空>
evaluator_ids: <ID 与版本>
annotation_provenance: <作者/复核者/来源/版本>
isolation_group: <同源或改写关联组，不跨 split 泄露>
```

这是新数据契约草稿，不承诺兼容现有两个加载器。空 gold 怎样区分无答案、标注
缺失和安全拒绝，由学习者判断后冻结。

## 7. Agent Behavior 模板与 10 个槽位

独立 suite，不用于 Retrieval 调参，沿用 ROADMAP §7 十类。

| ID | 规划类别 |
| --- | --- |
| SF-AB-001 | Tool Selection |
| SF-AB-002 | Argument Validation |
| SF-AB-003 | Timeout / Retry |
| SF-AB-004 | Loop Termination |
| SF-AB-005 | Permission |
| SF-AB-006 | Prompt Injection / Context Pollution |
| SF-AB-007 | No Evidence |
| SF-AB-008 | Required Handoff Failure |
| SF-AB-009 | Handoff Schema |
| SF-AB-010 | Handoff Integrity |

```yaml
case_id: <SF-AB-001 至 SF-AB-010>
suite: specflow_agent_behavior
version: v1
scope_and_trigger: <真实执行路径、前置条件与触发>
must_happen: <必须发生的可观察事件>
must_not_happen: <禁止事件及观察边界>
legal_terminal_state: <终态、退出码/错误类型映射>
observable_evidence: <Test/Artifact/Span 的具体字段、顺序或计数>
evaluator_id: <确定性优先；语义部分另记>
reachability: <proven | unknown | N/A，附源码理由>
actual_trajectory: <本日未执行；以后记录 tool/args/observation/retry/approval/deny>
```

四字段模板与 10 个槽位在 Day 8 冻结；具体正式内容留到 Day 9 数据任务。本日源码
导航只证明可达路径，不凭类别名称假设存在 Agent Tool Loop、Retry 或相应路径；
终态和观察点不可证实时写 unknown。

## 8. 数据纪律（FROZEN）

1. 固定 20 Dev + 10 `frozen_internal_holdout`；数据来源不独立，不声称严格盲测。
2. Day 9 固定 Case ID、内容、Gold、dataset/annotation version 和 isolation_group；
   同源问题整体进入一个 split，教材合成数据不得并入。
3. Days 10–20 不使用 10 条内部冻结题或逐题结果修改 Prompt、策略、阈值或 Evaluator。
4. Day 20 冻结 code/model/Prompt/Policy/Evaluator/阈值/运行配置；Day 21 按冻结配置
   运行一次、保存原始结果，结果差也不回调参数。
5. 若内容或结果用于开发/调参，降级为 `contaminated_internal_check`；替换题目只能
   创建新的 dataset version，不能恢复原版本证据等级。不使用 Primary/Reserve。
6. 允许声称：在 10 条预注册、未参与调参的内部冻结用例上完成一次性验证。
7. 禁止声称：严格盲测、独立数据泛化、统计显著性、生产流量效果、未知仓库普遍泛化。
8. 未来只有同时具备独立来源、独立保管者和真实访问隔离，才定义
   `blind_independent_holdout`。
9. 历史 evaluation、12 条 portfolio benchmark、10 条 Behavior、教材合成练习、
   正式 30 条任务分别标 suite，不拼成一个总通过率。Fake/Mock 只证明对应工程合同。

## 9. 收束与恢复

规划核验（2026-09-13）：

- ROADMAP 相对启动版本只有一处 8 行插入；Week 2 原表与 §6 条件门保持原文。
- 已核对 20 Dev / 10 Holdout / 10 Behavior ID、模板必填键、代码围栏和本地链接。
- `uv run --no-sync pytest -v`：`777 passed, 3 skipped, 3 warnings in 11.30s`。
- `uv run --no-sync ruff check .`：通过；`uv run --no-sync ruff format --check .`：
  `210 files already formatted`。使用现有依赖，不同步安装。
- `git diff --check`：通过。上述是既有回归检查，不是新的 Dev/Holdout baseline。

- [x] 核对基线、读取材料、盘点现有能力。
- [x] 执行卡、合同骨架、30/10 模板与 ID 规划。
- [x] ROADMAP 教材对应关系、CURRENT 的 Day 8 TUTOR 状态。
- [x] 冻结 Eval Contract v1；Recall T0 保持有理由的 hypothesis/unknown。
- [x] 冻结 Evaluator Contract v1；AI 起草正反例/盲区，学习者 Review 关键边界。
- [x] 冻结 10 条 Behavior 模板；Review No Evidence 双层状态，其余不可达项留 unknown。
- [x] 冻结 A/B、数据纪律、非目标和 frozen_internal_holdout 证据等级。
- [x] 完成第 19 章 Retrieval/Context Assembly 应用判断。
- [x] 通过侧对话闭卷复述完成结构/事实/Context/Citation 等核心边界 Teach-back。
- [x] 记录本人原答、【正确答案】、差异与 readiness，收束 Day 8。

Day 8 已完成。下一步只能在用户显式启动 Day 9 后创建 Dataset v1 与 Evaluator
Fixtures；不得由本卡自动进入正式数据、baseline 或 RAG。
各轮记录见 [Day 8 证据卡](evidence/day-08.md)。后台导航见
[源码 Evidence Pack](evidence/day-08-source-pack.md)，其状态为
`AI-prepared / learner-unverified`。
规划落盘不等于 Day 8 完成；教学完成后停在 Day 8，不自动启动 Day 9。
