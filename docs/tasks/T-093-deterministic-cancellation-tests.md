# T-093 — 取消测试确定性同步

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：用户确认修复本轮审查的七项问题；基点 5a9000a。

## Specification

### REQ-001 — 行为

替换剩余三处 Timer 触发：先确认相关 Future 状态，再触发超时，取消观察全部完成后释放 worker。

### REQ-002 — 边界

仅测试改动；所有 helper 有 finally 释放/join；调度等待时刻可被确定性延迟，仍检查原有取消语义，不放宽断言。

### AC-001 — 主行为

三个旧测试在主线程延迟直到worker完成的旧反例下失败已于审查复现；修复后用取消观察 handshake 验证固定前后关系。

### AC-002 — 边界与回归

相关取消/预算测试及多次独立复跑通过，无 Timer/sleep 作为释放机制，产品代码不变。

## Design

REQ-001、REQ-002：共用小型测试上下文管理 helper：controlled as_completed 驱动零timeout；_abort_agent 在所有状态观察后发 Event；finally cleanup。不改变 scheduler。
允许：tests/test_scheduler_cancellation_audit.py、本规格及报告。
禁止：真实 Provider、正式 Dev/Holdout、历史 baseline/raw/学习材料、依赖、权限扩张、全局预算提升、推送。
验证使用净化 Provider 环境且阻断主/子进程 HTTP 的已有包装；临时合成数据独立目录。
回退使用本项聚焦提交的 git revert；不重写旧 Artifact 或历史报告。

## Tasks

- [x] **TASK-001 — 行为回归与实现**：REQ-001、REQ-002；覆盖 AC-001、AC-002，先确认 RED 再修复 GREEN。
- [x] **TASK-002 — 验证与交付**：REQ-001、REQ-002；AC-001、AC-002 相关测试、Ruff/diff、报告与本地提交；最终全量及独立审查统一收口。
