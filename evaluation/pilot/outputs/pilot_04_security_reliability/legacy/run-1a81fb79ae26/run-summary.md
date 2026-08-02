# Run Summary

| Field | Value |
|---|---|
| Run ID | run-1a81fb79ae26 |
| Status | completed |
| Provider | mock |
| Model | mock-model |
| Review Decision | PASS |
| Degraded | False |
| Requires Review | False |
| Tool Calls | 14 |
| Files Read | 3 |
| Evidence Hash | 2293f77d48a743d5... |

## Files Read

- app/orders.py
- app/main.py
- tests/test_orders.py

## Tool Calls

- `list_files` (success) — include=['*.py', '*.md', '*.yaml', '*.yml', '*.toml', '*.cfg']
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=idempot
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=order
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=timeout
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=复优先级
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=对订单提交链
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=授权边界
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=泄露内部细节
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=等与竞态
- `search_code` (success) — case_sensitive=False, include=['*.py'], query=订单提交的幂
- ... and 4 more

## Capability Boundaries

- Read-only repository access only (no write/delete/shell/git)
- No automatic code modification
- No Agent Loop or ReAct pattern
- No multi-agent orchestration