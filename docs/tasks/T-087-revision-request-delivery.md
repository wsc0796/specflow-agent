# T-087 — 修订请求交付

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：用户确认修复本轮审查的七项问题；基点 5a9000a。

## Specification

### REQ-001 — 行为

REJECT 后只向批准的目标 Agent 发送本轮修订指令、完整已接受 Review 输出和该目标上一次已接受输出；原始角色输入仍隔离。

### REQ-002 — 边界

补充修订上下文纳入同一输入预算和 DLP；超过预算在请求前停止，保持最多一次修订、原 Handoff 校验和下游重新综合评审。

### AC-001 — 主行为

FakeProvider 真实请求覆盖三个可修订角色；首轮无修订块，二轮有 feedback/old output/instruction，其他角色不收到。

### AC-002 — 边界与回归

大 Review 使修订请求前 TOKEN_BUDGET_EXCEEDED，已接受四阶段保留；PASS 路径和现有 revision 回归通过。

## Design

REQ-001、REQ-002：runner 在 Handoff 验证后投影 revision_context（instruction/review_output/previous_output），adapter 序列化为独立 JSON 数据块后执行既有 token 准入。该补充执行上下文不改变正常业务 Schema。
允许：src/specflow/runner_multi.py、src/specflow/agents/adapter.py、tests/test_revision_request_delivery.py、本规格及报告。
禁止：真实 Provider、正式 Dev/Holdout、历史 baseline/raw/学习材料、依赖、权限扩张、全局预算提升、推送。
验证使用净化 Provider 环境且阻断主/子进程 HTTP 的已有包装；临时合成数据独立目录。
回退使用本项聚焦提交的 git revert；不重写旧 Artifact 或历史报告。

## Tasks

- [x] **TASK-001 — 行为回归与实现**：REQ-001、REQ-002；覆盖 AC-001、AC-002，先确认 RED 再修复 GREEN。
- [x] **TASK-002 — 验证与交付**：REQ-001、REQ-002；AC-001、AC-002 相关测试、Ruff/diff、报告与本地提交；最终全量及独立审查统一收口。
