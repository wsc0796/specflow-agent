# Control Coverage Backlog

本文件集中记录 Control Coverage Audit 中已经由源码发现、但尚未完成复现与处置的项目。记录不等于确认产品缺陷，也不授权进入 PATCH。

## CC-001 — Coordinator LLM 未接入当前 RuntimeGuard 计数与显式 Retry

- 记录日期：2026-09-13
- 状态：`OPEN / PENDING REPRODUCTION`
- 执行路径：`run_multi_agent → Coordinator.plan → SemanticPlanEnricher.enrich → LLMClient.complete`
- Control Matrix：
  - Coordinator LLM Budget：`×`
  - Coordinator LLM Retry：`×`（Enricher 应用层；Provider 内部行为尚未检查）

### 已观察源码事实

1. `run_multi_agent()` 创建 `RuntimeGuard(policy)`，随后创建 `Coordinator` 并调用 `coordinator.plan(run_id)`；`guard` 没有传入 Coordinator。
2. `Coordinator.plan()` 创建 `SemanticPlanEnricher`，并调用 `enricher.enrich(spec)`。
3. Enricher 直接调用 `self._llm.complete(request)`；当前 Enricher 路径没有调用 `guard.consume_llm_call()`。
4. `guard.consume_llm_call()` 位于后续 Agent Stage 的 `_budgeted_executor()` 中。
5. Enricher 调用失败时生成 `SemanticTaskBrief.degraded_default(...)`；当前 Enricher 应用层没有重新执行同一次失败调用。

### 源码锚点

- `src/specflow/runner_multi.py:79`
- `src/specflow/runner_multi.py:160-167`
- `src/specflow/coordinator/coordinator.py:101-107`
- `src/specflow/plan/enricher.py:49`
- `src/specflow/runner_multi.py:609-617`

### 可达影响假设

- `ExecutionPolicy.max_llm_calls` 可能只约束 Agent Stage，无法约束一次 Run 的全部 LLMClient 调用。
- `manifest.budget_usage.llm_calls` 可能不包含 Coordinator 语义增强调用。

以上均为待复现假设，不能作为已确认运行结果或简历事实。

### 后续验证

1. 使用可计数的 Fake/Mock LLMClient，并设置较小的 `max_llm_calls`。
2. 在运行前记录预测：Coordinator 调用次数、Agent 是否启动、预期退出码和 Manifest 计数。
3. 复现并保存实际调用次数、终态、失败 Artifact 和 Budget 记录。
4. 单独确认 Provider 客户端是否存在内部 Retry；不得用 Enricher 的 `degraded_default` 冒充 Retry。

### 处置边界

- Budget 与 Retry 分开裁决，不合并为一个未经证明的修复。
- 只有复现证明 Budget 语义或运行约束被真实绕过，并明确预算应覆盖 Coordinator，才创建冻结任务规格并进入 PATCH。
- 缺少 Retry 本身不自动构成 Bug；需先确定瞬时错误应当重试还是直接降级。

## CC-002 — RepositoryPolicy 其余字段的执行接线尚未形成完整证据

- 记录日期：2026-09-13
- 状态：`OPEN / FIELD-BY-FIELD VERIFICATION`
- 已关闭项：T-074 已验证 `max_file_bytes` 在 Legacy 与 Multi-Agent Runner
  中到达 Repository Tools。

### 已观察源码事实

1. `max_selected_files` 和 `max_total_evidence_chars` 在两个 Runner 中进入
   `EvidenceCollectionConfig`；T-074 没有为这两个字段新增行为测试。
2. T-074 的共享转换只映射 `max_file_bytes`，没有映射
   `max_scanned_files`。
3. 当前调查没有找到 `max_evidence_items` 到具体 Repository Tool 或
   EvidenceCollector 控制点的已验证执行闭环。
4. `EvidenceCollectionConfig.max_file_bytes` 仍存在，但当前 Collector 没有消费
   该字段；T-074 没有删除或重新定义它。

### 源码锚点

- `src/specflow/policy/models.py:29-42`
- `src/specflow/policy/repository_limits.py:9-11`
- `src/specflow/runner.py:89-99`
- `src/specflow/runner_multi.py:97-108`
- `src/specflow/evidence/models.py:58-72`

### 可达影响假设

- 可配置但未接线的字段可能使策略哈希、调用者预期与实际资源控制不一致。
- Legacy 与 Multi-Agent 若分别接线，可能产生不同的限制行为并影响 A/B 公平性。
- 将 `max_evidence_items` 直接等同于 `max_search_matches` 可能混淆搜索命中、
  最终摘录和 Artifact 条目三种不同对象。

以上除 T-074 已关闭项外均为待验证项，不自动构成产品缺陷。

### 后续验证

1. 为每个策略字段写清受控对象、执行边界和合法失败语义。
2. 先写 Legacy/Multi-Agent 行为测试，再增加集中转换映射。
3. 只有名称与语义均一致的字段才允许进入共享转换。
4. 无合法消费者的字段应选择记录为 `N/A`、弃用或删除，不能保留虚假控制声明。

### Deferred：搜索扫描量与读取输出量分离

当前 `max_file_bytes` 同时约束 `search_code` 和 `read_file`。若真实评测证明需要
“搜索较深、返回较少”，必须另行定义 `max_search_file_bytes`、
`max_read_file_bytes`、hash scope 和超出读取窗口的 Evidence provenance。
在这些契约冻结前，不进行简单拆分，避免搜索摘录超出 `source_hash` 覆盖范围。
