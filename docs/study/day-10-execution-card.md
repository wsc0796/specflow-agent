# Day 10 执行卡 — Legacy Dev 输入隔离与基线

- 日期：2026-09-14；唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 模式：`REVIEW`；状态：`ADAPTER_READY / BLOCKED_LIVE_IDENTITY / TEACHING_DEFERRED`。
- 授权：用户明确启动 Day 10，允许执行卡、最小恢复记录、只读 gap trace、适配规格草案与教学。
- 产品/评测 PATCH：T-075 展示后，用户已要求 AI 先完成可独立工作，并同步明确实现授权。
  允许 Day 11 镜像配置/一致性测试，不允许运行 Day 11 baseline；教学判断延后。
- 恢复入口：[CURRENT](CURRENT.md)；学习记录：[Day 10 证据卡](evidence/day-10.md)。

## 启动快照

- 已首先 Set-Location 到唯一项目；Get-Location 与 git rev-parse --show-toplevel 均核对通过。
- 分支：`codex/t072-no-evidence-fail-closed`；启动 HEAD：`cb665b4`。
- Dataset v1 冻结内容：`bf77d19455cb989984dc4f909e6e7ca4b4f91aaf`；指针记录：`cb665b4`。
- Gold/目标仓库 revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- 启动唯一未跟踪文件：`docs/study/SpecFlow-Agent-30天能力战役-更新执行版.docx`。
  保留，不删除、不覆盖、不暂存进 Day 10 提交。
- Day 9 历史质量门：777 passed、3 skipped、3 known warnings；不是本日验证结果。
- 不重做 Day 9，不重标注或修改 Dataset/Evaluator v1。

## 本日目标与门禁

1. 读取指定合同、Dev 与 calibration，追现有 evaluation/benchmark 源码及相关测试。
2. 识别旧 12 条 portfolio suite 与新 20 Dev 的加载、投影、运行、评分及报告缺口。
3. 提交最小 task spec：独立 Dataset v1 loader、requirement-only 产品输入、Evaluator-only 标注、
   固定 revision 且排除评测答案材料的目标快照、明确实际 Context 与评分观察面。
4. 学习者审查影响结论的输入隔离、评分观察面、公平性。每轮只作一个主要判断；回答后给【正确答案】。
5. 若需代码修改，规格与测试边界先批准并冻结，再进入 PATCH；隔离与报告口径验证前不运行 baseline。
6. 入口验证就绪后，仅运行 Legacy Dev，保存全体 planned/attempted/not_started、失败与降级记录。
   Mock/Live 分开；运行配置与模型身份未确定前不得冒充真实质量基线。
7. 有证据才评分；unknown/N/A/not_comparable 保留，结构通过不等于 task success。

## 禁止范围

- 不读取 `docs/study/datasets/v1/holdout.json`；只允许读取 Holdout manifest 元数据；不执行 Holdout。
- 不运行 Day 11 Multi-Agent baseline，不改 Prompt、检索策略、阈值或 Evaluator 语义。
- 不实现 RAG/Embedding/Vector/Hybrid/Rerank，不增加依赖或第二项目。
- 不把旧 benchmark、calibration 或测试 fixture 执行冒充正式 Dev 运行。
- 不把 Gold/answerability/expected_properties/forbidden_claims/答案笔记传给产品或放进可检索目标。
- 不把 AI 生成的 trace/spec/测试/答案记为本人 ownership。

## 最小恢复清单

- [x] 核对目录与 Git 根；读取项目规则、路线、CURRENT 和 Day 9 完成报告。
- [x] 读取 Eval/Evaluator 合同与 manifest 元数据；建立执行卡与证据卡。
- [x] 完成 Dev/calibration 与 evaluation/benchmark 的只读 gap trace。
- [x] 准备最小 task spec 和测试边界；提交第一轮高价值 Review。
- [x] 展示规格后收到用户继续执行及明确 PATCH 授权；不将授权当作学习判断。
- [x] 完成获批范围实现与输入隔离/报告口径测试；Day 11 plan-only 镜像与一致性测试已完成。
- [ ] 冻结 Legacy Dev 运行身份与配置，完成基线和评分证据。
- [x] 完成 T-075 项目质量门与完成报告；对应代码、测试和文档纳入同一聚焦提交。

当前未运行任何 Day 10 baseline、Provider 或 Holdout。只读结果见
[Gap Trace](evidence/day-10-gap-trace.md)，最小规格见 [T-075](../tasks/T-075-dataset-v1-legacy-dev-adapter.md)。
Legacy WorkerContext 摘录未进入三类 Worker 请求的行为，已用合成 marker 完成请求边界实证。
用户已要求 AI 先完成适配、验证和报告，T-075 冻结为 v1，R1 教学延后。
本轮质量门：802 passed、3 skipped、3 known warnings，Ruff lint/format 与 diff check 通过。
真实 Dev prepare-only 为 20/0/20，产物在 `data/day10/`；
[完成报告](../reports/day-10-adapter-completion-report.md)记录结果和复现入口。
当前真实 Provider 环境三项均未设置；停在运行身份 blocker，不用 Mock 替代语义 baseline。
下一步配置身份后冻结配置，再执行 Legacy 20 Dev；不需要重新批准已经完成的 T-075。
