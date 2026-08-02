# Claim–Evidence Update 建议(窗口 D,bc76214)

原则:只依据代码与测试事实;mock 证据不代表 live 验证或质量提升。

## 维持 VERIFIED(有证据)

| Claim | 证据 |
| --- | --- |
| Task Brief 严格版本化 Schema | `plan/models.py` strict models + `test_task_brief_execution.py` |
| 六角色各自消费自己的 brief | `runner_multi._validated_inputs` + 集成测试 |
| brief 可观察地影响真实请求 | `agents/adapter._build_user_message` + 分区断言测试 |
| brief 生成/消费/artifact/hash 可审计 | artifact + manifest hash + trace 事件 |
| findings 结构化且驱动 revision | `revision/models.py` + `test_finding_driven_revision.py` |
| bounded revision 终态 NEEDS_HUMAN_REVIEW | 状态机 + golden 测试 |
| 多 Agent 运行时 provider 调用统一受控 | `invoker.GuardedModelInvoker` + AST 门禁测试 |
| agent invocation ≠ provider attempt 等语义分离 | `runtime_guard.snapshot()` + 专项测试 |
| token 来自 usage,缺失=unknown 非 0 | `LLMResponse.usage` + `TestTokenAccounting` |
| 预算失败 fail-closed + 快照 | failed manifest + `TestFailureArtifacts` |

## 维持 REJECTED / PENDING / BLOCKED

- 默认 provider-attempt 预算支持 live 路径 → REJECTED(DECISION_D1:10 < 12,待选 24/48)。
- legacy 3-worker 走统一 invoker → REJECTED(冻结 A/B 基线,不迁移)。
- live validation → BLOCKED(未运行真实 provider,Phase 4B 待批准)。
- multi-agent quality improvement / 六角色优于单 Agent → PENDING(需 Phase 6/7 评测)。
- production-ready → REJECTED/BLOCKED。

## 建议

1. Phase 4/5 合入后,总控依据 live artifact 与 MCP/发布成果更新本 ledger。
2. DECISION_D1 定案后,把"默认预算支持 live 路径"从 REJECTED 移出并写新证据。
3. 本窗口不修改 ledger 文件本身。
