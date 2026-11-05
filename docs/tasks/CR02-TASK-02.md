# CR02 TASK-02：持久受理与证据纵向链

日期：2026-10-30。状态：受控执行纵向切片已交付，完整产品验收尚未关闭。
前置：TASK-00 完成、TASK-01 六例切片就绪。
沿 v0.2.2 C§3/5/6.5—6.6/8—11 及已选 A/A/B/A/A，不增加条件功能。

允许修改 `src/specflow/contract_review/`、`main.py` 的新资源接线、
`tests/contract_review/` 和本任务报告。旧 Provider、Run API、学习和评测资产不改。
依次实现：严格输入和密封 Git 来源、新表版本迁移、短事务/幂等受理、
OS 实例锁/单 worker、累计账/派发意图/实际请求/结果、测试 adapter 的正式报告链。
TASK-03 的完整报告语义结构和 TASK-04 的动态模型循环依后续原任务落实；
本任务若只完成受理切片，必须明示 PARTIAL，不能标完整 TASK-02 或 AC 通过。

主要反例：同 key 重放/冲突、准备失败零半成记录、活跃 job 唯一、
存储失败零外部派发、超时未收尾保持槽、重复维护不释放新槽、
current_report 属于 current_input、跨资源引用拒绝、旧八路由兼容。
所有测试使用临时 repo/DB 与 test adapter；无真实模型授权。

本轮记录：`docs/reports/CR02-TASK-02-progress.md`。
全量离线测试 1169 passed / 3 skipped；全库 Ruff 通过。
后续沿既定 TASK-03—05 补完整规则/核验、动态工具和人工答案闭环；
不能把本轮受控模型替身结果标为真实业务语义通过。
