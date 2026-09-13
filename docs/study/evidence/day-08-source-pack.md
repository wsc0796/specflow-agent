# Day 8 源码 Evidence Pack

- 日期：2026-09-13；基线：`5f2815d`。
- 状态：`AI-prepared / learner-unverified`；本文件不计学习完成或 ownership。
- 唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 用途：接续 [执行卡](../day-08-execution-card.md)，提供逐轮定位和短片段；不冻结合同。
- 本次只读源码/测试，未运行测试、baseline、Provider、实验，未访问 Holdout 或创建案例/gold。
- 以下位置均相对项目根；行号对应上述基线。测试位置表示已有断言，不表示本次执行。

## 一、Behavior 十个槽位的取证导航

每个槽位的 `must_happen / must_not_happen / legal_terminal_state` 仍待学习者定义。
这里只给现存路径、断言位置和可观察字段；不能用局部测试代替整个 suite 的验收。

### SF-AB-001 · Tool Selection

- 路径：`run_multi_agent` 调用 Collector，见 `src/specflow/runner_multi.py:111`；
  `EvidenceCollector.collect` 在 `src/specflow/evidence/collector.py:58` 固定调用
  list_files，`:67` 遍历关键词调用 search_code，`:100` 调用 read_file。
- 测试：`test_tool_call_records_are_complete`，`tests/test_evidence_collector.py:96`；
  `:103`–`:106` 检查 call_id、三种 tool_name、status、duration_ms。
- 观察：`ToolCallRecord`，`src/specflow/evidence/models.py:34` 的 call_id、tool_name、
  arguments_summary、output_summary、status、duration_ms；顺序来自 records 序列。
- 范围：这是 Collector 的确定性调用路径；标准 `AgentRunner → ToolExecutor` 的
  动态选择路径未获证明，记 `unknown`；现有测试未直接断言完整选择顺序。

### SF-AB-002 · Argument Validation

- 路径：`ReadFileTool.execute`，`src/specflow/tools/repository_tools.py:196`，先检查
  未知参数、非空 path，再进入 `RepositoryAccessPolicy.resolve_file`（`:199`）。
- 路径校验：`src/specflow/tools/repository_policy.py:205` 的
  `_normalize_relative_path`；异常由 `ToolExecutor.execute` 在
  `src/specflow/tools/executor.py:37` 转成 ToolResult。
- 测试：`test_read_file_rejects_parent_traversal`，`tests/test_repository_tools.py:212`；
  `:215`–`:216` 检查 result.status 和 result.error_type。
- 观察：ToolResult.status/error_type；Collector 的失败 record 写入点为
  `src/specflow/evidence/collector.py:180`。模型生成非法 JSON 的 Tool 循环路径为 `unknown`。

### SF-AB-003 · Timeout / Retry

- 路径 A：`AgentRunner.execute`，`src/specflow/agents/adapter.py:83` 的 bounded loop，
  `:96`–`:101` 分类错误、检查重试上限及 backoff；默认 max_retries 在 `:39` 为 0。
- 标准接线：`src/specflow/runner_multi.py:180` 的 AgentRunner 构造未传 max_retries。
  可配置能力与标准路径实际启用次数应分别记录。
- 测试 A：`TestAgentRunner.test_security_error_is_not_retried`，
  `tests/test_agent_adapter.py:162`；`:178`–`:179` 检查 calls 与 output.error_code。
- 路径 B：`MultiAgentScheduler.execute`，`src/specflow/coordinator/scheduler.py:131`；
  测试 `TestMultiAgentScheduler.test_expired_deadline_fails_before_submitting_work`，
  `tests/test_scheduler.py:196`；`:205` 检查异常分类，`:212` 检查 executed。
- 观察：Provider 调用计数、输出 error_code、scheduler 异常；ToolExecutor 自身的
  timeout/retry 路径及标准 AgentRunner timeout 重试集成断言为 `unknown`。

### SF-AB-004 · Loop Termination

- 路径 A：`EvidenceCollector.collect`，`src/specflow/evidence/collector.py:68`、`:96`；
  达到 max_tool_calls 时退出当前循环；`_execute_tool` 在 `:152` 也检查调用上限。
- 测试 A：`test_tool_call_count_is_bounded`，`tests/test_evidence_collector.py:109`；
  `:119` 检查 tool_call_records 数量。
- 路径 B：`run_multi_agent` 的 revision 分支见 `src/specflow/runner_multi.py:282`、
  `:355`–`:360`；涉及 revision_exhausted 和 workflow transition。
- 测试 B：`TestMultiAgentRunner.test_reject_runs_one_revision_then_completes_when_limit_is_exhausted`，
  `tests/test_cli_multi_agent.py:320`；`:355`–`:359` 检查 reviews、workflow_state、
  revision_count、revision_exhausted、workflow_history。
- 范围：Collector 调用边界、固定 revision 与重复 Observation 检测是不同对象；
  Agent Tool Loop 的 observation-repeat guard / max turns 为 `unknown`。

### SF-AB-005 · Permission

- 路径：`ReadFileTool.execute` → `RepositoryAccessPolicy.resolve_file` →
  `_validate_path_parts`，见 `src/specflow/tools/repository_policy.py:109`、`:223`；
  `:227`–`:228` 调用 is_sensitive_path 并抛 SensitiveFileError。
- 测试：`test_read_file_rejects_sensitive_files`，`tests/test_repository_tools.py:272`；
  `:277`–`:278` 检查 status/error_type。越界路径另见 SF-AB-002。
- 观察：ToolResult.status/error_type，及 Collector 失败 record；这是只读 Repository
  Tool 边界。模型覆盖权限、外部副作用审批的标准 Agent Tool 路径为 `unknown`。

### SF-AB-006 · Prompt Injection / Context Pollution

- 文本入口：`_build_user_message`，`src/specflow/agents/adapter.py:169`，`:180`、
  `:188`–`:193` 放入 untrusted 提示和 repository evidence。
- 测试：`TestAgentRunner.test_runner_warns_repository_evidence_is_untrusted_data`，
  `tests/test_agent_adapter.py:109`；`:115`–`:117` 检查请求文本。
- 字段入口：`_validated_inputs`，`src/specflow/runner_multi.py:627`，`:641`–`:658`
  为不同 receiver 构造 payload，`:663` 执行 model_validate。
- 额外接收面：`_budgeted_executor` 在 `src/specflow/runner_multi.py:619` 仍传入
  `{**context, "validated_input": validated_input}`；仅看 payload 字段表不够。
- 最近测试：`TestMultiAgentRunner.test_receiver_input_schema_is_executed_before_scheduling`，
  `tests/test_cli_multi_agent.py:52`，`:55` 检查非法输入异常；它不是完整 Context 隔离断言。
- 观察：实际 executor context、validated_input 和最终 LLMRequest.messages。
  提示词抗攻击效果、接收面最小化专项断言与危险 Tool 参数攻击链为 `unknown`。

### SF-AB-007 · No Evidence

- 路径：`run_multi_agent`，`src/specflow/runner_multi.py:130` 检查 evidence.excerpts，
  调用 `_persist_pre_execution_failure` 后在 `:142` 返回；持久化函数入口 `:951`。
- 测试：`TestMultiAgentRunner.test_zero_evidence_fails_before_agents_and_persists_reason`，
  `tests/test_cli_multi_agent.py:76`；`:116`–`:126` 检查 exit_code、调用标记及 manifest。
- 观察：Coordinator/analyst 调用标记、workflow_state、error、stages_completed、
  selected_file_count、referenced_file_count；不是“真实任务一定无答案”的语义标签。

### SF-AB-008 · Required Handoff Failure

- 路径：`_run_and_accumulate` 在 `src/specflow/runner_multi.py:608` 调用
  `_validate_stage_results`（`:667`），`:674`–`:675` 检查 agent_id/success。
- 测试：`TestMultiAgentRunner.test_required_agent_failure_stops_before_specialists`，
  `tests/test_cli_multi_agent.py:424`；`:443`–`:456` 检查返回值和 specialists_called。
- 观察：stage.agent_results、result.success、下游调用标记、exit_code。
  此测试注入的是 repository analyst 失败；同类每个 specialist 的逐项失败断言为
  `unknown`，不可把一条测试登记为所有 required 节点已测。

### SF-AB-009 · Handoff Schema

- 路径：`_validate_stage_inputs` 在 `src/specflow/runner_multi.py:757` 调用
  `HandoffValidator.validate`；源码 `src/specflow/handoff/validator.py:48`、`:53`
  分别比较 sender output 和 receiver input schema ID。
- 测试：`TestHandoffValidator.test_mismatched_target_input_schema_raises`，
  `tests/test_handoff_validator.py:89`；`:105`–`:106` 检查 HandoffValidationError。
- 观察：source_output_schema_id、target_input_schema_id、异常；payload 的输入
  验证另见 SF-AB-006，输出验证见 `src/specflow/runner_multi.py:681`–`:684`。
- 范围：ID 一致性与内容 schema 是不同校验；该单元拒绝测试的完整 Run 终态为 `unknown`。

### SF-AB-010 · Handoff Integrity

- 路径：`_validate_stage_inputs` 在 `src/specflow/runner_multi.py:758` 调用
  `HandoffValidator.validate_payload`；`src/specflow/handoff/validator.py:82`–`:84`
  对规范化 payload 重算 SHA-256 并比较 output_hash。
- 单元测试：`TestHandoffValidator.test_payload_mutated_after_hash_raises_integrity_error`，
  `tests/test_handoff_validator.py:130`；`:150`–`:159` 检查异常分类与 audit_context。
- 集成测试：`TestMultiAgentRunner.test_handoff_integrity_failure_stops_receiver_and_persists_context`，
  `tests/test_cli_multi_agent.py:256`；`:289`–`:310` 检查 receiver、manifest、traces。
- 观察：handoff_id/from_agent_id/to_agent_id/payload_ref、error_code、failure_context；
  已有异常捕获入口 `src/specflow/runner_multi.py:362`。不从 hash 一致推导内容正确。

## 二、R2–R5 的课堂最小片段

### R2 · EvaluationCase 字段到消费者

`EvaluationCase`，`src/specflow/evaluation/models.py:34`–`:39`：

```python
    expected_domains: tuple[str, ...]
    expected_file_patterns: tuple[str, ...]
    expected_risks: tuple[str, ...]
    expected_acceptance_topics: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    human_review_notes: str
```

`run_mock_evaluation`，`src/specflow/evaluation/runner.py:51`–`:57`：

```python
        missing_files = [
            path for path in case.expected_file_patterns if not (repository_root / path).is_file()
        ]
        exit_code = (
            3
            if missing_files
            else run(
```

测试入口：`test_mock_evaluation_detects_missing_grounding_file`，
`tests/test_evaluation.py:93`；`:100` 检查 case_file_missing。
其他 expected/forbidden 字段在 evaluation 包找到定义和加载，自动语义评分消费者为 `unknown`。
如需对照真实选入证据，再展示 `EvidenceCollector.collect`，`src/specflow/evidence/collector.py:89`。

### R3 · 分母、筛选集合与默认值

`_aggregate`，`src/specflow/evaluation/benchmark.py:207`–`:209`、`:219`–`:221`、
`:235`、`:238`–`:239`；`_rate`，`:262`–`:263`。以下为按原顺序摘取的非连续片段：

```python
def _aggregate(runs: list[dict[str, object]]) -> dict[str, object]:
    total = len(runs)
    passed = sum(run["status"] == "passed" for run in runs)
    metric_runs = [run for run in runs if run["status"] == "passed"]
    error_codes = Counter(code for run in runs for code in run["error_codes"])
    latencies = [run.get("wall_time_ms", 0) for run in metric_runs]
            "run_success_rate": _rate(passed, total),
            "total_input_tokens": sum(run.get("input_tokens", 0) for run in metric_runs),
            "total_output_tokens": sum(run.get("output_tokens", 0) for run in metric_runs),
def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
```

测试导航：`test_benchmark_cli_writes_report_and_baseline`，`tests/test_benchmark.py:98`，
`:118`–`:120` 是整体报告断言；失败成本聚合的直接断言为 `unknown`。
字段默认值对照 `RunMetrics`，`src/specflow/evaluation/metrics.py:49`–`:59`。

### R4 · Validator 的实际判定单位

`_validate_sources`，`src/specflow/evaluation/validators.py:220`–`:231`：

```python
        resolved = (root / path).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            findings.append(
                EvaluationFinding("source_path_external", f"External source path: {item}.")
            )
            continue
        if not resolved.is_file():
            findings.append(
                EvaluationFinding("source_path_missing", f"Missing source path: {item}.")
            )
```

测试导航：`test_live_import_rejects_missing_artifact_invalid_json_external_path_secret_and_traces`，
`tests/test_live_validation_import.py:77`；`:98`–`:101` 检查 source_path_external。
候选来源组成见 `src/specflow/evaluation/validators.py:204`；语义 Citation 评分入口为 `unknown`。

### R5 · A/B 的调用条件与分数来源

`run_mock_ab_case`，`src/specflow/evaluation/multi_agent_runner.py:60`–`:63`、`:68`–`:74`：
以下非连续片段分别位于运行部分与 legacy 字典内部。

```python
    legacy_code = run_legacy(
        repo=repo, requirement=requirement, output=legacy_output, provider="mock"
    )
    multi_code = run_multi_agent(repo=repo, requirement=requirement, output=multi_output, mock=True)
        "dimensions": [
            {
                "key": "artifact_completeness",
                "score": 2 if legacy_artifact and legacy_code in {0, 4} else 0,
            },
            {"key": "requirement_coverage", "score": 0},
        ],
```

测试：`TestMultiAgentEvaluation.test_mock_ab_runs_identical_input_through_both_pipelines`，
`tests/test_evaluation_multi_agent.py:81`；`:90`–`:92` 检查 case_id 和两侧 artifact 分。
多 Agent 分数见 `src/specflow/evaluation/multi_agent_runner.py:78`–`:84`；
`compare_legacy_vs_multi_agent` 在 `:45`–`:52` 汇总传入 dimensions。

## 三、使用与维护

- 教师按当前轮次取用片段；学习者回答后再给【正确答案】与差异解释。
- 四项行为断言、正反例、指标解释、T0 和合同冻结仍由学习者完成；本包不产生新测试数据。
- 核验覆盖引用路径/行号、短片段一致性、`git diff --check`；后续源码变化须更新引用基线。
