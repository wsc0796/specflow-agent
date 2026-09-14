# T-076 — Dataset v1 的 Multi-Agent Dev 最小评测适配

- 日期：2026-09-14；version：`v1`；status：`IMPLEMENTED_AND_VERIFIED / FORMAL_RUN_PENDING`。
- 授权：用户明确要求完成 Day 11 中所有不依赖公平性选择的 AI 工程工作，包括
  Multi-Agent adapter、实际请求观察、attempt 报告、输入隔离、测试、报告骨架和机器记录。
- 正式 20 Dev 运行仍由公平性判断门控制；本 task 不替学习者选择 `5 vs 10`。
- 依据：[Day 11 执行卡](../study/day-11-execution-card.md)、
  [Day 11 Gap Trace](../study/evidence/day-11-gap-trace.md)、
  [T-075](T-075-dataset-v1-legacy-dev-adapter.md)。

## 1. 问题与目标

Day 10 只留下 plan-only Multi-Agent 镜像。当前 `run_multi_agent` 没有实际
`LLMRequest` 观察钩子，Dataset v1 harness 又明确拒绝 Multi-Agent 执行，因此无法在不泄露
Evaluator 标注的前提下记录 Day 11 当前版本 baseline。

本 task 的唯一目标是把现有 20 Dev 隔离协议扩展到 Multi-Agent 当前版本：复用同一
requirement-only 投影、固定源码快照、Provider/model 和逐 attempt 口径，记录全部实际请求与
当前 artifact/usage/retry 事实。产品 Prompt、检索策略、Context 限额和 Evaluator 语义保持原样。

## 2. 行为需求

- **REQ-076-1 输入与快照复用**：只使用 T-075 的显式 `manifest.json` + `dev.json` loader、
  `authorized-source-v1` 快照和 requirement-only 产品投影。子进程不得接收 Gold、answerability、
  expected_properties、forbidden_claims、study 路径或 Dataset 路径。
- **REQ-076-2 请求观察**：`run_multi_agent` 增加默认关闭的只读观察钩子，记录 budget/Prompt
  已经确定后的不可变 `LLMRequest` 副本及 receiver/call index；Coordinator enrichment 与六类
  Agent 必须分 receiver。observer 失败不得改变原请求、异常、调用次数、重试或终态。
- **REQ-076-3 当前版本执行**：Multi-Agent 子进程按当前接线调用 `run_multi_agent`，保留
  `max_selected_files=min(10, policy...)`、max evidence chars/tool calls、temperature、token、
  retry、revision 和 artifact 行为；不得通过 adapter 静默改成 5。
- **REQ-076-4 attempt journal**：20 个固定 ID 各计划一次；开始产品调用前落盘 started，随后记录
  returned/execution_error/interrupted、exit code、wall time、产品终态、artifact locator、观察完整性
  与各 Evaluator 的独立状态；已有 attempts 禁止覆盖或自动重跑。
- **REQ-076-5 报告语义**：contract_run_success、Multi-Agent artifact observation、task_success、
  fact evidence coverage、safe abstention、citation support、Token completeness 分开。现有
  `portfolio_multi_agent_mock@5f2815d` 不静默冒充新的 live Dataset profile；无适用冻结 profile 时
  contract verdict 为 `unknown`/`N/A` 并说明原因。
- **REQ-076-6 usage/retry 诚实性**：请求观察记录实际 Provider 尝试；当前 Provider、
  SemanticPlanEnricher 和 AgentRunner 的 retry 接线按源码列出。`metrics.json` 未包含 enrichment usage
  时，完整 Token 成本必须为 unknown，比较为 not_comparable，不能把 agent-only subtotal 当全量。
- **REQ-076-7 公平性门**：正式执行前必须记录学习者选择。保留 10 时，把 selected-file cap 差异
  列为派生/混杂因素，并把受影响的跨路径维度标为 not_comparable；选择统一到 5 时只记录
  `requires_separate_patch`，不得使用 T-076 授权修改产品限额。
- **REQ-076-8 单次正式运行**：默认只 prepare/freeze/record decision；只有身份已冻结、公平性为
  approved、工作区代码身份一致且没有 attempts 时才允许一次正式 20 Dev。测试不得运行真实 Dev。

## 3. 允许与禁止范围

允许文件：

- `src/specflow/runner_multi.py`：最小、默认关闭的请求观察钩子。
- `src/specflow/runner.py`：仅把共享观察记录的说明从 Legacy 专用改为通用；不改 Legacy 行为。
- `src/specflow/evaluation/dev_baseline.py`、`scripts/run_dev_baseline.py`：Day 11 prepare/worker/
  attempt/report 分支与公平性门。
- `tests/test_cli_multi_agent.py`、`tests/test_dev_baseline.py`：观察非干扰、隔离、门禁和报告口径。
- 本 task、Day 11 study/evidence/report/CURRENT 文件。

禁止修改 Dataset/Gold/calibration、Prompt、EvidenceCollector、Context 组装、Policy 默认值、
`max_selected_files` 的产品接线、阈值、Evaluator 语义、Provider、依赖和 Word 文件。禁止读取或
运行 Holdout，禁止实现 RAG/Embedding/Vector/Hybrid/Rerank。

## 4. 验收标准与测试边界

| 验收 | 测试/检查 | 预期证据 |
| --- | --- | --- |
| AC-076-1 | 用 fake Provider 运行真实 Multi-Agent AgentRunner 分支 | 观察 6 enrichment + 6 agent 请求；Repository Evidence 只进入 repository analyst |
| AC-076-2 | observer 抛错、Provider 抛错 | 原 request 只转发一次；原异常/终态不被 observer 改写；不产生额外 retry |
| AC-076-3 | 合成 Dataset/临时 Git fixture | Multi payload 只有公共 7 字段，`max_files=10`；Evaluator marker 不进入 payload/messages |
| AC-076-4 | prepare/freeze/run 的 mock harness | 正式运行前 fairness pending 阻断；保留 20/0/20；批准 as-is 后逐 attempt journal 工作 |
| AC-076-5 | 选择 equalize-at-5 | 状态为 requires_separate_patch，仍阻断执行，不修改 runner 限额 |
| AC-076-6 | 合成 Multi artifact/metrics/request observation | product/artifact/semantic/token 字段分开；enrichment usage 缺失使 full_total unknown/not_comparable |
| AC-076-7 | CLI 旧入口回归 | 默认 Legacy 行为保持；Multi 必须显式 mode/output，不能运行 Holdout |
| AC-076-8 | 固定数据/源码/Prompt/Policy 身份检查 | 变更在产品调用前失败；已有 attempts 不覆盖 |

验证顺序：先观察 RED；再 focused tests；相关 Multi-Agent/Legacy 回归；随后全量 pytest、Ruff
lint/format、`git diff --check`、冻结 Dev 和 Word 边界检查。所有测试只用 mock/fake/临时仓库。

## 5. 系统模型与风险

- 对象：`MultiAgentDevAttempt` 与 `RequestObservation`；均为评测侧运行证据，不是产品业务状态。
- 真相源：冻结 Dev、固定源码快照、实际 `LLMRequest`、逐 attempt journal、产品 artifact。
- 生命周期：prepared → identity_frozen → fairness_decided → started → returned/error/interrupted →
  semantic_review_pending；正式运行只允许一次。
- 不变量：输入不含标注；observer 不干扰产品；快照/模型/策略不漂移；失败和未知不被成功过滤；
  Holdout 永不打开；Word 不触碰。
- 影响契约：`run_multi_agent` 新增可选参数，默认行为兼容；Dev CLI 新增显式 mode 分支。
- 已知风险：并行 Specialist 请求的观察到达顺序不固定；用 receiver + per-receiver call index 关联，
  不把全局顺序写成语义合同。完整 Token ledger 仍不在本 task 内。

## 6. 公平性实验定义（待学习者判断）

1. **current-topology-as-is**：Legacy=5，Multi-Agent=10；忠实测“当前两条产品路径”，但文件上限是
   拓扑之外的混杂因素。Evidence/Context、Fact coverage、task success、citation、安全拒答与受其影响的
   latency/token 不能作纯拓扑因果比较，只能给各自 baseline 和明确 `not_comparable`。
2. **controlled-cap-at-5**：把 Multi-Agent 也限制为 5；更接近单因子拓扑实验，但不再是“当前版本原样”
   baseline。必须另冻最小 task spec 和测试边界并取得明确 PATCH 批准；T-076 不实现。

正式 20 Dev 在该判断前保持 0 attempted。

## 7. 实现与验证结果

- 请求观察覆盖 Coordinator enrichment 和真实 AgentRunner 分支；observer 默认关闭、异常非干扰。
- Day 11 prepare-only 已生成：20 planned / 0 attempted / 20 not_started；fairness pending 时执行
  返回 exit 2 且不创建 attempts。
- RED：测试收集因 `_RequestObservingLLMClient` 不存在而失败；GREEN：35 focused passed。
- 相关 Multi-Agent/Evaluation 回归：72 passed。
- 全量质量门：807 passed、3 skipped、3 known warnings；Ruff lint/format、diff check、冻结数据和
  Word 边界检查通过。
- 正式 Provider 未调用；该结果只证明 adapter/观察/门禁，不是 Multi-Agent Dev 质量结论。
