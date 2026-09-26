# T-090 修复报告

日期：2026-09-26。新 manifest 声明 all_provider_requests_v1；评估器交叉验证完整性、budget_usage 与 metrics 后报告全调用用量。有请求观察时再拆分 Coordinator/Agent；无观察不捏造角色计数。无版本旧记录保持旧义，未知版本不声称完整。

| 验收 | 结果 | 证据 |
|---|---|---|
| AC-001 | PASS | RED 4 failed/24 passed，暴露无新契约及缺失全调用字段。 |
| AC-002 | PASS | GREEN 75 passed，覆盖Mock/Fake实链、计数/用量矛盾与非法类型、缺失observer、旧/未知版本；全部HTTP=0。 |

外部日志：specflow-repair-backups/2026-09-26-T087-T093/t090-{red,green}.log；主/子进程真实 HTTP=0。最终全量与独立审查统一收口。未读或改正式 Dev/Holdout、历史产物或学习材料。
