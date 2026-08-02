# Phase 5A — MCP Schema 单一来源改造方案(只写方案,不实现)

## 方案 A(推荐):Schema 进入 Tool 层

让每个 Tool 成为其输入 Schema 的唯一所有者:

- 在 `tools/models.py` 的 `ToolMetadata`(或 Tool 基类)增加 `input_schema: dict` 字段(JSON Schema,`additionalProperties=false` 由构造器强制)。
- `repository_tools.py` 的三个 Tool 显式声明自己的 schema(与现有校验约束同一处维护)。
- `McpToolCatalog` 改为读取 `metadata.input_schema`,`mcp/adapter.py` 删除 `_INPUT_SCHEMAS` 字典。
- `McpToolDefinition.__post_init__` 校验保留(防御性,双保险)。

收益:新增工具只需改一处;schema 与校验逻辑同 PR 同 review;MCP 层退化为零 Schema 知识。

## 方案 B(更彻底):Pydantic 参数模型

仓库已大量使用 Pydantic strict models。将每个工具的 arguments 定义为 Pydantic model,Tool 校验改为 model 解析,`input_schema = model_json_schema()` 直接生成。

收益:校验与 schema 天然一致;成本:重构三个 Tool 的校验路径与相关测试,风险高于 A。

## 方案 C(过渡):保留双份 + 一致性测试

保留 `_INPUT_SCHEMAS`,新增测试:对每个工具构造合法/非法参数矩阵,断言 MCP schema 拒绝的集合 == 工具层拒绝的集合。

收益:最小改动;成本:仍是双份维护,长期漂移风险不消除。

## 建议

选 **方案 A**;若实现窗口评估 A 改动面过大,退回 C 并把 B 记为 DEFER。此选择是 Phase 5 实现窗口的 DECISION_REQUIRED 项,本窗口不实现。
