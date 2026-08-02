# Phase 5A Unresolved Issues

1. **DECISION_REQUIRED — MCP Schema 单一来源方案**:方案 A(推荐)/ B / C,见 single-source-plan.md;由 Phase 5 实现窗口决定。
2. **DECISION_REQUIRED — 类型检查**:是否引入 mypy(核心模块 strict),见 typecheck-scope.md。
3. **缺口 — 工具错误码**:MCP 层工具失败只有文本无机器可读 code(TOOL_NOT_FOUND / PERMISSION_DENIED 等),建议 5B 实现窗口补充。
4. **缺口 — stdio timeout**:server 无请求级超时,需明确进程级或请求级策略。
5. **缺口 — LICENSE**:仓库根无 LICENSE,需用户决定许可协议(发布阻断项)。
6. **缺口 — MCP guide / Known limitations / CI badges**:README 与 docs 待补(5D 清单)。
