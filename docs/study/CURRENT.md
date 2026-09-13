# Current Study State

- Roadmap: [ROADMAP_V5_3_2.md](ROADMAP_V5_3_2.md)
- Roadmap version: V5.3.2 Learning Effectiveness Patch
- Campaign phase: Measure (Day 8-14)
- Study status: DAY 9 AI PREPARATION COMPLETE — DATASET / FIXTURES AWAITING LEARNER REVIEW
- Day: 9
- Current mode: TUTOR
- Updated on: 2026-09-13

## Day 9 active contract

用户于 2026-09-13 在独立任务中明确启动 Day 9，授权创建 Dataset v1、Evaluator
calibration fixtures、Holdout evidence-level manifest、执行卡与恢复记录，并直接开始教学。
唯一项目为 `D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
启动 HEAD `08e5a66f8ea8216433c72744adab92aa07d99c45`，启动工作区干净；不重做 Day 8。

执行入口：[Day 9 执行卡](day-09-execution-card.md)；本人记录：[Day 9 证据卡](evidence/day-09.md)。
启动源码阅读与离线概念实验已完成，见 [Day 9 Evidence Pack](evidence/day-09-source-pack.md)。
用户随后明确要求“AI 可以搞完的内容先一步搞定”。AI 已批量完成 30 条任务、34 个 Fixtures、
manifest、访问记录及机械核验，统一入口为 [Day 9 审查包](day-09-review-pack.md)。
当前下一步：学习者回来后再继续一个主要判断；可先做未公布答案的手算，再审三锚点与关键 Fixtures。
早先公布数值的离线实验只算 AI 演示，不算学习者预测或过关。
AI 完成候选数据/格式/机械核验；学习者只 Review 关键 Gold、Evaluator 盲区、隔离与取舍。
每次回答后明确给【正确答案】与标准表述；AI-authored 不计本人 ownership。
Day 8 整体仍为 `improving / partial`；Holdout 等级的有界决策保持 `verified`，不外推。

本日已创建 20 Dev + 10 frozen_internal_holdout 的 `v1-draft.1` 草案：34 个不同事实、
65 处源码定位检查通过；所有 Gold/annotation 绑定启动 revision，组/事实/Gold 来源文件不跨 split。
七项 Evaluator 共 34 个 Fixtures，8 个现有核心 helper 的结果匹配预期，26 个仅保留合同预期。
数据与 Fixture 的本人语义 Review 尚未完成，因此保持 draft_pending_review / frozen=false。
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
