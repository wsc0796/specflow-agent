# T-086 完成报告 — Trace 一致性（F4）

- 日期：2026-09-26；规格：[T-086](../tasks/T-086-accepted-agent-trace-status.md)。
- 状态：COMPLETE；focused/相关/全量通过，独立审查无新增问题，本地聚焦提交。

已接受stage的trace构造按既有validator/metrics合同将缺省success解释为true。
普通Mock输出标success，已接受degraded结果标degraded；显式success=false仍走失败审计，不改变
Handoff、业务Review或revision语义。仅一行产品逻辑变化，不回写历史trace。

| AC | 状态 | 实际证据 |
| --- | --- | --- |
| AC-001 | PASS | 实际Mock运行：completed+6 schema validated对应6 success spans；degraded与显式失败两例保持正确状态 |
| AC-002 | PASS | t086-green的CLI/失败审计/取消审计/请求预算相关76项通过；最终批次验证见统一报告 |

证据根为本批 `specflow-repair-backups/2026-09-26-integration-audit-T082-T086`。
`t086-red -v tests/test_agent_trace_consistency.py`：2 failed、1 passed，旧普通/降级trace错误地为failed。
`t086-green`：76 passed，真实HTTP=0；原测试未改。回退git revert本项提交，不推送。

最终统一验证：[本批报告](integration-audit-validation-2026-09-26.md)。全量899 passed、3 skipped、
3 warnings，主/子真实HTTP均0；Ruff lint/format与diff通过。独立只读审查无Critical/Important/Minor。
