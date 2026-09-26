# T-080 完成报告 — Scheduler deadline cancellation audit

- 日期：2026-09-26；状态：COMPLETE；验证与审查通过，等待本地聚焦提交。
- 规格：[T-080](../tasks/T-080-scheduler-cancellation-audit.md)；实施计划：CANCEL-AUDIT-v1 §9。
- 基线：`c30d73811f479f88cd26fa7c3c703802a30dd348`；分支：`codex/t080-cancellation-audit`。

## 交付

deadline 超时仍以 `TIME_BUDGET_EXCEEDED` 失败、exit=3，不改变既有 accepted stages、
prior_outputs 或 Handoff 语义。新增的是可选 `scheduler_abort`：只有 scheduler deadline 中止后、
既有 `shutdown(wait=True, cancel_futures=True)` 正常返回，才包含 version、原因、逻辑 stage、
每个提交 Future 的取消尝试/结果、两次观察状态和 `cleanup_completed=true`。

Future 状态只表示调度事实：`cancelled_before_start`、`running`、`finished_unvalidated` 或
`pending`。取消判断优先于 done；cancel 返回 false 不推断 running；已结束结果也不读取或接受为
业务成功。executor 主动抛出的 `CancelledError` 保留普通执行异常路径，不冒充真正取消。

runner 在 `_run_and_accumulate` 将 scheduler 局部 index 改为可信逻辑 stage，并验证 audit 中的
agent key 属当前 registered stage。失败 manifest 和 run/coordinator trace 写同一个安全对象；
`agent-outputs.json` 不写取消占位，不能成为下游输入或 Handoff。没有增加取消 API、线程强杀、
retry、Provider/预算/Prompt/Schema/Evaluator/topology 变更或依赖。

## 实际 Artifact 对照

对照位于本地备份根 `D:\Documents\ChatGPT\一个月冲刺\specflow-repair-backups\2026-09-26-T080-cancellation-audit\artifact-comparison.json`。
修前使用 `c30d738` 的 git archive 临时源重建同一 Stage1 timeout；修后使用实际 ThreadPoolExecutor
和受控 Future 状态的 T-080 集成测试。修前只证明当时 Artifact 无取消审计；修后测试才证明真实
deadline/cancel/shutdown 到持久化的完整链路。

| 观察 | 修前 | 修后 |
| --- | --- | --- |
| error / stages_completed | TIME_BUDGET_EXCEEDED / 1 | 相同 |
| manifest scheduler_abort | 缺失 | version=1、deadline_exceeded、stage_index=1、cleanup_completed=true |
| Future 处置 | 不可判断 | design running→finished_unvalidated；risk/test queued→cancelled_before_start |
| run trace | 无 scheduler_abort | 与 manifest 同源 |
| agent outputs | 仅 Stage0 | 仍仅 Stage0 |

## 验证

所有 pytest 通过隔离包装运行：导入前删除 `SPECFLOW_LLM_*`，阻断同步/异步真实 HTTPTransport，
并检查主进程及已核对临时 Mock worker 的计数为 0。未读取凭证、Holdout、正式 Dev 或 raw attempts；
不修改持久环境。`uv --offline` 只用于依赖解析，非网络沙箱。

| 标签 | 结果 |
| --- | --- |
| focused | 8 passed；初版测试通过但审查指出证据不够确定 |
| related | 139 passed、1 skipped、1 warning |
| review-fix | 8 passed；Event/Barrier 受控真实取消与真实 Stage1 Artifact 链 |
| full | 866 passed、3 skipped、3 warnings，144.44s；主/子 HTTP=0 |
| full-final | 866 passed、3 skipped、3 warnings，98.89s；主/子 HTTP=0 |

最终 `ruff check .`、`ruff format --check .` 和 `git diff --check` 均通过。skip 均为既有 Windows
symlink 权限限制；warnings 为既有 TestStrategy 收集与 Starlette/httpx 弃用提示；未新增 skip/xfail。
`full-final` 在审查修正后的测试上运行，是本次最终全量证据；先前 `full` 仅作为修正前历史记录。
T-080 的 Specification/Design/Tasks/Verification 经 Adaptive SDD 结构与追溯校验，结果为
0 errors、0 warnings。

| AC | 状态 | 证据 |
| --- | --- | --- |
| AC-001 | PASS | 真实 ThreadPool max_workers=1：running 未取消、queued cancel=true，cleanup 后才抛错 |
| AC-002 | PASS | 全部运行、已完成、主动 CancelledError 三种反例 |
| AC-003 | PASS | 真实 Stage1 deadline，trusted stage=1、同源 trace、outputs/Handoff 隔离 |
| AC-004 | PASS | pre-submit deadline agents=[]；write/size 失败无 `_COMPLETE`；focused/related/full 与静态检查 |

## 审查裁决与限制

独立只读审查先发现两项 Important 测试问题：短 deadline 定时器没有确认 worker 状态；Stage1
测试手工构造 audit 而非实际中止。已用 Event/Barrier + 受控 as_completed timeout 修复，添加真实
Stage1 worker/queued sentinel/敏感 marker，并以 `review-fix` 验证。审查未发现生产实现的 Critical
或 Minor 问题。

本批仍不能强杀运行中的同步线程；已发送请求或已启动 callable 必须等收口。没有用户主动取消入口，
所以 timeout 不是 RUN_CANCELLED。shutdown 自身失败时不会伪造 cleanup_completed，但不扩展成统一
清理故障框架。提交耗时与 Future 多线程观察并非全局原子快照；字段只描述中止处理期间的实际观察。

启动时 17 个 dirty 学习文件已备份并逐字节保持；原 Day14 越界记录、learner PARTIAL、旧文档/Word
和 raw attempts 均未改动或暂存。只提交 T-080 产品/测试/规格/报告文件，不推送、不发布、不创建 PR。
回退使用 `git revert <引入本报告的提交>`，无数据迁移。
