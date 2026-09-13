# 第 07 天证据卡

- 日期：2026-09-13
- 路线：V5.3.2 Learning Effectiveness Patch，第 7 天
- 学习模式：主链与重测阶段为只读教学；T-074 经显式批准和冻结规格后进入 PATCH
- 状态：已收束（Week 1 技术内容完成，learner ownership 为 `improving / partial`）
- 记录性质：学习者可观察行为、源码证据、RED/GREEN 测试和边界说明

## 1. 固定成功路径

本日固定 `tests/test_cli_multi_agent.py::test_run_multi_agent_mock_mode`，沿一次
`mock=True` Multi-Agent Run 检查：

```text
测试输入
→ EvidenceCollector / EvidenceBundle
→ base_context / validated_input / Executor Context
→ mock Agent stages
→ Review PASS
→ Artifact writes / _COMPLETE
→ return 0
```

学习者形成或修正了以下判断：

- 测试函数不是输入数据；测试创建 repo、匹配 Evidence 和 output 路径。
- 函数签名、函数调用、返回变量和运行时消费者是不同证据。
- `context` 被传入不等于 mock Agent 实际读取了它；当前 mock Design 返回固定内容。
- `validated_input` 是接收者专属视图，不会删除 Executor 外层 Context。
- Review `PASS` 后仍需 Artifact 写入和 Finalize 成功，Runner 才返回 `0`。
- `return 3` 不会回滚此前已写入的 Manifest 或其他文件。
- `test_run_multi_agent_mock_mode` 只证明退出码和输出目录，不证明方案满足需求。

## 2. Day 4/5/6 换题面重测

### Day 4 — 路径控制

新题面使用 `search_code(include=["../*.py"])`。学习者定位
`validate_patterns()` 和失败 `ToolResult`，但首次把“会在扫描前阻止”写成
“不会”。纠正后能够区分 Policy 抛出异常与 ToolExecutor 转换失败结果。

状态：`improving`。

### Day 5 — Context Visibility

新题面使用 Revision 阶段的 `revision_task`。学习者正确判断该字段不能经标准
路径进入 `LLMRequest.messages`；经纠正后区分“没有投影进 validated_input”与
“从外层 Executor Context 删除”。

状态：`improving`。

### Day 6 — Handoff Failure

新题面使用缺失 sender runtime output。学习者正确判断 Receiver 不执行、最终
记录 `MULTI_AGENT_RUN_FAILED` 并返回 `3`；首次把停止位置写到 Validator，随后
修正为 `_validate_stage_inputs()` 的 `payload is None` 分支。

状态：`improving`。

## 3. Control Matrix v1

符号必须绑定右侧口径，不能把局部 `✓` 扩大成全系统完成。

| 执行路径 | Budget | Retry | Schema | Trace | Permission | DLP/敏感 |
| --- | --- | --- | --- | --- | --- | --- |
| Coordinator LLM | `×` RuntimeGuard 未覆盖 Enricher | `×` 失败后直接 degraded | `×` 严格输出 Schema；仅 JSON + 最小 dataclass 检查 | `✓` 本地 provenance ID；`×` traces.json 关联 | `N/A` 当前无 ToolCall | `×` 显式扫描；当前 Prompt 不含 requirement/Evidence，未证明泄露 |
| Specialist LLM | `✓` call/time/token wrapper | `×` 当前 `max_retries=0`，RetryPolicy 未接线 | `✓` Receiver input + output | `✓` Agent stage；`×` Provider call/attempt | `N/A` 当前无 Tool Loop | `✓` Evidence/前序输出与 Agent 输出边界；`×` requirement 显式扫描 |
| Reviewer LLM | `✓` call/time/token wrapper | `×` 当前 `max_retries=0`，RetryPolicy 未接线 | `✓` Receiver input + output | `✓` Agent stage；`×` Provider call/attempt | `N/A` 当前无 Tool Loop | `✓` 前序/输出边界；`×` requirement 显式扫描 |
| Evidence Tools | `✓` Collector call budget | `×` 失败记录后返回 None | `✓` 手写参数校验；`×` 声明式 input_model 执行 | `✓` ToolCallRecord；`×` record-level run/span | `✓` 路径 Policy；`N/A` 当前 Agent caller；`×` 系统级 per-Agent 强制 | `✓` 已定义凭据模式 |
| Artifact Write | `✓` 单文件；`×` Run 目录总量 | `×` | `unknown`：本日未完成独立 Artifact Schema Audit | `unknown`：本日未完成 write-attempt Trace Audit | `unknown/N/A`：需按副作用口径定义 | `✓` 已核对 Evidence/Agent output；全 Artifact 覆盖仍为 `unknown` |

## 4. Tool Permission 反例结果

尝试验证当前标准路径中的：

```text
DesignAgent → AgentRunner → ToolExecutor → read_file
```

源码搜索只证明：

```text
run_multi_agent → EvidenceCollector → ToolExecutor → Repository Tool
```

`AgentRunner` 没有 ToolExecutor 依赖，当前没有证明可达的 Agent Permission
绕过。`tool_permissions` 未进入 ToolExecutor 仍是系统级强制能力的 `×`，但不能
单凭未消费字段把当前标准 Agent 路径判为可达 Bug。

## 5. T-074 correctness failure

### 学习者预测与复现

实验：`policy.repository.max_file_bytes=5`，文件大小 21 字节，匹配词位于文件开头。

学习者亲手运行并提交结果：

```text
configured_limit = 5
file_size = 21
exit_code = 0
read_file_truncated = False
```

学习者随后定位 `RepositoryToolSet(repo)` 未传入 `limits`，选择集中策略转换方案，
并追问默认行为、搜索召回和后续 Policy 字段的影响。

### 冻结设计

- 共享 `repository_tool_limits_from_policy()`。
- Legacy 与 Multi-Agent Runner 共同调用。
- 本任务只映射已复现的 `max_file_bytes`。
- 保持搜索和读取共享硬文件上限；搜索/读取分离进入 provenance-aware backlog。

### TDD 与实现证据

```text
RED：     2 failed；两条路径均为 False is True
GREEN：   2 passed
受影响：  107 passed, 1 skipped
完整：    777 passed, 3 skipped, 3 known warnings
Ruff：    lint/format passed
Diff：    git diff --check passed
Commit：  952a952 fix: wire repository file limits into runners
```

任务与报告：

- `docs/tasks/T-074-repository-file-limit-policy-wiring.md`
- `docs/reports/T-074-completion-report.md`

### Ownership 边界

学习者完成：

- 运行复现实验并提交原始结果；
- 定位最早接线断点；
- 选择集中转换方案并挑战其影响；
- 解释关键 Diff 为什么让 `truncated` 从 `False` 变为 `True`。

Codex 完成：任务规格、自动化测试、产品 Patch、验证、完成报告和提交。因此 T-074
形成真实 learner-owned prediction/reproduction/design/review 证据，但不冒充学习者
亲手编写产品代码。

## 6. Retest Queue v1

| 能力 | 本次观察 | Readiness | 下一次换题面重测 |
| --- | --- | --- | --- |
| 创建者、声明与运行时消费区分 | 多次需要纠正函数签名/形参与实际数据 | `improving` | Day 14 用 Evaluator 输入/输出新对象重测 |
| Executor Context 与 LLM Messages | 能判断 revision_task 不进入消息；“剔除”措辞需修正 | `improving` | Day 14 用 Evaluator metadata 或 failure context 重测 |
| 失败最早边界与终态 | Receiver/终态判断正确；最早停止位置不稳定 | `improving` | Day 14 用 Evaluator failure attribution 重测 |
| Test 证据边界 | 能识别 exit code/目录不证明需求满足 | `improving` | Day 14 用正反 Evaluator fixture 重测 |
| Control scope | 已区分路径 Permission、per-Agent Permission、局部 Trace/DLP | `improving` | Day 14 用不同执行路径重测 |
| correctness failure ownership | 完成复现、定位、设计选择、Diff 解释 | `improving` | Day 21 用新的 Dev failure 独立完成预测→验证→取舍 |

只有跨不同 surface 稳定完成，状态才提升为 `stable`。

## 7. Week 1 Gate 结论

- Week 1 教学与技术交付：完成。
- 主链源码导航和局部工程判断：`improving`。
- Day 4/5/6 partial 项：经过换题面重测，仍未提升为 `stable`。
- T-074 技术闭环：完成并提交。
- Learner ownership：有真实复现、定位、设计与 Review 证据；手工产品编码仍为
  `partial`。
- Repository RAG、Vector、Hybrid、Rerank、Day 8 和外部供体：未进入。
