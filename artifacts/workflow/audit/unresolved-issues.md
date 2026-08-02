# Security/Claim Audit Unresolved Issues(不修复,只记录)

1. **DECISION — API 认证**:`api_security.py` 未合入 bc76214;公开部署前必须合入并审计(本地单用户不受影响)。
2. **DECISION — LICENSE**:仓库根无 LICENSE,发布阻断项。
3. **DECISION — 依赖升级**:httpx2/starlette 弃用警告,升级策略由发布窗口决定。
4. **DEFER — PytestCollectionWarnings**:`TestStrategyAgent`/`TestStrategyOutput` 命名,无害,可后续改名。
5. **DEFER — MCP stdio timeout**:无请求级超时,5A 已记录。
