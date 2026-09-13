# Day 9 证据卡

- 日期：2026-09-13。
- 唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 启动 revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`；工作区启动时干净。
- 当前模式：`TUTOR`；状态：`AI_PREPARED / LEARNER_REVIEW_PENDING`；执行入口：[Day 9 执行卡](../day-09-execution-card.md)。

## AI-authored 工作

- 读取冻结合同、Day 8 收束材料与教材，核对 Git 基线。
- 创建本日执行卡及恢复记录；这些是学习脚手架，不是学习者能力证据。
- 已完成启动源码/测试/12 条历史案例阅读；[Evidence Pack](day-09-source-pack.md) 保存盘点和复查命令。
- 已运行只读教材函数并保存 [离线结果](day-09-offline-results.json)；退出码 0，数值断言通过。
  固定排序/Gold，K=1/4 分别得到 Recall=0.5/1、Precision=1/0.5、RR=1/1。
- 产品源码、Prompt、参数、Evaluator 实现、历史 benchmark 案例均未修改。
- 后续已创建 30 条正式 ID 对应的数据草案、34 个 Fixtures 与 manifest；尚未正式冻结数据。
- 未运行新的正式 Dev/Holdout baseline 或 Live Provider；已有回归测试结果单列。

## 学习者本人证据

Day 9 尚无本人技术判断、预测、实验解释或语义 Review；用户的范围与效率指令不替代这些能力证据。
继承 Day 8 整体 `improving / partial`；Holdout 等级的有界决策 `verified` 仅保留原范围。

## R1 — 离线指标与方案结论

- 主要判断：在固定 Gold 的离线对照中，只看到 Recall 上升是否足以宣布检索方案改进。
- 材料：教材 `retrieval_metrics`、`rrf`；项目 Evidence 的选择、摘录、Context 观察面。
- 发出的主要 Review：AI 提案“把 K 从 1 扩到 4，Recall 从 50% 变成 100%，因此可以认定检索方案更好，正式评测只保留 Recall。”是否接受；用表中一个变化说明理由。
- 本人原答：pending。
- 【正确答案】与标准表述：收到本人回答后提供并记录，不提前伪造 Review。
- 差异与 readiness：pending。

## 恢复点

启动材料核验：4 个 Markdown 的围栏/本地链接、离线 JSON 与语义标记检查通过；
`git diff --check` 通过，产品/测试/历史 benchmark/依赖 diff 为空。
初次临时链接检查误把 Python 下标调用识别成 Markdown 链接，排除 fenced code 后复核通过；
这不是产品故障，未修改产品或教材。尚未运行全量回归、创建完成报告或提交 Day 9。

R1 已展示但尚无本人回答；该数值已公布，只算 AI 演示。下一次手算使用新的未公布输入。
本日范围是 Dataset v1、Evaluator fixtures、Holdout manifest 与概念教学；不推进后续日程。

## AI 批量准备（用户于 2026-09-13 明确授权）

用户指令：现在把 AI 可以搞完的内容先一步搞定，避免浪费时间。
已完成源码取证、候选与字段写作、数据/fixture 文件、两个审查视图、manifest 和机械检查。

- Dataset：20 Dev + 10 Holdout，版本 v1-draft.1；34 个不同事实与 65 处定位已核验。
- Fixtures：7 项共 34 个，8 个现有核心调用通过，26 个仅有预期，不冒充 scorer 已运行。
- Holdout 创建与作者机械检查的访问已记录；从未执行正式 Case，不用于调参。
- 回归：777 passed、3 skipped、3 warnings；Ruff lint/format 通过。
- 默认检查不读取 Holdout 内容，也不把未检查的跨 split 重叠写为零。
- AI 编写的答案/条件/盲区仅为待 Review 材料；未计本人 ownership。

剩余本人工作集中在 [审查入口](../day-09-review-pack.md)。数据与 Fixtures 的语义 Review、
manifest Review 和闭卷复述完成前，保留 draft_pending_review / frozen=false。
详细结果与命令：[AI 准备报告](../../reports/day-09-ai-preparation-report.md)。
