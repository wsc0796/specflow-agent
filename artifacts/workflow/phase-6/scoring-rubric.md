# Phase 6A — 6G 评分规则定义(草案)

分数统一采用现有 `EvaluationScore` 语义:0/1/2。

| 指标 | 定义(2=完全满足,1=部分,0=不满足) | 来源 |
| --- | --- | --- |
| schema_valid | 产物通过严格输出 Schema 校验 | 自动化 |
| evidence_ref_valid | evidence 引用指向 evidence-index 中存在的条目 | 自动化 |
| referenced_path_exists | 引用的文件路径在 fixture 仓库中真实存在 | 自动化 |
| claim_evidence_coverage | 有证据支持的 claim 数 / claim 总数 | 自动化 |
| unsupported_claim_rate | 无证据 claim 数 / claim 总数(反向) | 自动化 |
| expected_module_recall | expected_file_patterns 中被正确引用的比例 | 自动化 |
| test_plan_coverage | expected_acceptance_topics 出现在测试计划的比例 | 自动化 |
| risk_coverage | expected_risks 被识别并给出应对的比例 | 自动化(结合人工复核) |
| uncertainty_calibration | 模糊/不确定处是否显式声明不确定性(不谎报确定) | 人工 |
| budget_violation | 是否触发任何预算失败(触发=0,否则=2) | 自动化 |
| run_success | run 状态 completed 且 manifest 一致 | 自动化 |

## 与既有 Rubric 的关系

- 人工盲评继续复用 `evaluation/rubric.RUBRIC_DIMENSIONS`(10 维)与 `multi_agent_runner.AB_DIMENSIONS`(10 维),6G 自动指标与它们并列、不合并混算。
- Pilot 阶段只做:指标可计算性验证、分布稳定性;不产出"六角色优于 X"的结论。
