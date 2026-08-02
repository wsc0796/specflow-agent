# Phase 6A — 三管道公平性协议(草案,Phase 6F 前冻结)

## 管道定义

| 管道 | 标识 | 现状 |
| --- | --- | --- |
| B1 | Single Agent | ⚠️ **代码库中无独立 single-agent 模式**(CLI 仅 legacy/multi-agent)。需 DECISION:实现 1-worker 变体,或明确定义 B1=legacy 3-worker 降级参数 |
| B2 | Legacy 3-worker | `specflow.runner.run`(analyze/generate/review),已冻结为 A/B 基线 |
| B4 | 6-role Runtime | `specflow.runner_multi.run_multi_agent`(Phase 1-3 接线) |

## 公平条件(全部相等)

1. repository commit:bc76214(冻结后 EVALUATION_BASE_COMMIT)
2. model/provider:同一 provider 配置(Phase 4B 批准后)
3. 参数:temperature 等推理参数一致;provider timeout 一致
4. evidence:同一 fixture 仓库、同一 evidence 收集策略
5. 工具:同一只读工具集(如启用)
6. token 预算:同一 Run 级 token 预算(Phase 4 定案后)
7. wall-clock:同一 max_wall_time_seconds
8. 输出 Schema:同一统一输出 Schema(见 unified-output-schema-draft.md)
9. 失败规则:同一 fail-closed 规则与错误码

## 执行纪律

- 运行顺序打乱(避免顺序偏差),每 case × pipeline 独立目录。
- 执行与评分分离:生成产物的窗口不得做最终盲评(6H 独立)。
- 任何管道运行失败不重试补分;失败计入 budget_violation/run_success。
- 冻结后不得为单条管道调整模型/预算/工具/评分/答案。
