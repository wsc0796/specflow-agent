# T-080 — Scheduler deadline cancellation audit

- 日期：2026-09-26；状态：FROZEN / IMPLEMENTED；模式：BUGFIX。
- 授权：用户要求按 `CANCEL-AUDIT-v1` 第 9 节实施；该指令就是本次 PATCH 授权。
- 基线：`c30d73811f479f88cd26fa7c3c703802a30dd348`；分支：`codex/t080-cancellation-audit`。

## Specification

当 scheduler 因 deadline 中止时，当前失败 Artifact 只有 `TIME_BUDGET_EXCEEDED`，不能可靠区分
排队 Future 是否真正取消、哪些已经运行，或清理是否完成。本任务补充有界调度中止审计，不改变
失败语义：`workflow_state=failed`、exit=3、主错误仍为 `TIME_BUDGET_EXCEEDED`。

### REQ-001 — 真实 Future 状态审计

deadline 中止后，对每个已提交 Future 记录 agent map key、是否尝试取消、真实 cancel 返回值、
中止观察状态与清理后状态。状态仅可为 `cancelled_before_start`、`running`、
`finished_unvalidated`、`pending`。取消判断优先于 done；`cancel=False` 不推断为 running。
主动抛出 `CancelledError` 是普通执行异常，不生成 deadline 中止审计。

### REQ-002 — 清理和接受集合保持原义

保留 `shutdown(wait=True, cancel_futures=True)`；仅在其正常返回后声明 cleanup_completed=true。
中止 stage 不追加进 accepted stages 或 prior_outputs，不生成取消占位 agent output/Handoff，也不把
Future done 推导成业务成功或 schema_validated。提交前已过期时 `agents=[]`。

### REQ-003 — Artifact 可信传播

新增可选 `scheduler_abort`，与 T-078 failure_context 独立。scheduler 只使用提交 map key；runner
将 scheduler 局部索引替换为可信逻辑 stage，并校验这些 agent 均为本阶段注册 identity。manifest
和 run/coordinator failure traces 写入相同审计；不写 Future 对象、正文、异常文本、路径、usage 或秘密。

### REQ-004 — 范围与兼容

只改 `src/specflow/coordinator/exceptions.py`、`scheduler.py`、`runner_multi.py`，新建
`tests/test_scheduler_cancellation_audit.py`、本规格和报告。保留 T-079 预算、Provider、retry、
Prompt、Schema、Evaluator、拓扑、默认并发、用户取消 API 和状态机。仅使用临时 Fake/Mock，
不读 Holdout/Dev 或调用真实 Provider；不新增依赖。

### AC-001 — 队列与运行任务

给直接 scheduler 更少 worker，deadline 时一个 Future 已运行、另一个排队：排队任务 cancel 成功且
sentinel 不运行；运行任务不标 cancelled；shutdown 完成后才抛出带 audit 的错误。

### AC-002 — 已开始和已完成 Future

全部已启动时没有虚假的 cancel 成功；已完成 Future 仅为 finished_unvalidated。主动
`CancelledError` 不带 scheduler_abort。

### AC-003 — Runner Artifact

Stage0 已接受、Stage1 timeout 时 audit stage_index=1、stages_completed=1、Synthesis/Review 不运行；
manifest 与 failure trace 同源，agent outputs 只有已接受 Stage0，完整性文件有效且无敏感 marker。

### AC-004 — 边界

提交前 deadline 过期时 agents=[]；写盘失败/超限不伪造 `_COMPLETE`；T-078/T-079、Handoff、成功、
预算、revision 相关回归不退化。新测试 RED→GREEN，隔离相关与全量 pytest、Ruff/diff 通过。

## Design

REQ-001/REQ-002：`ScheduleExecutionError` 获得可选不可变 `SchedulerAbortAudit`。scheduler 在
TimeoutError 后对每个已提交 Future 调用 cancel，一次性记录 cancel 返回及状态；finally 完成既有
shutdown 后，再写入清理后的状态并抛出审计异常。普通执行异常不使用此类型。
REQ-003：_run_and_accumulate 捕获并把局部 stage 0 改为调用方逻辑 stage；runner 将可选对象传入
失败 Artifact 和 trace builder。REQ-004：新增字段仅为可选审计，不触及其他产品边界。

`scheduler_abort` 格式为 version=1、reason=deadline_exceeded、stage_index、agents、
cleanup_completed=true。每个 agent 只有 agent_id、cancel_attempted、cancel_succeeded、
state_during_abort、state_after_cleanup。无中止时该字段缺失，原 ScheduleExecutionError(message)
调用兼容。回退为 `git revert <本提交>`，无数据迁移。

## Tasks

- [x] **TASK-001 — RED cancellation evidence**：REQ-001、REQ-002、REQ-003、REQ-004；AC-001、AC-002、AC-003、AC-004；新增直接 scheduler
  与 runner Artifact 反例，隔离运行确认旧实现没有 scheduler_abort。
- [x] **TASK-002 — bounded propagation**：REQ-001、REQ-002、REQ-003；AC-001、AC-002、AC-003；实现不可变审计、清理后
  传递和逻辑 stage 重绑定，focused GREEN。
- [x] **TASK-003 — regression closeout**：REQ-004，AC-004；相关/全量验证、报告、精确暂存、本地提交；
  不推送，也不更新既有 learner 原文。
