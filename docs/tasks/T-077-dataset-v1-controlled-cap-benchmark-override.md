# T-077 — Dataset v1 controlled-cap benchmark override

- 日期：2026-09-22；version：`v1`；status：`IMPLEMENTED_AND_VERIFIED / FORMAL_RUN_PENDING`。
- 授权：学习者已选择 `controlled-cap-at-5`，并明确批准独立 Patch。
- 前置任务：[T-076](T-076-dataset-v1-multi-agent-dev-adapter.md)。

## 1. 唯一目标

Day 11 正式 Multi-Agent Dev 基准必须在评测适配层把
`max_selected_files` 固定为 5，使 Legacy 与 Multi-Agent 的该项输入上限一致，尽量把比较变量
收敛到拓扑差异。产品 `run_multi_agent()` 的默认有效上限仍为 10。

## 2. 行为需求

- **REQ-077-1 评测层覆盖**：Dataset v1 Multi-Agent worker 从 `DEFAULT_POLICY` 派生一次仅把
  `repository.max_selected_files` 改为 5 的局部 `ExecutionPolicy`，并显式传给
  `run_multi_agent(policy=...)`。
- **REQ-077-2 产品默认不变**：不修改 `runner_multi.py`、`DEFAULT_POLICY` 或普通产品入口；不传
  覆盖 Policy 时，Multi-Agent 的产品有效上限继续为 `min(10, policy...) == 10`。
- **REQ-077-3 双值记录**：Day 11 config/report 同时记录
  `product_default_multi_agent_limits.max_selected_files=10` 与
  `effective_multi_agent_limits.max_selected_files=5`，不得把 benchmark 覆盖写成产品默认值。
- **REQ-077-4 fail closed**：正式运行只接受已批准的 `controlled-cap-at-5` 和完整的 10/5 配置。
  配置字段缺失、有效值不是 5、产品默认记录不是 10、runtime/policy 漂移或已有 attempts 时，
  必须在启动产品子进程前失败。
- **REQ-077-5 单次正式运行门不变**：本 Patch 只解除公平性实现阻塞；不运行正式 Provider，
  不创建任何 Dev attempt，也不自动进入 Day 12。

## 3. 允许与禁止范围

允许修改：

- `src/specflow/evaluation/dev_baseline.py`
- `tests/test_dev_baseline.py`
- `tests/test_cli_multi_agent.py`（仅产品默认值保留性测试）
- 本 task 与对应完成报告

禁止修改：

- `src/specflow/runner_multi.py`、Policy 默认值、Prompt、Retriever、EvidenceCollector、排序、阈值
- Dataset、Gold、Evaluator 语义、Provider、依赖
- Holdout 的任何 case/gold/output 内容
- 正式 Day 11 attempts、Day 12 内容、既有用户 Word 文件

## 4. 验收与验证

| 验收 | 自动化证据 |
| --- | --- |
| AC-077-1 | Multi payload 为 5；worker 传入的 `policy.repository.max_selected_files == 5` |
| AC-077-2 | 直接 `run_multi_agent()` 不传 Policy 时，EvidenceCollector 收到的上限仍为 10 |
| AC-077-3 | controlled decision 为 approved，config/report 同时保存产品默认 10 与基准有效 5 |
| AC-077-4 | 缺字段、非 5、默认值漂移、已有 attempts 均在 `launch_worker` 前失败 |
| AC-077-5 | focused、相关回归、全量 pytest、Ruff lint/format、`git diff --check` 通过 |

所有测试只用 mock/fake/临时仓库；不读取 Holdout，不调用真实 Provider。

## 5. 实现与验证结果

- RED：7 个 controlled-cap 新行为场景失败，产品默认值保留性场景通过。
- focused GREEN：8 passed；相关 Dev/Multi-Agent/Evaluation 回归：69 passed。
- 全量：812 passed、3 skipped、3 个既有 warning。
- Ruff lint、Ruff format、`git diff --check` 通过。
- 正式 Provider 未调用，正式 Dev attempts 仍为 0；下一门是重新冻结代码身份后完成学习者运行前预测。
