# Current Study State

- Roadmap: [ROADMAP_V5_3_2.md](ROADMAP_V5_3_2.md)
- Roadmap version: V5.3.2 Learning Effectiveness Patch
- Campaign phase: Measure (Day 8-14)
- Study status: DAY 8 IN PROGRESS — execution plan ready; learner answer pending
- Day: 8
- Current mode: TUTOR
- Updated on: 2026-09-13

## Day 8 active contract

用户明确授权开始 Day 8：先创建执行卡、最小补充 ROADMAP，然后直接教学。
执行与恢复入口：[Day 8 执行卡](day-08-execution-card.md)。当前合同为草稿，
还没有学习者验收证据；Day 7 ownership 保持 `IMPROVING`。

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

下一步：直接开始 R1，展示 `src/specflow/evaluation/benchmark.py:188–191`、`:235`
及 `tests/test_benchmark.py:118–120`，判断 run_success_rate 是否能代表真实需求完成率。
等待本题答案，不再等待“开始”。完成本日教学与证据记录后停止，不自动进入 Day 9。

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
