# Day 9 — 只审会改变结论的判断

- 日期：2026-09-13 至 2026-09-14；状态：`REVIEW_COMPLETE / DATASET V1 FROZEN`。
- 数据版本：`v1`；本人能力按证据保持 improving/partial。
- 用户明确要求 AI 先批量完成机械工作；不再让逐轮课堂等待阻塞候选数据与格式检查。

## 已准备

| 产物 | 结果 | 审查入口 |
| --- | --- | --- |
| Dataset v1 草案 | 20 Dev + 10 内部 Holdout，配额一致；34 个不同事实、65 处源码定位 | [Dev 审查包](datasets/v1/dev-review.md) |
| 三个锚点 | D001 精确关键词、D006 语义改写、D015 无答案；都属于原 20 Dev | [anchors](datasets/v1/anchors.json) |
| Evaluator Fixtures | 七项、34 个；8 个已有核心匹配，26 个只保存预期 | [Fixture 输入审查包](calibration/v1/fixture-review.md) |
| Holdout manifest | 等级、数量、ID、版本、执行纪律与访问记录；执行数 0 | [只审 manifest](datasets/v1/holdout-manifest.json) |
| 机械核验 | 原文/revision、ID、分类、组、Gold 引用与输入允许字段 | [结果](evidence/day-09-data-validation.json) |

## 留给学习者的四个判断面

1. Gold：Dev 中的条件、否定与源码事实是否足以区分正确/错误答案；从三个锚点开始，
   不需改写 JSON。AI 已把全部 20 条的题面和原文集中放好。
2. 可回答性：限定来源缺失与整个系统没有能力是否被混同；安全拒绝是否与普通无答案区分。
3. Evaluator：优先判断条件被删、attempted 清单缺失、合法失败这三个反例；先看输入再作判断。
   事实覆盖值不是任务通过线，路径 helper 通过不是语义支持。
4. 隔离/证据等级：同组放在同 split；不同来源职责造成的难度差异仍需注意。
   只审 Holdout manifest；不拿 Holdout 内容教学或调参，不声称独立盲测。

分类同步（2026-09-14）：D018-D020 与 H010 均为安全边界。AI 已把 manifest 显式修订为
`safety_case_count=4/covered`、`stale_index_case_count=0/not_covered`；当前没有索引运行时，
stale-index runtime capability 为 `N/A`。
学习者尚未亲自提交该分类判断，因此本项不计 learner ownership。

侧对话恢复（2026-09-14）：离线指标、三个 Gold 锚点、answerability、Fact Recall、
Token Completeness、Source/Citation、Safe Abstention、Holdout 边界和污染语义均已完成教学。
当前只从结构合同与任务语义的双判定 Fixture 继续，不重做前述内容。

每轮只处理一个主要判断。回答后无论对错，AI 都给【正确答案】、标准表述和差异，
再记录本人证据。以上四项是恢复导航，不是要求一次提交四份作业。

## 第一块教学的恢复

前一轮的已展示算例只算 AI 演示。学习者尚未提交手算/预测，不能登记为过关。
重新开始时用未展示答案的合成输入：Gold={x2,x4}，ranking=[x3,x2,x1,x4]，K=3；
先手算 Recall/Precision/RR，再改变相关项次序，最后做一次 RRF 手算。
这些新符号和变体仍属于教材概念 suite，不进入 Dataset 或 calibration。

## 通过机械检查仍保留的 unknown

- 新 Dataset 到旧 runner 的输入投影/加载接线未实现。
- 自动事实评分、语义 Citation、完整 Token ledger/scorer 与通用 task verdict 未实现。
- Repository Task 的产品终态映射须绑定未来实际 topology/profile；不能复用题目描述的函数终态。
- 当前没有旧索引拒绝实现证据；安全配额没有被包装成已实现 RAG。

本包已完成关键边界 Review。逐题 AI 内容不计学习者 ownership；最终证据见
[Day 9 证据卡](evidence/day-09.md)。
