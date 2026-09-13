# Day 9 执行卡 — Dataset v1 与 Evaluator 校准

- 日期：2026-09-13；唯一工作项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 模式：`TUTOR`；状态：`AI_PREPARED / LEARNER_REVIEW_PENDING`。
- 授权：用户明确启动 Day 9，允许本日数据、fixture、manifest、Evidence Pack 与学习行政记录；直接开始教学。
- 恢复入口：[CURRENT](CURRENT.md)；本人证据：[Day 9 证据卡](evidence/day-09.md)。

## 1. 启动基线

- 已核对 cwd 与 `git rev-parse --show-toplevel` 均为上述唯一项目。
- 分支：`codex/t072-no-evidence-fail-closed`。
- HEAD：`08e5a66f8ea8216433c72744adab92aa07d99c45`，`docs: close Day 8 evaluation contracts`。
- 启动 `git status --short` 无输出，工作区干净；Day 8 不重做。
- 冻结输入：[Eval Contract v1](eval-contract-v1.md)、[Evaluator Contract v1](evaluator-contract-v1.md)。
- Day 8 整体 ownership 仍为 `improving / partial`；Holdout 等级的有界决策为 `verified`，不外推。
- 根 AGENTS 的 773 tests 是 T-072 历史记录；Day 8 记录 777 passed、3 skipped、3 warnings。
  两者均不是 Day 9 新运行结果。

## 2. 本日范围与交付

1. 只读教材 `C:\Users\50469\python-learning\AI-Agent\22-llm-system-course-handbook\02-实验手册\19-21-RAG离线对照实验.md`
   与同目录 `offline_concept_lab.py`；离线实验解释 Recall、Precision、RR、RRF。
   合成数据及其变体单列概念 suite，不并入正式 Dev/Holdout。
2. Dataset v1：20 Dev + 10 frozen_internal_holdout，沿用 Day 8 预留 ID；题面、事实级 Gold、
   expected_properties、answerability、repository_revision、annotation/dataset version、isolation_group 与来源齐备。
3. 核心 Evaluator 的 should-pass、should-fail、unknown/N/A fixtures；预期裁决与实际执行结果分开。
   现成核心函数可作离线 fixture 校验；找不到 scorer 的条目保持 contract-only/unknown，不补实现。
4. Holdout evidence-level manifest 与创建/访问用途记录；正式冻结前完成数据机械检查和关键标注 Review。

30 条新数据单独位于 `docs/study/datasets/v1/`；不混入固定 12 条的 `benchmarks/cases/`。
校准数据计划位于 `docs/study/calibration/v1/`，与正式任务及教材 suite 分开。
上述目录现已创建；数据状态为 `v1-draft.1 / draft_pending_review`，尚未正式冻结。

## 3. 分工与逐轮教学

AI 完成源码检索、候选题、JSON/YAML、格式、Evidence Pack 和机械核验；学习者不手填模板。
每轮只 Review 一个会影响可信度的 Gold 判断、Evaluator 盲区、隔离边界或架构取舍；同时展示源码。
回答后无论对错均给出 **【正确答案】**、标准表述与差异，再写入本人证据。
AI-authored 内容不算 learner ownership；没有本人回答时不得提前记录通过或冻结 Review。

| 轮次 | 本轮主要判断 | AI 支持材料 |
| --- | --- | --- |
| R1 | 离线 Recall 提高是否足以支持方案改进结论 | 教材函数、固定 Gold 的排序对照与项目观察边界 |
| R2 | 事实级 Gold 的必要条件与 expected_properties 是否足以区分对错 | Dev 候选题、固定 revision 源码、事实定位 |
| R3 | 核心 Evaluator 的反例能否暴露其盲区，unknown/N/A 是否诚实 | 独立 calibration fixtures、已有实现与未知入口表 |
| R4 | 数据组隔离、内部冻结证据等级与可声称范围是否保持合同 | 无题面 manifest、组检查与创建/访问记录 |

按回答调整追问；不连续堆叠判断题，不把整份模板交给学习者填写。

## 4. Holdout 冻结纪律

以下字段已写入 manifest；10 条内容已创建并通过机械检查，冻结状态仍为待 Review，执行数为 0。

```yaml
holdout_evidence_level: frozen_internal_holdout
case_count: 10
used_for_tuning: false
execution_policy: run_once_after_freeze
independent_creator: false
independent_access_control: false
```

Day 9 的内容创建与版本核对属于已授权数据工作；不把 Holdout 内容作为教学调参反例。
Days 10–20 不用 Holdout 修改 Prompt、检索策略、阈值或 Evaluator；Day 20 固定配置，Day 21 运行一次。
不采用复杂加密或 Primary/Reserve；内容用于开发/调参后降级为 `contaminated_internal_check`。
替换只形成新 dataset version，不能恢复旧版本等级。记录 author/reviewer 与访问目的，不声称独立来源。

允许的结论模板（仅完成相应一次运行后才可作为结果声称）：

> 在 10 条预注册、未参与调参的内部冻结用例上，按冻结配置完成一次性验证。

禁止声称严格盲测、独立数据泛化、统计显著性、生产流量效果或未知仓库普遍泛化。

## 5. 禁止与停止线

- 不运行 Legacy/Multi-Agent Dev baseline，不运行 Holdout，不调用 Live Provider。
- 不因新数据修改 Prompt、检索策略、阈值、Evaluator 实现或任何产品源码。
- 不安装依赖；不实现 RAG/Embedding/Vector/Hybrid/Rerank，不安装 Milvus。
  相关实现最早 Day 15 且必须由 Day 14 ADR 触发。
- 不进入 Day 10–15；本日结束必须停下，不自动跨日。
- 每轮展示材料后等待一个本人判断；这属于教学流程，不是重新请求启动或写文件权限。

## 6. 最小恢复清单

- [x] 核对目录、HEAD、干净工作区与 Day 8 完成状态。
- [x] 创建执行卡与 Day 9 证据卡，更新 CURRENT。
- [x] 完成当前 evaluation/benchmark 源码、测试、案例的启动阅读与 Evidence Pack。
- [x] 运行并记录离线概念实验；提交 R1 给学习者。
- [ ] 收到 R1 本人判断，给【正确答案】并记录差异。
- [x] 创建与机械核验 Dataset v1 草案的 20 Dev + 10 Holdout。
- [x] 创建 34 个 calibration fixtures，分开 expected 与 observed/unknown。
- [ ] 完成关键 Review、manifest、版本与 isolation_group 核验后冻结数据。
- [ ] Day 9 收束检查、完成报告与聚焦提交；未到收束不声称完成。

收束时使用项目现有依赖运行必要检查；不把回归测试当 Day 10/11 baseline。
当前下一步：按 [精简审查入口](day-09-review-pack.md) 继续学习者判断，回答后给【正确答案】与标准表述。
源码与复查入口：[Day 9 Evidence Pack](evidence/day-09-source-pack.md)。

## 7. AI 批量准备检查点（2026-09-13）

用户明确要求 AI 先批量完成可独立完成的工作，避免逐轮等待机械制作。
本授权覆盖本日数据、校准输入与预期、manifest、只读核心校验、学习记录和聚焦检查点；不进入产品 PATCH。

- 20 Dev + 10 Holdout；类别配额保持 5/5/4/3/3 与 3/3/2/1/1。
- 34 个不同 Gold 事实、65 处源码引用：revision、symbol、行号与原文一致。
- 7 项 Evaluator、34 个 Fixtures；8 个现成核心调用匹配预期，26 个 observation 为 not_run。
- 30 条正式 Case 的执行数为 0；未调用 Live Provider；未改检索/Prompt/阈值/产品 Evaluator。
- 默认检查仅读 Dev 与 manifest；跨 split 结果为 not_checked。完整作者检查须显式
  `--include-holdout-authoring`，仅当前 Day 9 创建期使用，不在调参期使用。
- 完整回归：777 passed、3 skipped、3 warnings（13.94s）；Ruff lint/format 通过。
- 当前额外内容 digest 不生成；采用版本/文件清单/Git 检查点，不修改 Day 8 合同字段。
- 手算、Gold/Fixture 语义 Review 与最终 Teach-back 未完成，不能据 AI 产物提升 ownership 或宣告 Day 9 完成。

完成报告：[Day 9 AI 准备报告](../reports/day-09-ai-preparation-report.md)。
