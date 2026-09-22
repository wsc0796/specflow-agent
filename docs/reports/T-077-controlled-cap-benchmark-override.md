# T-077 controlled-cap benchmark override 完成报告

- 日期：2026-09-22。
- 状态：`IMPLEMENTED_AND_VERIFIED / FORMAL_RUN_PENDING`。
- 规格：[T-077](../tasks/T-077-dataset-v1-controlled-cap-benchmark-override.md)。

## 交付

1. Dataset v1 Multi-Agent worker 现在从 `DEFAULT_POLICY` 派生局部 Policy，仅把
   `repository.max_selected_files` 设为 5，再显式传给 `run_multi_agent`。
2. 普通产品入口与 `runner_multi.py` 未修改；不传覆盖 Policy 时，EvidenceCollector 的产品有效上限
   仍为 10。
3. run config/report 分开记录
   `product_default_multi_agent_limits.max_selected_files=10` 与
   `effective_multi_agent_limits.max_selected_files=5`。
4. `controlled-cap-at-5` 现在是 Day 11 官方运行唯一可批准实验；as-is 记录保留但不能启动官方运行。
5. 缺失/非 5/默认值漂移配置、runtime/policy 漂移和已有 attempts 均在产品子进程前失败。

## TDD 与验证证据

| 检查 | 结果 |
| --- | --- |
| RED | 7 failed、1 passed；失败点分别为 payload 仍为 10、缺少双值字段、controlled 状态仍需 Patch |
| focused GREEN | 8 passed |
| 相关 Dev/Multi-Agent/Evaluation 回归 | 69 passed |
| 全量 `uv run --no-sync pytest -v` | 812 passed、3 skipped、3 warnings，47.05s |
| `uv run --no-sync ruff check .` | passed |
| `uv run --no-sync ruff format --check .` | 216 files already formatted |
| `git diff --check` | passed |

三个 skip 均为 Windows symlink 权限条件；三个 warning 与既有 Pytest collection/Starlette
deprecation 一致。测试只使用 mock/fake/临时仓库；真实 Holdout 未读取，正式 Provider 未调用。

## 边界与下一门

未修改产品默认 Policy、`runner_multi.py`、Prompt、Retriever、EvidenceCollector、排序、阈值、
Dataset、Gold、Evaluator、Provider 或依赖；未创建正式 Dev attempt，未进入 Day 12。

代码聚焦提交后，需要把 Day 11 ignored run config 记录为 `controlled-cap-at-5` 并重新冻结新的
runtime identity。随后只收集学习者的 Q1–Q3 运行前预测；没有精确口令 `RUN DAY11` 时不得启动
唯一一次正式 20 Dev。
