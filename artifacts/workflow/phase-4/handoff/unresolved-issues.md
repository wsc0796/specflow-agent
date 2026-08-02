# Phase 4A Unresolved Issues

1. **DECISION_D1 — default provider-attempt budget**:当前默认 10 不足以覆盖正常 live 路径(12 attempts,一轮 revision 15,retry 最坏 36/45);需用户选 24 或 48。本阶段未改动默认值。
2. **Phase 4B live 审批(用户决策)**:API key、base URL、model、最大费用、最大 token、最大 wall-clock 均未定,禁止在批准前运行任何真实 provider。
3. **费用上限机制缺失**:只有 token/wall-clock 代理;正式方案需要明确“最大费用”如何折算或另行记账。
4. **Token 错误码粒度**:runtime_guard 当前统一 `TOKEN_BUDGET_EXCEEDED`,与 Phase 3F taxonomy 的 INPUT/OUTPUT/TOTAL 细分有差距,列入定案任务改动点 2。
5. **API 认证不在 verified base**:`api_security.py` 未合入 bc76214;live 仅限本地单用户。
