# T-082 — CLI 显式 LLM 调用预算（F5）

- 日期：2026-09-26；状态：FROZEN / approved-for-execution。
- 授权：integration-audit-handoff-2026-09-26，用户要求修复已复现 F1–F5。
- 基线：09bd60d8a189367c0ac443028e9b4ee3b33139f7；本地 checkout，无 worktree。

## Specification

### REQ-001 — 可配置且严格的调用上限

run CLI 增加 `--max-llm-calls` 正整数参数，仅 Multi-Agent 可用；省略仍使用全局默认10。
不得放松实际请求计数。非法值或 Legacy 显式使用该参数在执行前 exit=2。

### REQ-002 — 完整实时入口与说明

真实 CLI/runner/AgentRunner 配合 FakeProvider：cap=12 正常完成，cap=10 阻止第11次请求。
README 实时示例显式配置12，说明一轮 revision 最多需要15次（其它预算仍可能先停止）。

### AC-001 — 实际请求验收

显式12时 exit=0/12请求；显式10及省略时 exit=3/10请求/CALL_BUDGET_EXCEEDED，manifest计数一致。

### AC-002 — 参数与兼容

0/负数/非整数 exit=2 且未执行；Legacy 显式给参数 exit=2，原Legacy/Mock CLI测试通过。

## Design

REQ-001：argparse 正整数类型、default=None 识别显式传参；Multi-Agent 使用 replace(DEFAULT_POLICY)
创建本次 policy，无持久配置变更。REQ-002：README 只改实时调用预算说明。
允许：src/specflow/cli.py、tests/test_cli_llm_call_budget.py、README.md、本规格和对应报告。
不改 Provider、预算算法、默认额度、旧基准或正式数据。回退为本项提交的 git revert。

## Tasks

- [x] **TASK-001 — RED→GREEN**：REQ-001、REQ-002，AC-001、AC-002；新增真实CLI Fake测试，先RED再最小接线。
- [x] **TASK-002 — 验证与提交**：REQ-001、REQ-002，AC-001、AC-002；CLI/请求预算相关回归与Ruff/diff；
  本项报告与聚焦提交，按用户交接在五项结束后运行一次最终全量并记录统一验证报告。
