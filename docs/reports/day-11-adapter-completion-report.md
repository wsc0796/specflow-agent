# Day 11 — T-076 Adapter 完成报告

- 日期：2026-09-14；状态：`IMPLEMENTED_AND_VERIFIED / FORMAL_RUN_PENDING`。
- Dataset freeze：`bf77d19455cb989984dc4f909e6e7ca4b4f91aaf`。
- 目标源码/Gold revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- Day 10 adapter/result：`53287306bc1d4aaa2e1e0ff493f520c81096f0a4` /
  `271d409cb0164ffa998a47b164abed3682c60801`。
- 本次 adapter commit：由
  `git log -1 --format=%H -- docs/reports/day-11-adapter-completion-report.md` 定位。
- 规格：[T-076](../tasks/T-076-dataset-v1-multi-agent-dev-adapter.md)。

## 交付

1. `run_multi_agent` 新增默认关闭的请求观察边界；Coordinator enrichment 与每个 Agent receiver
   分开计数，保存 budget/Prompt 已确定后的不可变 messages/参数副本。observer 异常不改变
   Provider request、响应、原异常或重试。
2. Dataset v1 harness 增加 Multi-Agent prepare/worker/attempt/report 分支，复用 Day 10 的 20 ID、
   requirement-only 投影、`authorized-source-v1` 快照、Provider/model 和公共 Policy。
3. 冻结有效接线：max_selected_files=10、evidence chars=80000、tool calls=20、Agent max tokens=3000、
   enrichment max tokens=1024、temperature=0、Agent/Provider retry=0、revision max=1。
4. artifact observation 与 contract/task/fact/citation/safety/token 分面保存。旧 Mock portfolio contract
   不静默冒充 live Dataset profile；metrics 不含 enrichment usage，完整成本保持 unknown/not_comparable。
5. 公平性门支持两种记录：as-is 才可运行且自动列混杂维度；controlled-cap-at-5 只记录
   requires_separate_patch，不能借本 task 改产品限额。
6. 代表 Case 原始材料包和 Day 12 可消费机器骨架已准备；AI 内容不提升 learner ownership。

## TDD 与验证证据

| 检查 | 结果 |
| --- | --- |
| RED | pytest 收集失败：`_RequestObservingLLMClient` 尚不存在 |
| focused GREEN | 35 passed |
| 相关 Dataset/Evaluation/Runner/Coordinator 回归 | 72 passed |
| 全量 `uv run --no-sync pytest -v --basetemp data/day11-full-pytest` | 807 passed、3 skipped、3 warnings，60.02s |
| `uv run --no-sync ruff check .` | passed |
| `uv run --no-sync ruff format --check .` | 216 files already formatted |
| `git diff --check` | passed |
| Dev/fixture 相对 bf77d19 | unchanged |
| prepare-only | 20 planned / 0 attempted / 20 not_started，deepseek-flash，cap=10，fairness pending |
| pending fairness 执行门 | exit 2；`attempts.json` 不存在 |

完整 pytest 日志位于 `data/day11/pytest-full.log`。三个 skip 和三个 warning 均为既有 Windows
symlink/pytest/deprecation 项；没有新增 skip/xfail。测试只使用 fake/mock 与临时仓库，不是正式 Dev。

## 边界

未读取或运行 Holdout，未调用正式 Provider，未改 Dataset/Gold/Prompt/检索/Context 限制/Policy/
阈值/Evaluator/模型，未实现 RAG/Vector/Hybrid/Rerank，未安装依赖，未触碰或暂存 Word。

本 adapter 已聚焦提交，prepare-only 配置已在未读取 `.env`、未输出凭证的条件下冻结
`deepseek-flash` 与干净 runtime code identity。正式运行还需完成代表 Case Review 与公平性判断；
随后只运行一次 20 Dev，完成语义报告与独立结果提交。
