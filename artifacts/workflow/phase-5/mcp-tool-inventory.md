# Phase 5A — MCP Schema 单一来源只读盘点

窗口:phase5a(由 phase_4a_live_prep 窗口代为执行)· 分支:fix/phase-5a-mcp-inventory · Base commit:bc76214

## 1. 盘点表

| 维度 | Tool 层(内部) | MCP 层 | 一致性 |
| --- | --- | --- | --- |
| 工具名 | `ToolMetadata.name`(`tools/repository_tools.py`、`tools/registry.py`) | `McpToolCatalog` 直接遍历 `registry.metadata()` | ✅ 单一来源 |
| 工具描述 | `ToolMetadata.description` | 直接取自 metadata | ✅ 单一来源 |
| 参数 Schema | 校验逻辑内联在 `repository_tools.py`(`_reject_unknown_arguments`、`_bounded_int` 等)+ `repository_policy.py` 限制 | `mcp/adapter.py::_INPUT_SCHEMAS` 手工维护的 JSON Schema 副本 | ⚠️ **重复维护,漂移风险**;当前由测试锁定一致,但无自动同步 |
| 权限 | `RepositoryAccessPolicy`(路径白名单、敏感路径、符号链接拒绝) | MCP 无独立权限层,`tools/call` 走同一 `ToolExecutor` | ✅ 复用同一策略 |
| 错误码 | `ToolResult.error_type`(字符串)+ `ToolStatus` | 协议错误用 `McpError.code`;工具失败映射 `isError=true` + text | ⚠️ 缺口:工具错误没有机器可读 code 直通 MCP(只有文本) |
| `additionalProperties=false` | 工具层 `_reject_unknown_arguments` 强制 | Schema 已声明且 `McpToolDefinition.__post_init__` 强制 | ✅ 一致 |
| 新工具接入 | 注册到 `ToolRegistry` | 必须手工补 `_INPUT_SCHEMAS` 条目,缺失则构造时抛 `McpSchemaMissingError` | ⚠️ fail-loud,但双份维护 |

## 2. 实际验证(2026-08-02,bc76214)

- `uv run pytest -q tests/test_mcp_adapter.py tests/test_mcp_server.py` → **31 passed**。
- stdio smoke(真实进程,`uv run specflow mcp --root benchmarks/fixtures/portfolio-python`):
  - initialize → 回显 protocolVersion 2025-06-18、capabilities(`tools.listChanged=false`)、serverInfo 1.1.0;
  - `notifications/initialized` 前调用 tools/list → `-32002 Server not initialized`(协议顺序严格);
  - 通知后 tools/list → 3 个工具(list_files / read_file / search_code)带完整 JSON Schema;
  - tools/call read_file → 成功返回 content_hash、encoding、truncated;
  - 未知工具 → `isError=true` + "Tool not registered";
  - EOF → 干净退出。

## 3. 关键结论

1. 工具名/描述/权限/执行路径已是单一来源;**输入 Schema 是唯一的重复维护点**。
2. 错误语义:协议错误有 code,工具执行错误只有文本——MCP 客户端无法程序化区分"权限拒绝/参数非法/限流",是 5B 之后需要补的契约。
3. 现有 31 个测试覆盖了协议矩阵的大部分路径(见 protocol-smoke-checklist.md 映射)。
