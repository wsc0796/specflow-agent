# T-091 修复报告

最终验证：974 passed、3 skipped、3 warnings；独立审查通过。详见 [批次汇总](audit-repairs-T087-T093-validation-2026-09-26.md)。

日期：2026-09-26。list_files 失败直接转安全 EvidenceCollectionError；multi-agent 任意采集/setup异常均保存 EVIDENCE_COLLECTION_FAILED、阶段、实际工具次数及允许名单内工具类型，不打印原始 traceback。

| 验收 | 结果 | 证据 |
|---|---|---|
| AC-001 | PASS | RED 4 failed，原路径全部没有manifest；修复后分类失败产物齐全且不泄漏异常。 |
| AC-002 | PASS | GREEN首轮83 passed/1 failed因旧测试替身缺tool_call_records；补齐接口、不改断言后 t091-green-2：84 passed/1 skipped/1 warning。 |

外部日志：specflow-repair-backups/2026-09-26-T087-T093/t091-{red,green}.log；主/子进程真实 HTTP=0。最终全量与独立审查统一收口。未读或改正式 Dev/Holdout、历史产物或学习材料。
