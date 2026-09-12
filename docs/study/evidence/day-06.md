# 第 06 天证据卡

- 日期：2026-09-11
- 路线：V5.3.2 Learning Effectiveness Patch，第 6 天
- 学习模式：SURVEY；Integrity Tamper 缺口经用户明确批准后进入独立 PATCH（T-073）
- 状态：已完结（教学内容与行政记录均已收束）
- 记录性质：源码级学习记录与已执行的确定性测试证据；按用户要求取消闭卷复述和最终能力判定

## 当前主题

追踪 Coordinator → Repository Analyst → Design/Test/Risk → Synthesis →
Review → Revision/Artifact，区分 Schema 声明、映射后输入合法、payload
完整性、接收者字段最小化与事实正确性。

## Handoff 契约图

```text
发送方业务输出
  -> Output Schema 校验
  -> 完整 Agent 执行 envelope
  -> payload_ref + output_hash
  -> HandoffValidator
  -> 从 envelope 提取 result["output"]
  -> 按接收者字段重新组装 payload
  -> Receiver Input Schema 校验
  -> Executor Context + validated_input
  -> 标准 AgentRunner 构造 LLMRequest.messages
```

`output_hash` 保护完整执行 envelope，`payload_ref` 指向
`agent-outputs.json#stage-N/agent-id`，接收者获得的是从 envelope 中提取并
重新投影后的 receiver-specific input。Synthesis 的三条依赖边产生三个
`AgentHandoff` 记录，再汇聚成一个经过校验的 `SynthesisInput`。

Schema compatibility 的结论是：当前实现证明映射后的 Receiver Input 合法，
不证明发送方 Output Schema 与接收方 Input Schema 直接兼容。Schema ID 已
注册、Handoff ID 与双方 Identity 一致、实际 receiver payload 通过 Pydantic
校验，是三个不同的证明层级。

### 失败假设：Schema incompatible

若 Design 角色仍生成 `requirement + repository_analysis`，但其 Identity 改为
已经注册的 `ReviewInput`，PlanValidator 与 HandoffValidator 可以通过，随后
Receiver Input Schema 拒绝 `repository_analysis`，Design Executor 不得绕过
输入校验执行。当前没有为这一精确注入单独实现集成测试；该缺口不阻塞
Day 6 教学内容完结。

## 失败卡：Integrity Tamper

### 注入变化

先根据原始 payload 生成正确 `output_hash`，然后在
`HandoffValidator.validate_payload()` 执行前修改同一个 payload 的 `output`
内容。

```text
原始 payload
  -> 生成正确 output_hash
  -> 修改 payload.output
  -> validate_payload 重新计算 hash
```

### 最早拒绝位置

`HandoffValidator.validate_payload()` 会重新计算实际 payload 的规范化 SHA-256，
并与 Handoff 中记录的 `output_hash` 比较。两者不一致时拒绝 Handoff。

源码锚点：

- `src/specflow/handoff/validator.py:59-84`
- `src/specflow/runner_multi.py:696-732`

### 接收者执行边界

接收者不应执行。下游阶段先调用 `_validate_stage_inputs()` 完成 Handoff
校验，随后才会进入 `_run_and_accumulate()` 和 Scheduler。

预期可观察断言：

```text
receiver_call_count == 0
```

### 当前合法终态

该 mismatch 现在抛出专用 `HandoffIntegrityError`。Multi-Agent Runner 在
接收者调度前捕获该异常：Workflow 转入 `FAILED`，Runner 返回退出码 `3`，
并以 `HANDOFF_INTEGRITY_FAILED` 写入失败 Artifact。

源码锚点：

- `src/specflow/handoff/exceptions.py:12-37`
- `src/specflow/handoff/validator.py:82-92`
- `src/specflow/policy/errors.py:42`
- `src/specflow/runner_multi.py:358-381`
- `src/specflow/runner_multi.py:982-1041`

### 当前 Trace 粒度

失败 Manifest 与根/Coordinator Trace 现在记录
`HANDOFF_INTEGRITY_FAILED`，并携带 `handoff_id`、`from_agent_id`、
`to_agent_id` 和 `payload_ref`。定位信息不包含原始 payload、expected/actual
hash、异常文本、仓库路径或 secret。

### 当前测试证据与缺口

T-073 已补齐两层确定性测试：

- `tests/test_handoff_validator.py:130-160`：正确 hash 后修改 payload，真实
  Validator 抛出专用完整性异常；
- `tests/test_cli_multi_agent.py:256-320`：Runner 边界篡改、Receiver 零调用、
  失败终态、Manifest/Trace 定位字段和 payload-safe Artifact。

验证证据：受影响路径 `58 passed`；完整测试
`775 passed, 3 skipped, 3 known warnings`；Ruff lint、Ruff format 与
`git diff --check` 通过。实现记录见
`docs/tasks/T-073-handoff-integrity-failure-observability.md`、
`docs/reports/T-073-completion-report.md` 和 commit `6c69308`。

## Day 6 收束

- Handoff 契约图：完成；
- Schema compatibility：完成直接兼容与映射后输入合法的区分；
- 失败假设：Schema incompatible 与 Integrity tamper 均已覆盖；
- Receiver isolation：完成 `validated_input`、Executor Context 与 LLM 可见性
  的区分；
- 失败传播、Revision、Synthesis 汇合、Artifact 与 Trace 粒度：已覆盖；
- 闭卷复述与最终能力判定：按用户要求取消，不构成完结阻塞；
- Day 6 教学内容：已完结；
- Day 7、Vector、Hybrid、Rerank、外部供体：未进入。
