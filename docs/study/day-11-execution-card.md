# Day 11 执行卡 — Multi-Agent 当前版本 Dev Baseline

- 日期：2026-09-14；唯一项目：`D:\Documents\ChatGPT\一个月冲刺\specflow-agent`。
- 阶段：Measure；模式：`REVIEW`；状态：`ADAPTER VERIFIED / FORMAL RUN BLOCKED ON FAIRNESS`。
- 唯一工程目标：用同一 20 Dev、固定源码快照、`deepseek-flash`、requirement-only 投影和报告语义，
  运行一次 Multi-Agent 当前版本 baseline，形成 Multi-Agent Dev Report。
- 正式运行门：公平性选择未完成前保持 0 attempted。
- 恢复入口：[CURRENT](CURRENT.md)；规格：[T-076](../tasks/T-076-dataset-v1-multi-agent-dev-adapter.md)。

## 固定身份

- Day 10 adapter commit：`53287306bc1d4aaa2e1e0ff493f520c81096f0a4`。
- Day 10 result commit：`271d409cb0164ffa998a47b164abed3682c60801`。
- Dataset v1 freeze：`bf77d19455cb989984dc4f909e6e7ca4b4f91aaf`。
- 目标仓库/Gold revision：`08e5a66f8ea8216433c72744adab92aa07d99c45`。
- Provider/model：DeepSeek OpenAI-compatible / `deepseek-flash`。
- Dataset → 产品投影：`requirement` only；Case ID/attempt ID 仅作 harness 关联。
- 源码 profile：`authorized-source-v1`，复用 `data/day10/target/`。
- Prompt/Policy/effective limits：由 Day 11 运行代码身份与 config 显式冻结；不从名称推断。

## AI 可先完成

- [x] 核对仓库根、Git/Word 基线和全部强制启动资料。
- [x] 只读闭合 Multi-Agent 输入、LLMRequest、Provider、Prompt/Policy、终态、usage/retry、artifact 链。
- [x] 冻结 T-076 最小 task spec 与测试边界。
- [x] 完成请求观察、Multi worker、attempt/report、输入隔离和单次运行门的 TDD 实现。
- [x] 运行 focused/相关/全量质量门并生成完成报告。
- [x] 生成 Day 11 prepare-only 目录、报告骨架、机器记录和代表 Case Review 包。

## 学习者保留判断

1. 按 D001 → D015 → D018 → D017，每次只 Review 一个 Case；三句话回答实际可见 Context、
   全部必要属性、最早错误层。回答后给【正确答案】、差异和 evidence path。
2. 选择 `current-topology-as-is` 或 `controlled-cap-at-5`。前者保持 5/10 并标混杂与
   not_comparable；后者需要另行 PATCH，不能直接运行。

## 禁止范围

- 禁止读取/执行 `docs/study/datasets/v1/holdout.json`；仅允许 manifest 元数据。
- 不改 Dataset/Gold/Prompt/检索策略/Context 限制/阈值/Evaluator 语义或 DeepSeek 模型。
- 不提前修 Legacy Context 接线，不实现 RAG/Embedding/Vector/Hybrid/Rerank，不安装依赖。
- 不把旧 12 条、calibration、Mock 回归或 Legacy 结果当 Multi-Agent 正式 Dev。
- 不删除、覆盖或暂存 `docs/study/SpecFlow-Agent-30天能力战役-更新执行版.docx`。
- 正式 20 Dev 只运行一次，不自动重跑。

## 恢复检查点

当前 HEAD 为 Day 10 result commit `271d409c`；工作区启动时只有指定 Word 未跟踪。
Day 10 正式结果为 20/20 attempted、20 completed/degraded、AI task success 2/20、最终请求
Gold coverage 0/23、Token coverage 16/20/not_comparable。Collector 共 744 excerpts，实际 60 个
Legacy Worker 请求均无 Repository Evidence；最早问题在 Context 接线，不能归因成 Collector 全败
或 DeepSeek 不会读代码。Day 11 尚未正式运行。

T-076 当前质量门为 807 passed、3 skipped、3 known warnings；Ruff lint/format、diff check、
Dev/fixture 冻结边界和 Word 排除检查通过。prepare-only 配置已复用 deepseek-flash、20 ID、
08e5a66 源码快照与 v1 Evaluator/report 身份；adapter 已聚焦提交，运行身份已冻结且 runtime
代码面干净，formal attempts 仍为 0。
