# Security & Claim Audit — 窗口 D(bc76214)

审计窗口:security_claim_audit(由 phase_4a_live_prep 窗口代为执行)· 分支:fix/security-claim-audit
性质:只读审计,不修复任何问题。

## 1. 检查结果

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 全量 pytest | ✅ 777 passed, 2 skipped(29.5s) | 本窗口实跑 |
| Secret scan | ✅ 通过 | `python scripts/check_secrets.py` |
| Ruff lint / format | ✅ All checks passed / 204 files formatted | 本窗口实跑 |
| Benchmark baseline | ✅ 未变 | SHA-256 = BE9BB6F16ADA25638315EDEBDC3A70B654A321D521126B110E667A8386EE3E81 |
| MCP 测试 | ✅ 31 passed | 同 commit 5A 窗口实跑 |
| Trace 无 prompt/secret | ✅ | `test_finding_driven_revision.py:852-872` marker 断言(marker 与全文不进入 trace);ArtifactPolicy `include_raw_prompt/output=False` |
| README/docs 无未支持主张 | ✅ | README 全文无 production-ready/high availability/resume support/quality improvement;ledger 中相关词均为 REJECTED/PENDING 语境 |

## 2. Claim 审计结论(详见 claim-evidence-update.md)

- Phase 1/2/3 已解锁 claims 全部有代码 + 测试证据,维持 VERIFIED。
- 未解锁 claims(live validation、multi-agent quality improvement、production-ready、legacy 全量统一、默认预算支持 live 路径)维持 REJECTED/PENDING/BLOCKED。
- 本窗口不改 ledger;合入 Phase 4/5 后由总控按新证据复评。

## 3. 发现(只记录,不修复)

- F1:两个 `PytestCollectionWarning`(`TestStrategyAgent`、`TestStrategyOutput` 类带 `__init__`),不影响结果,建议 DEFER 改名。
- F2:`StarletteDeprecationWarning`(httpx2),依赖升级决策,DEFER。
- F3:API 认证(`api_security`)不在 verified base(bc76214),公开部署前必须补;本地单用户不受影响。
- F4:仓库根无 LICENSE,发布阻断项(5A 同发现)。
- F5:MCP stdio 无请求级 timeout,5A 同发现,DEFER。

## 4. 退出状态

**PASS**(无 MUST_FIX;F3/F4 为发布前置决策项,不属于本窗口修复范围)。
