# Current Study State

- Roadmap: [ROADMAP_V5_3_2.md](ROADMAP_V5_3_2.md)
- Roadmap version: V5.3.2 Learning Effectiveness Patch
- Campaign phase: Measure (Day 8-14)
- Study status: DAY 11 IN PROGRESS — ADAPTER VERIFIED, FAIRNESS REVIEW PENDING
- Day: 11
- Current mode: REVIEW
- Updated on: 2026-09-14

## Day 11 active contract

用户已明确启动 Day 11，并进一步授权先完成所有不依赖公平性选择的 AI 工程工作：执行卡、恢复记录、
gap trace、T-076、Multi-Agent adapter/请求观察/attempt 报告、输入隔离、测试、报告骨架和机器记录。
正式 20 Dev 仍只能在学习者裁决 Legacy max_selected_files=5 与 Multi-Agent=10 后运行一次。

唯一工程目标是复用同一 20 Dev、`08e5a66f8ea8216433c72744adab92aa07d99c45`
源码快照、`deepseek-flash`、requirement-only 投影和 Day 10 报告语义，测 Multi-Agent 当前版本。
不因 Day 10 的 2/20 修 Legacy Context 接线，不改 Dataset/Gold/Prompt/检索策略/Context 限制/
阈值/Evaluator/模型，不实现 RAG/Vector/Hybrid/Rerank，不安装依赖。

恢复入口：[Day 11 执行卡](day-11-execution-card.md)；规格：
[T-076](../tasks/T-076-dataset-v1-multi-agent-dev-adapter.md)；只读事实：
[Day 11 Gap Trace](evidence/day-11-gap-trace.md)；报告骨架：
[Multi-Agent Dev Report](../reports/day-11-multi-agent-dev-report.md)。当前正式状态为
20 planned / 0 attempted / 20 not_started。

T-076 适配已完成：Multi-Agent 请求观察覆盖 6 次 Coordinator enrichment 与真实 AgentRunner
receiver，请求副本不可变且 observer 失败不改变 Provider 异常/调用次数；harness 支持 Multi-Agent
逐 attempt journal、artifact observation、usage 缺口和 fairness gate。RED 为缺少观察类的收集失败；
GREEN 为 35 focused passed，相关回归 72 passed，全量为 807 passed、3 skipped、3 known warnings；
Ruff lint/format、diff check、冻结 Dev/fixture 与 Word 边界通过。prepare-only 正式执行门实测 exit 2，
attempts 文件不存在。完成报告见 [Day 11 Adapter Report](../reports/day-11-adapter-completion-report.md)。
adapter 已聚焦提交；gitignored Day 11 config 已冻结 openai-compatible/deepseek-flash 和干净的
runtime code identity。没有读取 `.env` 或输出凭证值；fairness 仍 pending，正式 Provider 尚未调用。

Legacy 请求观察的正确归因保持：Collector 有 744 excerpts，但 60 个 Worker 请求均没有
Repository Evidence；最早错误是 Context 接线，不是 Collector 全败或 DeepSeek 不会读代码。
Day 10 质量门为 802 passed、3 skipped、3 known warnings。启动工作区只有无关未跟踪 Word，
必须保留、不删除、不覆盖、不暂存。

教学按 D001 → D015 → D018 → D017 进行，每次只展示一个 Case 的 requirement、sources、
llm-requests、generation、expected_properties/forbidden_claims；学习者用三句话回答后，AI 才给
【正确答案】、差异和 evidence path。AI 产物不提升 ownership。

## Day 10 active contract

用户于 2026-09-14 在本窗口明确启动 Day 10；唯一项目为
`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`，已首先进入并核对 cwd 与 Git 根。
启动 HEAD 为 `cb665b4`，Dataset v1 冻结内容为 `bf77d19455cb989984dc4f909e6e7ca4b4f91aaf`，
目标仓库/Gold revision 为 `08e5a66f8ea8216433c72744adab92aa07d99c45`；不重做 Day 9。

执行与恢复入口：[Day 10 执行卡](day-10-execution-card.md)；本人记录：[Day 10 证据卡](evidence/day-10.md)。
已先完成 gap trace 并展示规格，随后按用户明确授权完成 T-075 PATCH 和必要验证。
用户最新要求是先完成 AI 可独立工作，教学判断延后；不再重复请求 PATCH 批准。
学习者的运行前预测、关键 Diff Review、代表 Case 解释与 Teach-back 尚未完成；
本日尚无本人回答，不因 AI 产物提升 ownership。恢复教学后每轮一个主要判断，回答后给【正确答案】。

本日只允许 Legacy Dev；不运行 Multi-Agent baseline，不改 Prompt、检索策略、阈值或 Evaluator
语义，不实现 RAG/Embedding/Vector/Hybrid/Rerank。Holdout 只读 manifest 元数据；禁止读取
`datasets/v1/holdout.json`，不执行 Holdout。旧 12 条 portfolio suite 不得冒充 20 Dev。
原未跟踪 `docs/study/SpecFlow-Agent-30天能力战役-更新执行版.docx` 必须保留，不覆盖、不删除、不暂存。
成本遥测不完整为 not_comparable；实现无证据为 unknown；结构通过不等于 task success。

只读追踪已完成：[Gap Trace](evidence/day-10-gap-trace.md)；
冻结规格与测试边界：[T-075 v1](../tasks/T-075-dataset-v1-legacy-dev-adapter.md)。
旧 12 条入口与新 Dev 不兼容；Legacy Worker 未读取传入 WorkerContext 的摘录来构建请求，
该行为已由合成 marker 的实际请求观察复现：Collector 有摘录，但三个 Legacy Worker 请求不含该摘录。
产品接线保持原样，不能只从 sources.json 推定 Context 事实覆盖。
用户随后要求“现在先把AI可以解决的内容解决了，再给我谈后续的内容”，并通过任务同步明确
批准 T-075 PATCH、Day 11 镜像脚手架和一致性测试。规格已冻结为 v1；实现与质量门已完成，
暂停教学提问，不把执行授权记为 R1 回答。Legacy 产品 Prompt/检索/Context 接线保持原样。
新增 dataset_v1.py、dev_baseline.py、run_dev_baseline.py、两份测试；runner.py 仅增加请求观察钩子。
验证结果：802 passed、3 skipped、3 known warnings；Ruff lint/format 与 diff check 均通过。
本次新增 25 项测试。真实数据仅 prepare-only：20 planned / 0 attempted / 20 not_started。
隔离源码快照及两侧公共配置已生成于 `data/day10/`；Day 11 镜像为 plan-only，执行明确禁用。
初始进程没有 SPECFLOW_LLM_BASE_URL/API_KEY/MODEL。后续按用户要求从本机只读发现 DeepSeek
Harness 配置：已有 DeepSeek 凭证，官方 OpenAI-compatible models 入口实际返回
`deepseek-flash` 与 `deepseek-v4-pro`。选择与当前 Flash 档对应的 `deepseek-flash`，
完成一次兼容性 smoke 后，冻结 Day 10/11 共用模型身份；未读取 .env 或输出凭证值。
Multi-Agent 选文件上限 10，Legacy 默认 5，已在镜像协议显式记录 not_comparable；不调整该限额。
当前恢复入口：[T-075 完成报告](../reports/day-10-adapter-completion-report.md)、
[验证摘要](evidence/day-10-adapter-validation.json)。提交由完成报告所属 Git commit 定位。
正式 Legacy Dev 已完成：20 planned / 20 attempted / 0 not_started，20 条均 product completed、
exit 4/degraded；无顶层重跑。60 个实际请求均可观察，Repository Evidence 进入请求为 0，
Evaluator-only/study 路径泄露为 0。AI 按冻结属性复核 task_success=2/20；14 个 answerable
Case 的 23 条 Gold facts 在最终请求 Context 为 0/23。Token run coverage=16/20，完整成本 unknown，
Day 11 成本比较 not_comparable。详见 [Legacy Dev Report](../reports/day-10-legacy-dev-report.md)
与 [AI Semantic Review](evidence/day-10-legacy-semantic-review.json)。AI Review 不计 learner ownership。

Day 10 到此结束；不自动执行 Day 11。Day 11 启动时复用同 Dataset/revision/模型/投影和报告口径，
但必须先裁决 Legacy max_files=5 与 Multi-Agent=10 的限额差异，并补 Multi-Agent 实际请求观察。
不因 Day 10 失败调 Prompt、检索、Context 接线、限额、阈值或 Evaluator；不进入 Holdout。

## Day 9 archived completion record

以下为 Day 9 的历史完成状态和当时停止线；用户已明确启动 Day 10，当前授权以上方为准。

用户于 2026-09-13 在独立任务中明确启动 Day 9，授权创建 Dataset v1、Evaluator
calibration fixtures、Holdout evidence-level manifest、执行卡与恢复记录，并直接开始教学。
唯一项目为 `D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
启动 HEAD `08e5a66f8ea8216433c72744adab92aa07d99c45`，启动工作区干净；不重做 Day 8。

执行入口：[Day 9 执行卡](day-09-execution-card.md)；本人记录：[Day 9 证据卡](evidence/day-09.md)。
启动源码阅读与离线概念实验已完成，见 [Day 9 Evidence Pack](evidence/day-09-source-pack.md)。
用户随后明确要求“AI 可以搞完的内容先一步搞定”。AI 已批量完成 30 条任务、34 个 Fixtures、
manifest、访问记录及机械核验，统一入口为 [Day 9 审查包](day-09-review-pack.md)。
学习者于 2026-09-14 同步此前教学进度：离线 Recall、Precision、RR 与 RRF 已通过，
但当前证据卡未保存原始先验答案，因此登记为 learner-reported passed，真实 Dev 报告中再重测。
三条 Dev 锚点已审。学习者于 2026-09-14 提供截图同步实际进度：当前正在集中审查
D015-D020 的 answerability；D015-D017 草案为 unanswerable，D018-D020 为 safety_reject。
上一轮 Fact Recall Fixture 不再重复。安全/旧索引 coverage 仍由 AI 修订，不计 ownership。
学习者已正确识别 D018-D020 的敏感与越界边界，但未解释 D015-D017 的指定证据缺失；
已给【正确答案】，answerability 区分记为 practicing / partial。当前进入 `CAL-CS-F01`：
路径存在且合法，但引用语义不支持 claim 时，Citation Support 应如何裁决。
学习者随后正确判定 `CAL-CS-F01` 为 fail；理由经补充为 claim 删除了
`approved is True` 必要条件。当前进入 `CAL-TC-U01`：attempted-run 清单完整性未知时，
Token Completeness 的 verdict、coverage 和完整总成本如何记录。
侧对话记录随后同步：离线指标/RRF 已通过；Fact Recall、Token Completeness 和 Safe
Abstention 均完成首次判断、纠正与标准答案；Source/Citation 判断正确。Holdout 边界与污染
语义已讲清，stale index 记为 case_count=0/not_covered，当前无索引时 runtime capability=N/A。
当前停点是结构合同与任务语义的独立裁决：七件 artifact 与 0/6 Schema 均满足，
但 agent output 是无关天气内容。等待学习者同时判断 contract_run_success 与 task_success。
学习者最终正确判断 `contract_run_success=pass`、`task_success=fail`，并完成 Day 9 最后一个
关键边界 Review。Dataset/annotation version 已冻结为 v1；Holdout 执行数为 0，未参与调参。
Day 9 已在冻结内容提交 `bf77d19455cb989984dc4f909e6e7ca4b4f91aaf` 收束。
用户已明确要求另开 Day 10 窗口，须从该准确检查点启动，不在本任务执行 Day 10 baseline。
AI 完成候选数据/格式/机械核验；学习者只 Review 关键 Gold、Evaluator 盲区、隔离与取舍。
每次回答后明确给【正确答案】与标准表述；AI-authored 不计本人 ownership。
Day 8 整体仍为 `improving / partial`；Holdout 等级的有界决策保持 `verified`，不外推。

本日已冻结 20 Dev + 10 frozen_internal_holdout 的 `v1`：34 个不同事实、
65 处源码定位检查通过；所有 Gold/annotation 绑定启动 revision，组/事实/Gold 来源文件不跨 split。
七项 Evaluator 共 34 个 Fixtures，8 个现有核心 helper 的结果匹配预期，26 个仅保留合同预期。
关键语义边界 Review 已完成；未逐条本人审阅的内容继续标为 AI-authored，不提升 ownership。
详见 [AI 准备报告](../reports/day-09-ai-preparation-report.md)；这不是 Day 9 最终收束。
保持 frozen_internal_holdout / never tune / freeze 后 run once / creator 与 access control 不独立。
不使用复杂加密或 Primary/Reserve；污染后降级，替换必须新版本且不能恢复旧证据等级。
不运行 Legacy/Multi-Agent baseline、Holdout 或 Live Provider，不改产品/Evaluator/Prompt/策略/阈值，
不装依赖，不实现 RAG/Vector/Hybrid/Rerank，不进入 Day 10–15。

本轮质量检查：777 passed、3 skipped、3 warnings；Ruff lint/format 通过，211 个文件格式合格。
已有回归测试中的 mock fixture 运行不作为正式 Dev/Holdout baseline。默认数据检查不读取 Holdout 内容。

## Day 8 archived completion record

以下保留 Day 8 的历史完成状态与当时停止指令；用户已显式启动 Day 9，当前授权以上方为准。

用户明确授权开始 Day 8：先创建执行卡、最小补充 ROADMAP，然后直接教学。
执行与恢复入口：[Day 8 执行卡](day-08-execution-card.md)。Eval/Evaluator Contract v1
已冻结；其中 implementation_status=unknown 的能力仍是明确缺口，不冒充已有实现。
[Day 8 证据卡](evidence/day-08.md) 已记录 R1：定位判定行正确，但将 contract pass
外推成需求完成；R1b 在反馈后正确判断 passed。R2 结论正确，但混淆了磁盘
不存在与 Evidence 漏选。R2b 正确选择事实级 Gold，理由侧重文件移动，尚需补足
“文件命中不等于事实命中”。R2c 正确要求显式 answerability，R2d 正确判断标签
不应进入模型任务输入；已将其冻结为 Evaluator-side metadata。R3 正确区分成本与
效果，但未识别 passed-only 聚合对成本本身造成的选择偏差。R3b 正确将全部
attempted runs 纳入资源成本集合。R3c 正确区分观测 0 与 unknown/incomplete，
并将现有 0 回退登记为 Evaluator 盲区。R3d 正确判定遥测不完整时成本不可比较。
成本合同已形成：all attempted、0/unknown 分离、coverage、not_comparable。
R3e 正确把无 Gold/scorer/Dev 校准的 Recall T0 标为 hypothesis。侧对话的最终闭卷
复述已覆盖结构/语义、Gold 泄露、失败成本与 frozen_internal_holdout 边界。
当前整体 ownership 为 `improving / partial`。

学习者反馈连续判断题缺少工程/架构获得感。后续教学已改为“本人提交小型合同/设计
→ AI 源码审查与反例攻击”：D1 Metric Contract、D2 Evaluator Contract、
D3 Behavior Case、D4 数据纪律。微型判断只作诊断，不冒充 C3/C4 ownership。

D1 已由学习者提交并接受源码审查：纳入集合基本正确；missing_data 混淆产品失败
与 Evaluator 不完整；A/B 条件有方向但不可执行。当前 `practicing`，不是 C4 verified。
学习者指出 YAML/模板应由 AI 完成；已采纳。AI 后台起草 Eval/Evaluator Contract，
学习者只审查会改变结论可信度的边界、盲区与取舍。D2 接受路径有效/语义支持拆分，
但误认为拆分后两者均获保证；已纠正 citation_support 为 contract-only/unknown。
D2b 已接受复合三值规则：fail/unknown/pass 不互相冒充。D3 首次把合法失败运行
判为 Behavior fail，经解释后正确修正为 product failed / Behavior pass。D4 正确
拒绝同 Gold 的语义改写跨 split，并纠正为同源近重复泄露；同一仓库本身不是污染。
D4b 进一步指出“直接替换”不能防止重复泄露；随后继续识别密封/Reserve 不会使
同一开发流程生成的数据变成独立 Holdout。最终冻结 `frozen_internal_holdout`：
10 条、never tune、freeze 后 run once、creator/access control 不独立；污染后降级为
`contaminated_internal_check`，换题只能建立新版本。该有界 C4 决策为 verified。
Day 7 ownership 保持 `IMPROVING`。

- 目标：Eval/Evaluator Contract v1、20 Dev + 10 Holdout 的模板/ID、10 条 Behavior
  模板与断言、非目标和数据纪律。AI 检索与排版，学习者负责判断和解释。
- 每轮一个主要判断，同时展示源码；回答后无论对错都标【正确答案】并解释差异。
- 本日允许学习行政文档更新，不构成产品 PATCH 授权。
- 不写正式 30 条数据，不查看/运行/调参 Holdout，不跑新的 Dev baseline；不修改
  产品、现有案例或依赖，不安装 Milvus/向量库，不进入 Day 9 或后续日程。
- 第 19 章定向阅读 30–45 分钟；离线 Recall/Precision/RR/RRF 实验属于 Day 9。
  教材合成数据不得进入项目 Dev/Holdout。
- Milvus、Vector、Hybrid、Rerank、23-specflow-repository-rag 最早 Day 15 且由
  Day 14 ADR 触发。不可证实的实现事实写 unknown。

第 19 章应用题已正确归因为 Context Assembly；侧对话闭卷复述与本题共同完成最终
Teach-back。正确答案、差异和 readiness 见 [Day 8 证据卡](evidence/day-08.md)。
后台 [源码 Evidence Pack](evidence/day-08-source-pack.md) 已完成，状态保持
`AI-prepared / learner-unverified`。
Day 8 已收束。停止，不自动进入 Day 9；正式数据、fixtures 和 baseline 均待用户
在独立任务中显式启动。

## Day 7 archived record

以下各节保留 Day 7 收束时的历史状态与当时停止指令。用户于 2026-09-13 显式启动
Day 8，当前模式和下一步以上方 Day 8 active contract 为准；不重做 Day 7/T-074。

## Completed objective

Recover one concrete mock Multi-Agent path from test input through Evidence,
Agent stages, Review, Artifact, and terminal return; retest Day 4/5/6 partial
items on changed surfaces; produce Control Matrix v1; test Tool Permission
reachability; and complete one learner-predicted correctness-failure loop.

## Completed deliverables

- One source-grounded mock Run trace using
  `test_run_multi_agent_mock_mode`, with explicit test-evidence boundaries.
- Changed-surface Day 4/5/6 retests for path validation, Context visibility,
  and Handoff failure propagation.
- Control Matrix v1 covering Coordinator LLM, Specialist/Reviewer LLM,
  Evidence Tools, and Artifact Write with scoped `✓ / × / unknown` results.
- Tool Permission reachability judgment: no current standard
  `AgentRunner → ToolExecutor` path was proven.
- T-074: reproduced ignored `policy.repository.max_file_bytes`, froze a task,
  implemented one shared translation for both runners, and verified the fix at
  commit `952a952`.
- Retest Queue v1 with all role-critical Week 1 items retained as `improving`
  rather than promoted from AI-generated summaries.

## Evidence

- [Day 7 evidence card](evidence/day-07.md)
- `docs/study/control-coverage-backlog.md`
- `docs/tasks/T-074-repository-file-limit-policy-wiring.md`
- `docs/reports/T-074-completion-report.md`
- T-074 RED: `2 failed` because both ToolCall records had `truncated=false`.
- T-074 GREEN: `2 passed`; affected paths `107 passed, 1 skipped`.
- Full validation: `777 passed, 3 skipped, 3 known warnings`.
- Ruff lint, Ruff format, and `git diff --check`: passed.

## Completion boundary

Week 1 teaching content and the T-074 technical loop are complete. Learner
ownership is `improving / partial`: the learner personally reproduced and
located the failure, selected the design, challenged its consequences, and
reviewed the critical Diff; Codex authored the task specification, tests,
product Patch, report, and commit. This does not claim independent manual
product coding or `stable` closed-note mastery.

## Current mode contract

This record closes Day 7 in REVIEW. Do not extend T-074 or promote any
`improving` item to `stable` without a changed-surface retest. Any future study
task requires an explicit user transition and must re-read the current roadmap,
evidence, backlog, and relevant source/tests.

## Forbidden until an explicit transition

- Do not enter Day 8 or create Eval/Dataset assets.
- Do not start Repository RAG, Vector, Hybrid, Rerank, or external-donor work.
- Do not patch Control Coverage backlog items without a new reproduction,
  explicit approval, and frozen task specification.

## Stop condition

Day 7 content, T-074 validation, evidence capture, Control Matrix v1, and Retest
Queue v1 are complete. Remaining `improving` and `unknown` items are carried
forward rather than forced closed.

## Next action

Stop at Day 7. Wait for the learner to explicitly start Day 8 in a separate
teaching task; do not infer the transition from Week 1 completion.
