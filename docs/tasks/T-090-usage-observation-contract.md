# T-090 — 全调用计量观测契约

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：用户确认修复本轮审查的七项问题；基点 5a9000a。

## Specification

### REQ-001 — 行为

新 Artifact 显式声明 all_provider_requests_v1 用量契约；评估器据此将 Coordinator+Agent 计入全调用，不再假报 Coordinator 未计量。

### REQ-002 — 边界

无契约旧 Artifact 保留原解释；完整性来自有效 usage_complete、非负整数计数和用量一致性，缺失/矛盾/未知契约不声称全计量；不改历史报告。

### AC-001 — 主行为

新实际 Mock/FakeProvider 产物可得到完整 coverage/total；旧 Artifact 仍明确 subtotal/unknown。

### AC-002 — 边界与回归

用量完整性缺失、false、计数/总量矛盾、非法类型、未知契约安全降为unknown；混合汇总正确。

## Design

REQ-001、REQ-002：runner manifest 增加版本化 usage_contract。inspect_attempt 按契约及 budget_usage 与 metrics 校验解释，summary 根据实际观测说明原因。
允许：src/specflow/runner_multi.py、src/specflow/evaluation/dev_baseline.py、tests/test_usage_observation_contract.py、本规格及报告。
禁止：真实 Provider、正式 Dev/Holdout、历史 baseline/raw/学习材料、依赖、权限扩张、全局预算提升、推送。
验证使用净化 Provider 环境且阻断主/子进程 HTTP 的已有包装；临时合成数据独立目录。
回退使用本项聚焦提交的 git revert；不重写旧 Artifact 或历史报告。

## Tasks

- [x] **TASK-001 — 行为回归与实现**：REQ-001、REQ-002；覆盖 AC-001、AC-002，先确认 RED 再修复 GREEN。
- [x] **TASK-002 — 验证与交付**：REQ-001、REQ-002；AC-001、AC-002 相关测试、Ruff/diff、报告与本地提交；最终全量及独立审查统一收口。
