# T-081 完成报告 — Cancellation audit test synchronization

- 日期：2026-09-26；状态：COMPLETE；验证通过，等待本地聚焦提交。
- 规格：[T-081](../tasks/T-081-cancellation-audit-test-synchronization.md)。
- 基线：`1aa5682f3e4e233c330e62b0bc0982531c628488`。

## 问题与修复

用户复现表明 T-080 Stage1 测试可能先检查 `stage_one_started.is_set()`，再走到正常等待路径；这时
没有释放 design worker 的机制，测试超时表现为 `MULTI_AGENT_RUN_FAILED`，即测试未能稳定触达真正的
scheduler deadline/cancel/shutdown 链。该问题是测试编排，不是生产取消逻辑的已知缺陷。

本修复将使用独立事件确认 Stage1 已提交与 design worker 已启动；受控 `as_completed` 仅在两者完成后
注入 TimeoutError。测试包装 scheduler 的 `_abort_agent`，第三个 Stage1 Future 完成取消观察时才释放
design worker；finally 无条件释放并 join helper。生产源码不改。

## 验证记录

| 标签 | 结果 |
| --- | --- |
| sync-focused | 1 passed；新控制顺序通过 |
| sync-stability-1…20 | 同一场景独立运行 20 次，0 failures |
| sync-related | 139 passed、1 skipped、1 warning；主/子 HTTP=0 |
| sync-full | 866 passed、3 skipped、3 warnings，98.84s；主/子 HTTP=0 |

Ruff lint/format 与 `git diff --check` 通过。所有运行沿用隔离包装：清除
`SPECFLOW_LLM_*`，主/子 HTTP 哨兵为 0；不读取正式 Dev/Holdout 或凭证。

| AC | 状态 | 证据 |
| --- | --- | --- |
| AC-001 | PASS | Stage1 submitted→design started→受控 TimeoutError，20 次稳定运行 |
| AC-002 | PASS | 三个 `_abort_agent` 观察完成才释放 design；queued sentinel=0，finally 释放/join |
| AC-003 | PASS | sync-full、Ruff/diff 通过；原 17 个 dirty 学习材料逐字节未变，精确暂存待提交 |

最终全量后的 3 个 skip 均为既有 Windows symlink 权限限制；3 个 warning 为既有
TestStrategy 收集与 Starlette/httpx 弃用提示。未新增 skip/xfail。测试同步以外没有产品代码改动；
回退用 `git revert <引入本报告的提交>`，不推送、不发布。
