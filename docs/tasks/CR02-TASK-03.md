# CR02 TASK-03：规则适用与外部核验

日期：2026-10-30。状态：本任务工程范围已完成；基线提交 3803f5a，范围保持 A/A/B/A/A。
沿 v0.2.2 C§4/7.1—7.4/8.6/9、D TASK-03 和 AC-11/17/23 实施。

本轮完成：规则精确作用域及差集三值校验、历史/排除原因；外部核验 POST、列表、
详情；严格导入 Schema、成功幂等优先、归属/版本/当前目标/源码基线的错误顺序；
新输入显式采用并重核逐目标适用性；报告引用与实际请求证据相连。

允许改动：contract_review 内相关 schemas/inputs/store/service/api/protocol/
report_validation/worker/execution，新增 verification 模块及对应 tests/contract_review 测试。
仅为新表增加 v2 迁移，保留已提交 v1 checksum 和数据。

验收：弱证 201 保存但不声称系统验证；重复成功请求返回原响应；错误导入零写入；
当前采用不修改原归属；同 commit 错目标不适用、缺维度/规则变化保留未知；
报告逐目标核对而非使用汇总布尔值；旧报告/NOT_RUN 不变；新增迁移可重入、可回退读取。
复用已有覆盖集合/quality 测试，不重复建设测试体系。

动态工具与真实 Provider 接入留在 TASK-04，人工答案及公开 revisions 留在 TASK-05。
本轮仅扩展现有内部 enqueue_revision 接点以冻结外部证据采用；不增加项目长期记忆、
写入执行、委派或回放。完成后运行规定离线检查并做一个本地聚焦提交，不推送。

结果：本模块 112 passed；全量 1224 passed / 3 skipped，Ruff 全部通过。
详情见 `docs/reports/CR02-TASK-03-completion.md`。真实模型语义验收仍未运行。
