# CR02 TASK-01：六例早期业务切片

日期：2026-10-30。前置 TASK-00 已核定；采用已选 A/A/B/A/A。
本次只冻结原计划的 F01/F02/C01/C03/H01/H02 早期切片，供 TASK-02—05 使用。
其余 COMMON 案例继续登记为 later_common；R03/R05 按未选项目记忆排除。
允许改动：benchmarks/contract_review 的新材料/manifest/oracle/答案脚本，
tests/contract_review/test_public_fixtures.py 及最小任务/报告。
不执行被查代码、不导入旧评测、不运行真实模型，不由输出反推 oracle。
完成条件：材料可解析且路径闭合、H01/H02 初始业务材料完全相同而答案不同，
固定 case/trial/sample 身份与六例集合正确；oracle/答案脚本与业务 sources 分离。
通过材料检查不改变任何语义 AC 的 NOT_RUN。
