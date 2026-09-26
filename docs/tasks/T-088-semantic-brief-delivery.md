# T-088 — 语义任务说明交付

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：用户确认修复本轮审查的七项问题；基点 5a9000a。

## Specification

### REQ-001 — 行为

每个实际 Agent 请求包含其自身 task_brief 的 task_description/analysis_focus/evaluation_hints/repository_scope_hint，包括修订重执行。

### REQ-002 — 边界

brief 是有界任务数据，不改变权限/依赖或输出 Schema；通过最终 DLP 和现有整请求预算，不发送其它角色 brief 或 provenance。

### AC-001 — 主行为

完整 FakeProvider 链路的六角色每个仅收到自身四个语义字段；degraded brief 可用，修订同样保留目标 brief。

### AC-002 — 边界与回归

大 brief 在 Agent 调用前拒绝；DLP 和原 receiver isolation、请求预算回归通过。

## Design

REQ-001、REQ-002：构造 AgentRunner 时显式注入接收者的 task_brief 数据字典，适配器以 JSON 块交付。保留不提供 brief 的独立适配器默认行为。
允许：src/specflow/runner_multi.py、src/specflow/agents/adapter.py、tests/test_semantic_brief_delivery.py、本规格及报告。
禁止：真实 Provider、正式 Dev/Holdout、历史 baseline/raw/学习材料、依赖、权限扩张、全局预算提升、推送。
验证使用净化 Provider 环境且阻断主/子进程 HTTP 的已有包装；临时合成数据独立目录。
回退使用本项聚焦提交的 git revert；不重写旧 Artifact 或历史报告。

## Tasks

- [x] **TASK-001 — 行为回归与实现**：REQ-001、REQ-002；覆盖 AC-001、AC-002，先确认 RED 再修复 GREEN。
- [x] **TASK-002 — 验证与交付**：REQ-001、REQ-002；AC-001、AC-002 相关测试、Ruff/diff、报告与本地提交；最终全量及独立审查统一收口。
