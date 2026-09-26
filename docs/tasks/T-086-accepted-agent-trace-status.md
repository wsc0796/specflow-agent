# T-086 — 已接受 Agent Trace 状态一致性（F4）

- 日期：2026-09-26；状态：FROZEN / approved-for-execution；授权：本批交接F4。

## Specification

### REQ-001 — 与现有接受合同一致

已通过stage身份/Schema/业务门的确定性Mock envelope缺省success按true解释，与validator/metrics一致。
显式success=false继续失败，degraded=true在已接受成功结果中标degraded，不改Review/revision合同。

### AC-001 — 实际Artifact一致性

正常Mock完整run exit0/completed、6个schema validated时，6个Agent trace均success；
已接受degraded结果trace为degraded，显式失败结果仍failed/exit3，完成数保持0。

### AC-002 — 回归

T078失败span、T080取消审计、请求预算、成功/Handoff/revision相关回归通过；五项完成后统一全量、
Ruff/diff与本地聚焦提交，无真实HTTP或正式数据访问。

## Design

REQ-001：只把trace builder的 result.get("success", False) 改为既有true缺省，不修改validator与Schema。
允许：src/specflow/runner_multi.py、tests/test_agent_trace_consistency.py、本规格/报告；最终附本批
统一验证报告。旧trace不回写，不新增统一状态系统。回退git revert本项提交。

## Tasks

- [x] **TASK-001 — RED→GREEN**：REQ-001，AC-001；真实run/manifest/metrics/traces正反例。
- [x] **TASK-002 — 收口**：REQ-001，AC-002；受影响回归、五项全量、独立只读审查和逐路径本地提交。
