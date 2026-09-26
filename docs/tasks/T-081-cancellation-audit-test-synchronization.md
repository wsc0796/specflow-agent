# T-081 — Cancellation audit integration-test synchronization

- 日期：2026-09-26；状态：FROZEN / approved-for-execution；模式：BUGFIX。
- 授权：用户复现 T-080 Stage1 集成测试时序问题，明确要求主窗口补稳；只修测试同步。
- 基线：`1aa5682f3e4e233c330e62b0bc0982531c628488`；分支：`codex/t081-cancellation-test-sync`。

## Specification

T-080 的 Stage1 集成测试用 `stage_one_started.is_set()` 判断 worker 状态；主线程可能先到达该点，
不安排释放 worker，最终令运行因 executor 等待失败而成为 `MULTI_AGENT_RUN_FAILED`，而非预期的
deadline audit。生产 scheduler 实现不改。

### REQ-001 — 确定性 Stage1 触发

测试必须区分 Stage1 已提交和 design worker 已启动，且在二者都确认后才让受控 `as_completed`
触发 TimeoutError。不得用 `is_set()` 轮询、短 deadline 或 sleep 推断线程状态。

### REQ-002 — 确定性收口

测试须观察 scheduler 已对三个 Stage1 Future 调用取消处理后再释放 design worker；任意断言失败时
`finally` 仍释放并 join helper，避免 pytest 残留或悬挂线程。测试继续调用真实 ThreadPoolExecutor、
真实 deadline abort、真实 shutdown 和 Artifact 持久化链。

### REQ-003 — 范围与验证

只改 `tests/test_scheduler_cancellation_audit.py`，新增本规格与报告。不得修改 scheduler、runner、
T-080 产品合同、默认并发、预算、Provider 或现有测试语义。focused 测试重复运行，相关回归、
完整 pytest、Ruff/diff 通过；不推送。

### AC-001 — 已启动后才超时

受控运行证明 Stage1 submitted 和 design started 都已发生，才触发 timeout；结果稳定为
`TIME_BUDGET_EXCEEDED` 且有 scheduler_abort。

### AC-002 — 取消观察后才释放

三个 Stage1 Future 都已经过取消观察后才释放运行 worker；queued sentinel 不执行；finally 可以安全
收口。Artifact 保持 Stage1、Stage0 accepted output 与敏感 marker 不持久化断言。

### AC-003 — 无回归

T-080 focused/相关/全量与静态检查通过，原 dirty 学习材料不变，本地聚焦提交可 revert。

## Tasks

- [x] **TASK-001 — deterministic regression**：REQ-001、REQ-002、AC-001、AC-002；以 Events 和
  abort observer 替换 Stage1 轮询/Timer，先复查原不稳定触发，再运行 focused。
- [x] **TASK-002 — closeout**：REQ-003、AC-003；重复 focused、相关与全量验证，写报告、精确暂存、
  本地提交；不推送。
