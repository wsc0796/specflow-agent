# Evaluator calibration v1

34 个独立合成 Fixtures，覆盖冻结合同的七项 Evaluator；没有取用教材或正式 30 条任务的题面/Gold。
数据与完整预期在 [fixtures.json](fixtures.json)，便于先预测的输入展示在 [审查包](fixture-review.md)。

| Evaluator | 数量 | 当前可执行内容 |
| --- | --- | --- |
| contract_run_success | 6 | 4 个现有核心 helper 调用；unknown/N/A 的公共 wrapper 未实现 |
| source_reference_validity | 6 | 4 个现有路径 helper 调用；unknown/N/A 的公共 wrapper 未实现 |
| fact_evidence_coverage | 4 | 预期事实映射与数值；scorer unknown |
| citation_support | 4 | 预期语义裁决；scorer unknown |
| task_success | 3 | 预期属性裁决；统一 scorer unknown |
| token_cost_completeness | 6 | 完整、零调用、遗漏、未知清单、零尝试的预期数据；scorer unknown |
| safe_abstention | 5 | 预期语义/轨迹裁决；完整 evaluator unknown |

八次实际核心调用结果见 [calibration results](../../evidence/day-09-calibration-results.json)。
其余 26 个 observation 明确为 `not_run`。fixture 文件保存预期，观察记录独立存放，不覆盖成伪执行结果。
Fixture 文件完整与核心函数匹配，不等于人工语义校准已经完成；human_review_status 保持 pending。

`fixture_role=should_pass/should_fail` 表示校准正反例。Fact Recall 的两类 fixture 输出具体比例
而非产品任务 verdict；`expected.verdict=null`、`product_task_verdict=unknown` 明确保留阈值缺口。
缺少输入时 unknown，不适用时 N/A，不把它们填成 0 或满分。

`check_day09.py --execute-existing-core` 只调用现有 `_read_run` 与 `_validate_sources`，
在项目 data 目录下用临时最小文件集完成检查；不运行 Agent、不导入正式 Case 作为任务执行、
不调用 Provider、不新增语义评分器。unknown/N/A wrapper 的预期不能冒充现有 helper 已支持。
