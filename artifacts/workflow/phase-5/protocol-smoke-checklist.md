# Phase 5A — 5B 协议与 stdio Smoke 检查清单

Base commit:bc76214。`✅ covered` = 现有测试或本次 smoke 已验证;`⬜ gap` = 尚无直接验证/实现缺口。

| # | 检查项 | 验证方式 | 现状 |
| --- | --- | --- | --- |
| 1 | initialize | JSON-RPC `initialize` 请求/响应 | ✅ test_mcp_server + 本次 smoke |
| 2 | protocol negotiation | protocolVersion 回显(2025-06-18) | ✅ smoke 实测 |
| 3 | capabilities | `capabilities.tools.listChanged=false` | ✅ smoke 实测 |
| 4 | tools/list | 3 工具 + JSON Schema 输出 | ✅ smoke 实测 |
| 5 | tools/call(成功) | read_file 返回结构化结果 | ✅ smoke 实测 |
| 6 | unknown tool | `isError=true` + 文本错误 | ✅ smoke 实测 |
| 7 | invalid arguments | 缺 required/未知字段/类型错误 | ✅ 测试覆盖(test_mcp_adapter/test_mcp_server) |
| 8 | permission denied | 路径越界/根外路径 | ⚠️ 工具层有测试;MCP 层 isError 文本无独立 code |
| 9 | security rejection | 敏感路径(.aws/.ssh 等) | ⚠️ `RepositoryAccessPolicy.is_sensitive_path` 有测试;MCP 无独立 code |
| 10 | timeout | 请求级超时 | ⬜ 当前 stdio server 无请求 timeout(进程级生命周期);缺口 |
| 11 | clean shutdown | EOF → 退出 | ✅ smoke 实测 |

## 5B 执行记录

- 单元/协议测试:`uv run pytest -q tests/test_mcp_adapter.py tests/test_mcp_server.py` → 31 passed。
- stdio smoke:initialize → notifications/initialized → tools/list → tools/call → unknown tool → EOF,全部符合预期(输出见 mcp-tool-inventory.md §2)。

## 建议新增(Phase 5 实现窗口)

1. 参数非法矩阵测试(每个工具:缺 required、未知字段、越界值)断言 MCP 与工具层拒绝一致。
2. 工具错误码映射:在 MCP 错误响应中增加稳定 `code`(如 `TOOL_NOT_FOUND`、`PERMISSION_DENIED`),避免客户端解析文本。
3. 明确 stdio 超时策略(进程级由调用方控制,或 server 增加请求 deadline)——当前无,列为 DEFER/DECISION。
