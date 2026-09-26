# T-084 完成报告 — 证据来源一致性（F2）

- 日期：2026-09-26；规格：[T-084](../tasks/T-084-evidence-snapshot-consistency.md)。
- 状态：本项实现与相关验证完成；五项最终全量记录于本轮统一验证报告。

Search match 现在携带该次完整有界脱敏读取的hash，沿用ReadFileTool的内容及换行定义。
Collector 对所选路径的全部match hash和后续read hash做一致性检查；变化或缺失时丢弃该路径的
全部摘录和来源绑定，标记truncated并返回warning。没有额外read/retry，没有改排名或搜索词。

| AC | 状态 | 实际证据 |
| --- | --- | --- |
| AC-001 | PASS | read前修改和第二次search前修改两例均无旧excerpt/新hash错配，有warning；唯一冲突路径被剔除后runner在规划前exit3/EVIDENCE_NOT_FOUND |
| AC-002 | PASS | LF/CRLF正常快照hash一致且不等于单摘录hash；脱敏/截断、缺失版本反例通过 |

本批证据根 `specflow-repair-backups/2026-09-26-integration-audit-T082-T086`。
`validate.py t084-red -v tests/test_evidence_snapshot_consistency.py`：6 failed；旧实现保留冲突摘录且search无hash。
`t084-green` 包含新测试、test_evidence_collector、test_repository_tools、test_cli_multi_agent、test_cli：
93 passed、1个既有Windows symlink skip。增加唯一冲突来源的runner验收后，`t084-boundary` 为7 passed。
所有真实 HTTP=0；Ruff/format/diff和规格追溯通过，旧测试未改。

source_hash 是完整脱敏的“已读取内容”身份；文件截断时只覆盖已读前缀，不能据此声称已验证未读取尾部
或原始含敏感内容的全文件。不是跨文件事务快照；文件在采集完成后还可变化。丢弃版本冲突路径的策略
可能减少可用证据，warnings明确说明，不重试或混用版本。旧基准、Gold与正式数据原样保留。
回退 `git revert <引入本报告的提交>`；不推送。
