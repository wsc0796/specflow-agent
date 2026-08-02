# Phase 5A — 5D Release 文档检查清单(bc76214)

| 项目 | 现状 | 缺口 |
| --- | --- | --- |
| README | ✅ 存在,含 benchmark 说明;无未支持主张 | 无 MCP 使用说明、无配置/预算说明 |
| Architecture | ⚠️ `docs/00-SPEC-BASELINE.md` + `docs/records/M8-production-hardening.md` 覆盖 | 无统一 Architecture 文档 |
| MCP guide | ⬜ 缺失 | 需要 tools/list/call 示例、stdio 用法、权限边界 |
| Live guide | ⬜ 缺失 | Phase 4 交付后补(本窗口只标记) |
| Benchmark boundaries | ✅ README "Portfolio benchmark (mock-only)" | 可补充 baseline 校验步骤 |
| Known limitations | ⚠️ claim-evidence-ledger 的 REJECTED 行承担此职责 | 无用户向 Known limitations 章节 |
| CHANGELOG | ✅ 存在 | 需追加 Phase 1-3 条目 |
| LICENSE | ⬜ **缺失**(仓库根无 LICENSE 文件) | 需用户决定许可协议 |
| version | ✅ pyproject 1.1.0 | 发布前按语义化版本决策 |
| CI badges | ⬜ README 无 badges | 可在 README 顶部加 |
| test counts | ⚠️ CI 输出含 | 发布前从最新 CI/本地全量更新 |
| issues/PR | 外部事项 | 由总控/用户处理 |

## 禁止写入词(4 项)

`production-ready`、`high availability`、`resume support`、`quality improvement`——除非有正式评测/证据支持(当前均无,claim-evidence-ledger 全部标 REJECTED 或 PENDING)。

## 现状扫描结果

对 README/CHANGELOG/docs 全文 grep:上述 4 词只出现在 claim-evidence-ledger 的 REJECTED 说明与任务文档的否定语境中,未发现未支持主张。✅
