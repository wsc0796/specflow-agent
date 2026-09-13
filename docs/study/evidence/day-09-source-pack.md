# Day 9 源码与离线 Evidence Pack

- 日期：2026-09-13；项目基线：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- 状态：`AI-prepared / learner-unverified`；执行卡：[Day 9](../day-09-execution-card.md)。
- 已读启动清单：AGENTS、SPEC-BASELINE、ROADMAP V5.3.2、CURRENT、Day 8 执行卡、
  Eval/Evaluator Contract v1、Day 8 evidence/source pack、下列源码/测试、12 条 benchmark JSON、
  指定的只读教材与 `offline_concept_lab.py`。
- `git diff 5f2815d 08e5a66 -- src tests benchmarks` 无输出；Day 8 合同源码基线到当前 HEAD 的相关实现无差异。
- 启动阶段测试文件只读，唯一运行是教材标准库函数及离线数值断言；后续批量准备结果另见文末。

## 1. 当前实现盘点

路径相对项目根；现有测试的存在不等于今天已运行。

| 对象 | 源码事实 | 测试与用途 |
| --- | --- | --- |
| 历史 benchmark | `src/specflow/evaluation/benchmark.py:41` 加载固定 12 条、3 类各 4 条；`:75` 调用 mock Multi-Agent | `tests/test_benchmark.py:18` 数量分布，`:98` 报告及既有 baseline 比对；本日不运行 |
| 旧 EvaluationCase | `src/specflow/evaluation/models.py:29` 无事实级 Gold/split/version；`runner.py:20` 只加载 JSON，`:51` 检查预期文件磁盘存在 | `tests/test_evaluation.py:55` 固定 3 条历史任务，`:93` 缺文件检查；不兼容新数据协议 |
| contract_run_success | `benchmark.py:164` 检查七个文件，解析 manifest/metrics，`:188` 起检查完成态和 0/6 Schema 计数 | 已有核心；公共四态 wrapper unknown；内容偏题但结构通过的校准 fixture 待建 |
| source_reference_validity | `validators.py:200` 来源候选并集、非空、相对路径、仓库包含关系、存在性 | `tests/test_live_validation_import.py:60` 手工 fixture 导入，`:77` 起异常；语义支持不在 helper 中 |
| token_cost_completeness | `benchmark.py:219` passed-only；`:258` 缺失/非法回退 0；`metrics.py:51` 默认 0 | 完整性 evaluator 为 contract-only/unknown；不修改现有实现 |
| fact_evidence_coverage / citation_support | `metrics.py:61` 仅文件计数；`validators.py:200` 不消费 Gold/claim 语义 | 自动 scorer unknown；独立 fixtures 保存预期映射，不冒充已实现评分器 |
| task_success | `rubric.py:15` 人工维度；`models.py:73` 分数范围；`multi_agent_runner.py:56` mock A/B 只给 artifact 分 | `tests/test_evaluation_multi_agent.py:81` 同输入 A/B 测试；完整 task scorer unknown |
| safe_abstention | Day 8 导航绑定 `runner_multi.py:130` 零摘录停止及 `tests/test_cli_multi_agent.py:76` | 本次未重跑；完整语义 evaluator unknown；不把工程零摘录等同真实无答案 |
| Evidence 观察面 | `evidence/collector.py:89` 文件选择，`:109` 从匹配结果生成摘录，`:120` 按字符预算保留摘录；`evidence/models.py:117` 序列化 | `tests/test_evidence_collector.py:143` 有字符上限断言；不是事实覆盖评分 |

`evaluation/report.py` 仅序列化现有报告/状态/finding；Day 9 不扩展 reporter。
12 条历史案例均来自 portfolio fixture：authentication/order/catalog/cache、变更规划、风险审查。
它们不自动转成新 20/10 数据，不把教材或 Behavior suite 拼进总通过率。

## 2. 教材函数与实际离线结果

只读教材目录：
`C:\Users\50469\python-learning\AI-Agent\22-llm-system-course-handbook\02-实验手册`。
脚本仅 import argparse/json/math，无文件写入或网络调用；本次以项目已有 Python、`-B` 和 runpy 加载。
结果：[day-09-offline-results.json](day-09-offline-results.json)，suite=`day09_offline_concepts_only`。
作者/操作者为 AI，learner_prediction=null，不计作学习者亲手实验。

`offline_concept_lab.py:50` 的 `retrieval_metrics`，如下按原顺序摘取非连续行：

```python
    top = ranking[:k]
    hits = len(set(top) & relevant)
    rr = next((1 / i for i, doc in enumerate(top, 1) if doc in relevant), 0.0)
        "recall": hits / len(relevant) if relevant else None,
        "precision_returned": hits / len(top) if top else None,
```

本脚本要求 ranking 去重；Recall 分母为 Gold 数，Precision 分母为实际返回数。
RR@K 是 Top-K 中首个相关项名次的倒数，有非空 Gold 但无命中时为 0。

| 固定 Gold={d1,d3}，排序=[d1,d2,d4,d3] | 实际返回数 | hits | Recall | Precision_returned | RR@K |
| --- | --- | --- | --- | --- | --- |
| K=1 | 1 | 1 | 0.5 | 1.0 | 1.0 |
| K=3 | 3 | 1 | 0.5 | 1/3 | 1.0 |
| K=4 | 4 | 2 | 1.0 | 0.5 | 1.0 |

固定 K=3，排序 `[d1,d2,d3]` 与 `[d2,d1,d3]` 的 Recall 均为 1、Precision 均为 2/3，
RR 分别为 1 与 0.5。这些是给定相关标签后的数学结果，不是对真实语义相关性的判断。

`offline_concept_lab.py:38` 的 `rrf` 在 `:46` 按各榜名次累加：

```python
            scores[document] = scores.get(document, 0.0) + 1 / (constant + rank)
```

RRF 是排序融合规则，输入没有 Gold。常数 60 与返回条数 K 不同。
两路 `[d1,d2,d3]` / `[d3,d2,d4]` 的实际融合结果为 `d3 → d2 → d1 → d4`；
d3=1/63+1/61≈0.03226646，d2=2/62≈0.03225806。该结果不表示 SpecFlow 已实现 RRF。

教材基例 `[d2,d1,d4]`、Gold={d1,d3}、K=3 实测为 Recall=0.5、Precision=1/3、RR=0.5。
空 Gold 的实际结果是 Recall/RR=null，但非空返回列表的 Precision=0.0。
教材“空金标返回 null”的文字不能外推成所有字段都为 null；这个 0 也不能区分标注缺失与无答案。
项目沿用冻结的 answerability 和 unknown/N/A 合同，不直接套用此合成函数充当正式 scorer。

## 3. 复查命令

从唯一项目目录运行；使用已安装 Python，不同步依赖，不写教材目录：

```powershell
& .\.venv\Scripts\python.exe -B "C:\Users\50469\python-learning\AI-Agent\22-llm-system-course-handbook\02-实验手册\offline_concept_lab.py" retrieval
```

K 对照可按下列只打印命令复现；本次结果 JSON 由同样函数调用另行写入项目证据目录：

```powershell
@'
import json, runpy
lab = runpy.run_path(r'C:\Users\50469\python-learning\AI-Agent\22-llm-system-course-handbook\02-实验手册\offline_concept_lab.py')
for k in (1, 3, 4):
    print(json.dumps(lab['retrieval_metrics'](['d1','d2','d4','d3'], {'d1','d3'}, k)))
'@ | & .\.venv\Scripts\python.exe -B -
```

本次离线调用退出码 0，基例数值、RRF 完整顺序、K=1/4 数值及空 Gold Recall 的断言通过。
不包括产品测试、Legacy/Multi-Agent baseline、Holdout 或 Live Provider。

## 4. 恢复边界

启动阅读已完成；下一步等待 R1 本人 Review，然后给【正确答案】与标准表述。
以上是启动阶段恢复点。用户随后授权 AI 先完成机械工作，Dataset 与 calibration 草案现已创建；
统一入口为 [Day 9 审查包](../day-09-review-pack.md)，核验见
[AI 准备报告](../../reports/day-09-ai-preparation-report.md)。学习者 Review 与正式冻结仍待完成。
