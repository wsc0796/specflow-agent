# T-072 — Execution Lanes and Bounded Admission 完成报告

开始日期：2026-09-13；验证与交付日期：2026-09-14。
状态：**实现及完整本地质量门通过，待外部独立审查。** 用户已批准唯一测试
钩子适配，原阻塞已通过仓库内完整回归解除；不自动关闭 T-072。

## 实施基线与开工门

- 仓库：`wsc0796/specflow-agent`。
- 工作目录：`C:/Users/50469/specflow-future-tasks-review-20260913`。
- 分支：`feat/t072-execution-lanes-bounded-admission`。
- implementation base：`009de77b54508fe53d1490b4a6dcc7929f767f0b`。
- 权威交接：`C:/Users/50469/AI_HANDOFF/specflow-t072-20260913.md`，已实际读取，
  未根据聊天重建。规范为 [T-072](../tasks/T-072-execution-lanes-and-bounded-admission.md)。
- PR #14 已合并，merge commit 即该 base，main 上 T-071 completion report 最新
  章节为 T-071 — CLOSED。开始时路径、branch、HEAD、clean status 和 main ancestry
  均核对通过，ancestry exit 0；用户指定本轮为新的 focused implementation session。
  因此开始时 **T-072 implementation gate satisfied**。
- 已阅读前置契约；本会话此前完整读取的未变前置文档经 Git 比对确认仍一致。
  本轮不修改 T-070/T-071 规范、breaker 实现或后续任务规范。
- final HEAD 在唯一 implementation commit 创建后记录于审查 PR 与交付回复，
  不以循环提交方式把本报告自己的 SHA 写入正文。

## 真实执行路径与修改面

| 位置 | 职责与 T-072 接入 |
| --- | --- |
| `coordinator/scheduler.py:MultiAgentScheduler.execute/_execute_stages` | 保留顺序 stage、stage 内并发上限、prior-output 传播；通过 lane 提交并跟踪本 stage 的 accepted Futures，失败后取消排队项并等待已派发项退栈 |
| `runner_multi.py:_run_multi_agent_owned` → `EvidenceCollector.collect` → `ToolExecutor.execute` | collection 外层一次提交到 local_tool，内部原同步工具不再嵌套提交同 lane |
| `runner_multi.py:_budgeted_executor` / `AgentRunner.execute` | Agent 本地处理及编排在 local_tool；真正 HTTP 在 provider lane。按实际执行内容分资源，Agent ID/role 不创建新 lane 或线程池 |
| `llm/providers/openai_compatible.py:OpenAICompatibleLLMClient.complete/_complete_once` | T-071 guard 接纳后才调用 attempt_executor 提交真实 HTTP；OPEN 在 submit 前拒绝。submit 位于 `_complete_once` broad transport catch 外 |
| `single_flight.py:SingleFlightCoordinator.claim/execute_owned` | ownership 先于新 lane 操作，只有 owner 调用 owned runner；follower 保持 bounded wait，不再次提交 collection/Agent/provider |
| `api_security.py:admit_single_flight` / `runs.py:RunService.create` | 原 Run permit、认证、allowlist、速率计数与审计身份保持不变 |
| `runner_multi.py:except ScheduleExecutionError/_validate_stage_results` | scheduler 的安全 SpecFlowError cause 原样分类；lane saturation 的失败 envelope 在 handoff 前 fail closed，保留 LANE_SATURATED |

生产文件限于新 `coordinator/execution_lanes.py`、既有 scheduler、runner_multi、
policy models/errors/validator，以及最小 provider submission adapter。测试集中在
新 `tests/test_execution_lanes.py`；另经用户明确授权，对现有
`tests/test_runtime_repair_integration.py` 仅适配一个取消测试的同步钩子，全部行为
断言保留。没有改 `resilience.py`、
retry/fallback/enricher、拓扑、schema、DLP、revision、Run API、依赖或 benchmark baseline。

## Lane ownership 与容量语义

`LaneManager` 仅支持 `local_tool` 和 `provider`，每条 lane 拥有固定大小的
ThreadPoolExecutor 与单独的有界等待 deque。默认两条 lane 各为 max_active=3、
queue_capacity=8；不启用可选 side_effect lane，必需产物写入保持原同步契约。

`ExecutionPolicy.lanes` 增加冻结的 ExecutionLanePolicy/LaneLimits，active 与 queue
必须为正整数，并进入完整 policy hash 与 hard-limit 校验。这些值属于既有 policy
配置的扩展，不改变 metrics.json 或 artifact 文件契约。默认 manager 是进程级共享
实例；显式运行时 manager 必须与传入 policy.lanes 匹配，否则返回安全配置不匹配
错误。自定义容量通过 `LaneManager(policy.lanes)` 构造后显式传给 owned runner，
不按每个请求创建无界的 policy→executor 注册表，不在运行中热切换共享容量。

独立使用的 scheduler 若未注入 manager，会按 max_parallel_workers 创建并关闭
自己的有界 manager；正式 multi-agent runner 注入共享实例。scheduler 不关闭其他
run 正在使用的共享 manager。固定 stage 较大时采用不超过其原并发上限的提交窗口，
没有动态 topology、通用 DAG、每 Agent 线程池或 caller-runs。

### accepted / rejected 与许可生命周期

- active 表示已占用执行槽的派发项，包含即将启动的 wrapper；started 另记真正开始
  执行 operation 的数量。queued 只包含尚未派发的有界 deque 项。
- 锁内完成 active 或 queue 容量接纳，且物理 submit 成功或已进入有界 queue 后才
  accepted；然后返回 LaneFuture。未获接纳时只抛 LaneAdmissionError，不暴露 Future。
- 容量耗尽、关闭或不可用的 lane 以 `LANE_SATURATED` / admission_rejected 明确拒绝，
  不作为 provider availability failure、retry exhaustion 或 wall-time 错误。
- 成功与 operation 异常先释放资源、发出 settled acknowledgement，再发布结果/异常。
  排队 cancel 从 deque 移除并释放 queue 槽；被派发后取消的 Future，仍等 wrapper
  确认不执行并退栈后才释放 active 槽。兼容 futures.wait/as_completed 的取消通知。
- 不把每个排队项都预先放入 ThreadPoolExecutor 的原生队列，因此反复排队取消不会
  隐藏累积无界 executor work items。同 lane 重入明确拒绝，避免自己等待自己。
- shutdown 先停止两条 lane 接纳，取消 queued/pending 项，再等待已派发 wrapper，
  所有 accepted Futures 结算。不能强制终止已启动的同步 Python work。

### submit 失败及取消

真实 ThreadPoolExecutor 可能先 enqueue 再因 Thread.start 抛错。失败时先撤销 job
执行权限并回滚 active；迟到 wrapper 看到 aborted 状态后直接退出，永不执行拒绝项。
失败 pool 在已接受 active work 退栈前暂停新派发，防止反复线程启动失败在原生队列
积累无界废项；退栈后清理旧 pool 队列并构造空 pool。不重新提交被拒绝的 operation。

该清理同样覆盖 KeyboardInterrupt/SystemExit：未接受的提交清理后原样传播取消；
已经 accepted 的排队项若在后续物理派发中被中断，异常进入其 Future，当前 job 和
其余已接受 Futures 仍结算。不是新的 retry、后台恢复任务或 durable job system。

## deadline、T-070 与 T-071 边界

- deadline 使用同一 lane monotonic clock；worker 在 operation 开始前检查。排队项
  到期显式 cancelled；scheduler 或同步 wait 超时会取消未开始项，再 drain 已启动项。
  physical settled 与 Future 的逻辑 cancel 分离，避免提前释放 owner 的共享容量。
- 同键 follower 完全绕过 owned work；不同 key 仍受共享 lane 接纳约束。显式注入
  不同 manager 的直接调用仅在已有 prepare_run.extra 中增加内部实例区分，默认
  direct/API key 形状不变；新增 lane policy 字段仍进入既有完整 policy hash。
- provider `with resilience.attempt(...)` 在 lane submit 外，因此 OPEN 为零 lane
  submission、零 HTTP。被 lane 拒绝或排队取消不会计入 breaker health。
- 对已开始 HTTP 的 deadline，adapter 单独保留真实 attempt 结果：先让不变的 T-071
  guard 观察真实成功或已分类失败并释放 probe，再向调用方报告 deadline 主结果。
  真实 429/503 不会被 deadline 覆盖漏计，成功 probe 也不会停留在 HALF_OPEN。
- 原 RetryStrategy/AgentRunner 的所有权和预算不变。新的 lane 错误不可重试。
  SemanticPlanEnricher 对失败调用沿用既有 degraded brief；其 fallback 不修改。
  因此富化阶段的 admission rejection 在 submission 边界和 lane 拒绝计数中明确，
  不被报告为真实 provider 成功；必需 Agent 遇到持续 saturation 时按该错误失败。

`LaneSnapshot` 仅提供两个固定 lane 名、submitted/started/completed/active/queued/
rejected/cancelled 计数与最近提交/开始/完成 UTC 时间。没有无界事件历史、request
内容、路径或 provider identity；未接入 T-073 artifact/metrics contract。

## 验收与独立复核

| AC | 当前测试证据 |
| --- | --- |
| AC-072-1/-2 | 两条 lane 的 active/queue 上限、无 Future 的明确拒绝、拒绝项不执行、真实 Thread.start 入队后失败与失败风暴 |
| AC-072-3 | 成功/Exception/BaseException 结算、queued cancel、已接受后派发失败/中断、deadline、shutdown，两种容量归还 |
| AC-072-4 | saturate local_tool/provider 后另一 lane 仍可用；无 side_effect 扩展 |
| AC-072-5 | 既有 scheduler 测试、固定 stage 顺序/并发上限/prior outputs；注入时钟下 queued 取消、started drain |
| AC-072-6 | 真重叠 owner/follower 无第二份容量，不同 key saturation；OPEN 零 provider submission 与零 HTTP |
| AC-072-7/-8 | T-070/T-071、CLI/API、policy、schema/DLP、完整回归及质量门，实际结果见下 |
| AC-072-9 | 本报告、聚焦 implementation commit、独立审查 PR，交付后停止 |

独立只读复核发现并复验解决两项 P2：

| 发现 | 红测试与修复 | 复核处置 |
| --- | --- | --- |
| T072-R1：物理 submit 抛错但拒绝项仍在原生 queue | 真实 Thread.start 失败复现；增加 aborted 权限、坏 pool 排空与禁止失败风暴积累；补 KeyboardInterrupt/SystemExit 及 queued dispatch 取消清理 | 已复验解决；中断原样传播，active 归零，拒绝项不执行，后续正常接纳 |
| T072-R2：deadline 覆盖真实 HTTP 结果导致 breaker 漏计 | deadline 后 200/429/503 三个反例先红；分开 caller deadline 与真实 attempt 健康结算，guard 本体不变 | 已复验解决；真实失败计一次，成功 probe 关闭，公开结果仍为 deadline |

最后独立定向复核为 **10 passed、24 deselected，0.32s**，没有剩余由这些修复
引入的 blocking finding；复核者未修改仓库或执行全量测试。本地完成不代表外部
最终审查通过，不自动登记 CLOSED。

## 验证记录

环境：Windows / Python 3.12.10，现有 `uv.lock`，`UV_FROZEN=true`；无 live provider。
日志目录：`C:/Users/50469/temp/specflow-t072-20260913/`，保留首次失败与后续通过记录。

- 初始 lane / policy 红测试：14 failed、5 failed；实现核心后通过。
- 新 scheduler/provider 参数接入前：2 failed / 20 passed；接入后通过。
- 组合验证发现冷导入循环、follower 测试容量不足；前者通过延迟导入现有
  SpecFlowError 修正，后者将场景容量改为覆盖固定三 Agent stage 并实际填满队列，
  保留不同 key 拒绝、follower 零额外提交断言。
- 一份跨夜旧日志记录 1 failed / 93 passed 和异常长耗时 41960.60s；未作为性能
  证据或通过结果。2026-09-14 重新执行得到 94 passed / 2.40s。
- scheduler 注入 clock 与真实提交失败/deadline 反例均先红后修复；最后 lane
  文件为 34 passed / 1.10s。
- 首次最终定向命令误写不存在的 `test_runtime_budget.py`，exit 4、0 tests；
  已改用实际存在的测试文件，预算/deadline 覆盖在 execution_policy、scheduler、
  CLI_multi_agent 等文件中，不为此删除或跳过测试。

| 本轮命令 / 检查 | Exit code | 实际结果 |
| --- | --- | --- |
| `uv run pytest tests/test_execution_lanes.py -q --tb=short` | 0 | 34 passed，0.74s；最后同步点修正后重跑 |
| 下列十三文件定向 pytest | 1 | 347 passed、1 failed、1 skipped、1 warning，37.78s；失败为原取消测试的 shutdown 同步钩子 |
| 最终 `uv run pytest -v` | 1 | 1008 passed、1 failed、3 skipped、3 warnings，57.52s；同一旧钩子失败，未跳过 |
| `uv run ruff check .` | 0 | All checks passed! |
| `uv run ruff format --check .` | 0 | 217 files already formatted |
| `uv run python scripts/check_secrets.py` 与新文件模式扫描 | 0 | 无发现 |
| `git diff --check` | 0 | 无空白错误 |
| 12-case benchmark / normalized baseline 比对 | 0 / 0 | 12 案例 passed，原 baseline 无差异 |
| `uv run python scripts/smoke_installed_wheel.py` | 0 | 新 wheel 与 standalone sdist-rebuilt wheel 各 10 项 PASS，非 editable 安装 |

```text
uv run pytest tests/test_execution_lanes.py tests/test_scheduler.py tests/test_execution_policy.py tests/test_provider_resilience.py tests/test_run_single_flight.py tests/test_runs.py tests/test_api_security.py tests/test_cli.py tests/test_cli_multi_agent.py tests/test_token_budget.py tests/test_runtime_repair_integration.py tests/test_runner_dlp.py tests/test_required_output_validity.py -v
uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/t072-validation-20260914 --baseline artifacts/t072-validation-20260914/baseline.json
git diff --no-index --exit-code benchmarks/results/mock-baseline.json artifacts/t072-validation-20260914/baseline.json
uv run python scripts/smoke_installed_wheel.py
```

smoke 仅在该命令进程设置 `PIP_CONFIG_FILE=NUL`、官方 PyPI 的 PIP_INDEX_URL、
空 PIP_EXTRA_INDEX_URL 和禁用 pip 版本提示；依旧按锁文件及 hash 安装，未改系统
配置、依赖或 smoke 脚本。两轮 wheel SHA-256 均为
`b9474340c6f01bb0f681056d677a1c9acadd163e1f0637770f7ba664156f2c7c`；sdist 为
`89f1e909c9c20e59bc636449e7b4374b802398e9d0113b18b0a51b87ae188f53`。
构建使用最终运行时代码、最后测试同步点和报告结算前的树，不是已发布版本。

全量三个 skip 为既有 Windows symlink 权限，三个 warning 为两项 pytest class
收集警告及 Starlette/httpx 弃用提示。没有新增 skip 或修改原测试断言。首次全量
还发现新 scheduler 拒绝测试过早释放任务的竞态，已在允许的 `test_execution_lanes.py`
中以“实际拒绝发生”的 Event 同步修正，最终全量只剩下面一个阻塞。

## 历史阻塞与未批准范围（适配前）

以下为用户首次选择暂不扩大范围时的记录；最新授权与复验见下一节。

唯一最终失败：
`tests/test_runtime_repair_integration.py::test_actual_worker_cancellation_waits_for_peer_and_keeps_permit`，
第 257 行等待 `unwinding` Event。该 Event 由测试 monkeypatch 的
`ThreadPoolExecutor.shutdown` 设置；共享 lane scheduler 正确地只调用
`LaneManager.cancel_and_wait` 等待本 stage 的工作，不关闭其他 run 共享的 pool，
因此旧同步钩子不会触发。未将该失败伪装为测试通过。

最小候选适配只将上述观察点替换为 LaneManager.cancel_and_wait，保持实际 worker、
peer、permit、follower、持久化取消状态及后续重新执行的全部断言。
Diff 保存在 `proposed-test-adaptation/adaptation.diff`。仓库外的同断言复验为
**1 passed、1 warning、1.18s，exit 0**；首次因外部副本找不到 test_runs helper
而 collection exit 4，加入当前 tests 的导入路径后完成。该副本不是仓库回归通过证据。

2026-09-14 用户明确选择“暂不扩大范围”。因此未修改原
`tests/test_runtime_repair_integration.py`，未应用候选 Diff。没有通过生产代码中的
无意义线程池 shutdown 来满足旧测试钩子；全量测试失败按原样保留。

AC-072-7/-8 的完整回归条件尚未满足，AC-072-9 的最终提交交付也未完成。
不能按交接要求创建“已完成”的 implementation commit 或发布通过门禁的 PR。
本轮只完成允许范围内的修复与验证，保留九个已知改动文件、基线 HEAD 不变且未暂存。
后续只有用户批准该最小测试适配或另行决定兼容方案后，才能继续处理此阻塞并重跑门禁。

## 批准最小测试适配后的交付复验

2026-09-14，用户在明确说明最小适配范围后回复“可以”，授权修改
`tests/test_runtime_repair_integration.py` 中唯一取消测试的同步观察点。
实际应用内容与此前仓库外验证的 Diff 一致：从 ThreadPoolExecutor.shutdown
切换到 LaneManager.cancel_and_wait，保留全部 worker/peer、permit、follower、
持久化取消结果及后续重新执行断言；本次未为测试适配修改运行时代码。

仓库内该测试新执行：**1 passed、1 warning、1.64s，exit 0**，记录在
`approved-adaptation.log`。这与此前仓库外副本的复验分开，不将历史失败改写成通过。
前一节的未批准状态属于历史，现在最终改动范围为十份文件。

| 批准后的检查 | Exit code | 实际结果 |
| --- | --- | --- |
| 原取消测试在仓库内复验 | 0 | 1 passed、1 warning，1.64s |
| 上列十三文件定向命令 | 0 | 348 passed、1 skipped、1 warning，30.55s |
| `uv run pytest -v` | 0 | 1009 passed、3 skipped、3 warnings，53.38s |
| `uv run ruff check .` | 0 | All checks passed! |
| `uv run ruff format --check .` | 0 | 217 files already formatted |
| `git diff --check` / 提交前 cached 检查 | 0 | 无空白错误 |
| 原测试 AST / 已批准 Diff 核对 | 0 | 所有原 assert 完整保留；实际适配与已批准提案 AST 一致 |
| 十文件范围与 secrets 检查 | 0 | 仅最终授权文件；暂存后覆盖新增文件扫描 |

最终日志分别为 `approved-adaptation.log`、`targeted-approved.log`、
`full-approved.log`；未覆盖历史失败日志。三个 skip 与三个 warning 仍为既有
Windows symlink 权限和 pytest class / Starlette-httpx 提示，未新增 skip。

本次批准后只有上述测试钩子和本报告改变，运行时代码、依赖与 benchmark baseline
不变。因此前文 12-case benchmark 和两轮 installed-wheel smoke 的本轮实施证据
仍适用；不将它们称为批准后重新执行。推送后的 CI 按最终提交另行核对并写入 PR。
本轮 Ruff 首次提示的是新改动行的 LF/CRLF 混合，统一为该文件原有换行形式后通过。

AC-072-7/-8 的完整回归门禁已满足。按交接书创建单个聚焦 implementation commit，
推送独立审查 PR，并在 PR 正文记录完整 final HEAD、base 和实际远端 CI。
这是实现交付，不等同于独立审查通过、PR 合并或 T-072 CLOSED；交付后停止。

## 已知限制与停止点

只保证单进程内固定两类资源；不提供多进程协调、持久化队列、重启恢复或强制
终止同步线程。默认共享 manager 配置固定，自定义容量须显式提供匹配的运行时
manager；不支持按请求无界扩建或热重配线程池。local_tool 槽包含 Agent 本地控制
栈等待 provider 的时间；provider 与 local_tool 各有独立容量，但复合调用仍存在
本地控制→provider 的依赖，不宣称不同运行链路完全无相互等待。

不声明真实 provider 质量、生产吞吐、时延或容量。没有新框架、DAG、asyncio、
process pool、Redis、后台 job、silent discard、caller-runs 或后续任务实现。
完成聚焦提交与审查 PR 后停止，不自动合并，不开始 T-073/cache/preflight/Java/M10。
