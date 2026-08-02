# Phase 6A — 6E 成本采集字段草案(不实现)

基于现有 `RunMetrics`,每 run 输出 `cost.json`:

```json
{
  "run_id": "...",
  "pipeline": "B4",
  "case_id": "pilot_01_single_file",
  "model": "<frozen>",
  "provider": "openai-compatible",
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "token_usage_known": true,
  "provider_call_attempts": 12,
  "successful_provider_calls": 12,
  "failed_provider_calls": 0,
  "provider_latency_ms": 0,
  "wall_clock_ms": 0,
  "estimated_cost_usd": 0.0,
  "cost_basis": "PENDING_USER_APPROVAL"
}
```

注意:

- `estimated_cost_usd` 依赖用户批准的单价口径(Phase 4B);未批准前只记录 token 数,不估算费用。
- 缺失 usage 的调用按 `token_usage_unknown_calls` 单独记录,不得按 0 计入成本。
