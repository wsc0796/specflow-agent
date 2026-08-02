# Phase 6A — 6B 统一输出 Schema 草案(规格文档,不实现)

## 目标

三管道产物必须可被同一评分器消费。建议顶层产物为 `evaluation-output/v1`:

```json
{
  "schema_version": "evaluation-output/v1",
  "case_id": "pilot_01_single_file",
  "pipeline": "B1|B2|B4",
  "provider": "openai-compatible",
  "model": "<frozen>",
  "status": "completed|degraded|failed",
  "plan": {
    "summary": "",
    "sections": [],
    "evidence_refs": [{"id": "...", "path": "...", "hash": "..."}],
    "claims": [{"text": "...", "evidence_refs": ["..."], "uncertainty": "none|low|high"}],
    "risks": [{"id": "...", "severity": "...", "evidence_refs": ["..."]}],
    "test_plan": [{"topic": "...", "files": ["..."], "cases": []}]
  },
  "metrics": { "<RunMetrics 全部字段>" },
  "trace_ref": "traces.jsonl",
  "manifest_hash": "..."
}
```

## 约束

- 严格 schema(未知字段拒绝);所有路径为仓库相对路径;禁止绝对路径、API key、完整 prompt。
- B2/B4 现有 artifact 通过适配层映射到该结构,不重写业务逻辑。
- 该草案是否作为 6C 实现依据,由 Phase 6C 窗口确认(DECISION_REQUIRED)。
