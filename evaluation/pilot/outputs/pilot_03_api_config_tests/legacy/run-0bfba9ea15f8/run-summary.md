# Run Summary

| Field | Value |
|---|---|
| Run ID | run-0bfba9ea15f8 |
| Status | completed |
| Provider | mock |
| Model | mock-model |
| Review Decision | PASS |
| Degraded | False |
| Requires Review | False |
| Tool Calls | 14 |
| Files Read | 3 |
| Evidence Hash | b965a26eaab9ae78... |

## Files Read

- app/main.py
- app/orders.py
- tests/test_orders.py

## Tool Calls

- `list_files` (success) — include=['*.py', '*.md', '*.yaml', '*.yml', '*.toml', '*.cfg']
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=test
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=API
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=order
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=test_orders
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=为订单
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=入位置
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=环境变量
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=的实施计划
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=的测试计划与
- ... and 4 more

## Capability Boundaries

- Read-only repository access only (no write/delete/shell/git)
- No automatic code modification
- No Agent Loop or ReAct pattern
- No multi-agent orchestration