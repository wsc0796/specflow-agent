# T-070 — Run Single-Flight and Early Idempotency 完成报告

> **当前状态（2026-09-13）：T-070 — CLOSED。** 本次按用户授权，在核对已合并
> main、A01、组合回归、独立复审处置和 CI 后登记关闭，依据见文末关闭章节。
> 以下初始交付/A01 待评审状态及验证数字保留为历史，不改写成当时已经关闭。

初始交付：2026-09-11；A01 修复更新：2026-09-12。状态：实现交付待评审。本地验证结果见下，不自行宣布独立验收通过。

## 实现基线、分支与远端状态

- 仓库：`wsc0796/specflow-agent`。
- IMPLEMENTATION_BASE：`826d3a7257ad903bc09b0d2d6635a3449576a3ce`。
- SPEC_SOURCE：`02c1d3fe9bcd8c95d6bb7cf3959328844598e473`。
- TARGET_BASE_BRANCH：`docs/m10-runtime-assurance-spec`。
- 实现分支：`feat/t070-run-single-flight`。
- 工作区：`C:/Users/50469/specflow-agent-t070`，创建时干净。
- 主工作区的未跟踪文件 `docs/reports/live-provider-evaluation-v1.md` 保留原样；其他工作区未修改。
- 开始前核对远端全部 PR、分支、本地历史及报告，未发现已有 T-070 实现。
- PR #6 尚未合并，本次是依赖它的独立堆叠 PR，不向父分支写代码，不合并或 APPROVE。
- 任务执行期间父分支更新到 `02556b90aeec5fcc55dd7426bb3098dcf1e788f4`。只新增一个 M10 文档提交、修改七个 Markdown 文件；`src/`、`tests/`、依赖、AGENTS、M9 与 T-070 契约均无变化。
- **同步需求单独记录：** 实现分支尚未吸收父分支的上述文档提交，仍保留已经验证的 IMPLEMENTATION_BASE；未自动 merge/rebase。合并评审时由维护者决定何时同步或在父 PR 合并后 retarget。当前 PR 的三点比较基线仍是 `826d3a7`，只计算 T-070 增量。
- T-070、M9 任务和冻结报告与 SPEC_SOURCE 比较无差异。M10 实现门不用于阻塞或授权本任务。
- 最终实现 SHA 与 PR 链接在提交后记录于 PR 和交付回复，本报告不要求包含自身提交 SHA。
- 本轮 A01 修复起点：`7856e3a1bff737282f7cf9cece2e38f2fe7895f9`；在用户确认分离结果与文件解析方案后追加一个聚焦修复提交，不改写已发布历史。

## 修改范围与调用链决定

| 文件 | 变化与必要性 |
| --- | --- |
| `src/specflow/single_flight.py` | 早期快照与规范化键、唯一线程安全协调器、owner/follower lease、有界等待、安全终态和产物定位 |
| `src/specflow/runner_multi.py` | 在 evidence 前领取 ownership；API 传入 owner lease 时直接执行；返回保持整数兼容的审计结果；成功 manifest 增加 owner 审计；异常日志不附原文 |
| `src/specflow/runs.py` | 每个接受的请求保存独立 WorkflowRun；state_payload/DTO 表达合并；owner 独占 permit，follower 持久化共享终态；安全相对产物引用 |
| `src/specflow/api_security.py` | 从原 acquire 抽出请求计数；原 acquire 行为兼容；新增按 ownership 角色准入 |
| `src/specflow/runner.py` | legacy 最小入口封装，复用同一协调器与准备好的 provider 配置；原 worker、退出码、产物写入契约保留 |
| `tests/test_run_single_flight.py` | 直接调用/legacy 真重叠、键语义、快照边界、终态清理和非缓存测试 |
| `tests/test_runs.py` | API 真重叠、独立审计、安全准入、失败、调用方取消等待与 follower 超时 |
| `tests/test_api_security.py` | follower 计数不取得第二个 permit、不同键拒绝与释放后的准入 |
| 本报告 | 契约映射、验证证据、已验证范围与同步需求 |

无需修改 `policy/models.py`：现有完整 `ExecutionPolicy.policy_hash()` 提供策略指纹，`max_wall_time_seconds`（默认 300 秒）提供 follower 等待配置；Flight.wait 进一步拒绝非有限或负数界限。数据库列、冻结规范、六 agent 拓扑、stage 依赖、handoff schema、revision 上限和 benchmark baseline 均未改动。

A01 修复复用该文件中现有的冻结 `RunOutcome`，由整数兼容的 `RunResult` 持有；未新增第三套结果模型。此次生产改动仅在 `single_flight.py`、`runner.py`、`runner_multi.py`、`runs.py`，另更新现有 single-flight 测试与本报告。

1. 昂贵工作始于 `EvidenceCollector.collect`，随后是 `Coordinator.plan` 的 enrichment/provider、`MultiAgentScheduler.execute` 和产物目录创建。legacy 在 evidence 前配置 client，随后调用 workers 和 ArtifactStore。
2. HTTP 中间件和 dependency 先认证；`RunService.create` 在读取仓库前重新验证现行 allowlist。相同 key 也必须通过上述路径。
3. 原 permit 在路由进入服务前领取、路由 finally 释放。现在协调器在锁内区分 owner/follower，并在同一次原子操作中准入：owner 调用原 acquire，follower 只计每分钟请求。不同键的并发拒绝不消耗速率配额，保留已有测试的计数语义。
4. `WorkflowRun.id` 是请求审计身份；`current_state/result_status` 保存状态；`artifact_directory` 保存相对于 API artifact_root 的既有引用。`state_payload` 已是 JSON，无需加列。
5. **唯一 ownership 入口是协调器 claim。** API 领取后显式传 owner Flight 给 runner；runner 不再次注册。直接 multi-agent/legacy 调用自行进入同一协调器。
6. 完成发布和移除 entry 在 owner 的 finally 路径执行，API permit 同时释放。API owner 的持久化终态提交在发布 follower 结果之前完成。
7. 同步调用退栈才清理；scheduler 已有 `shutdown(wait=True)` 等待实际执行中的线程。取消调用方等待不等于底层工作已结束。
8. 两条 owned runner 直接返回结构化终态、错误分类与已完成产物的安全定位；API 从这份结果保存请求终态。manifest 是持久化审计产物，不再用于重建本次执行结果。既有 bare-int adapter 兼容分支仍可读取其旧产物，但标准 runner 不走该分支。

## 等价键与早期 snapshot 边界

key 只驻留于进程内，不记录完整 key、需求、仓库路径或秘密到日志/响应。request ID、output directory 不参与语义键。

包含：规范化仓库身份、仓库显示名称及 pyproject 存在状态、snapshot、精确 requirement SHA-256、legacy/multi-agent mode、有效 mock/live mode、实际 provider/环境选择的 model/endpoint/timeout、用于区分 provider 凭据上下文的内存摘要、会影响 provenance/manifest 的请求 model/provider 标签、完整 execution-policy hash、版本项及额外输出配置。版本项明确覆盖 topology、schema、prompt、enrichment、sanitizer、artifact 和 evidence 契约；legacy 的 max_files 与测试 executor overrides 也区分。准备好的 provider 配置向执行链传递，避免构造 key 后再次读取不同配置。

snapshot 使用既有 `RepositoryAccessPolicy` 的敏感文件、ignored-directory、symlink/reparse、resolve_file 规则，以及同一个 `_read_text` 前缀读取器；新增遍历器在每个 scandir 项上计数，防止大量空目录绕过文件计数上限。

- 最多 `min(10000, policy.repository.max_scanned_files)` 个文件/目录项，含跳过项的计数；超过即失败。
- 累计读取前缀预算 8 MiB；超限即失败。
- 只覆盖 evidence 候选 `*.py/*.md/*.yaml/*.yml/*.toml/*.cfg`，不读 Git、忽略目录、敏感路径或非候选内容。
- 每文件使用 Tool 现有 262144-byte 窗口及一个 sentinel byte。snapshot 哈希解码前缀和截断状态；sentinel 中 NUL/无效文本维持现有读工具拒绝语义。不会扩大现有 source_hash 或持久化文件哈希契约。
- 使用未脱敏的有界文本参与内存摘要，因为 `search_code` 在脱敏前匹配关键词；仅复用脱敏后的 ReadFile hash 会漏掉影响搜索选择的变化。
- 读取前后检查文件 inode/大小/mtime/ctime，检查目录遍历期间变化。读取错误、扫描不完整或已发现变化以 `SINGLE_FLIGHT_SNAPSHOT_UNAVAILABLE` 在注册前失败。
- **不能证明：** 任意仓库字节的全量相等、两次读取间的原子一致性、执行过程中敌对修改、进程间共享或重启恢复。本契约仅支持执行期间保持稳定的仓库；没有添加锁或仓库 mutation 支持。byte 窗口之后、ignored/sensitive/非候选内容不在等价证明范围，且当前执行链不读取它们。

每个行为版本是显式兼容版本，后续修改对应行为时需要更新版本项；本轮没有引入代码文件扫描哈希或热替换支持。

## owner/follower 审计与失败语义

安全示例（示例标识不是实际用户数据）：

```json
{"id":"11111111-1111-4111-8111-111111111111","status":"completed","single_flight":{"role":"owner","owner_run_id":"11111111-1111-4111-8111-111111111111"},"artifact_available":true}
{"id":"22222222-2222-4222-8222-222222222222","status":"completed","single_flight":{"role":"follower","owner_run_id":"11111111-1111-4111-8111-111111111111"},"artifact_available":true}
```

两个 state_payload 分别保存 `{"mock":true,"single_flight":...}`；两个 artifact_directory 可以指向同一个安全的 `owner-id/run-multi-example` 相对目录。API 不返回本地目录，产物索引仍通过各自 Run ID 请求。直接调用返回 int 子类 RunResult，其 role/owner_run_id 和内部 owner 产物定位可检查；CLI 退出码和确定性 run_id 保持兼容。

RunResult 的普通字段赋值和删除被禁止，审计 metadata 每次返回副本，避免 owner/follower 调用者修改已发布的共享终态。分类集中在现有 RunOutcome/RunResult，RunService 不再重复从退出码映射另一份终态。

- 成功与已分类失败共享 owner 终态，不启动第二套执行。
- 业务 REJECT 保持业务拒绝，正常 revision 最多一次；不会变成基础设施失败。
- 意外异常使用安全运行时失败；owner 真正取消退栈时 follower 得到 RUN_CANCELLED/cancelled。
- follower 超时是 `SINGLE_FLIGHT_WAIT_TIMEOUT`，API 保存 failed_runtime；不自动转为 owner，不删除在执行的 owner。
- 调用方取消 async 等待时，已经运行的同步线程继续完成；其 ownership/permit 不提前释放，最终仍落下真实终态。
- multi-agent 仅共享带既有 `_COMPLETE` 标志的目录；部分产物失败不会作为完成产物引用。legacy 保持原写入契约，不扩展原子性。
- API 共享引用必须重新落在该服务的 artifact_root 内；越界时明确安全失败，不复制产物到 follower 目录。
- 清理后的下一请求重新执行，完成结果不保留在协调器中。相同 output 已存在时保持原冲突行为，不读取旧结果充当缓存。

## 2026-09-12 A01 修复证据

独立验收在初始实现发现：legacy 需求正文进入 manifest，文件超过 131072 字节时，新增 artifact_result 提前返回保留完成码但没有 artifact_directory 的结果；真实重叠的两个调用都返回 4，却丢失共享引用。这是必需结果契约缺口，初始全量测试通过不能证明该边界正确。

本次修复删除该结果反向解析函数及 128 KiB 阈值。owned runner 在真实执行、必需产物写入结束后直接产生 RunResult；`completed_artifact_directory` 仅检查安全定位、manifest 文件存在性以及 multi-agent 的原有完成标志，不解析 JSON 内容。原有 artifact-integrity 的文件哈希仍执行，未扩大或绕过它的契约。

成功或降级完成结果只有在必需写入结束并取得安全定位后才产生。已分类执行失败直接保留原错误码，诊断产物写入失败不会把它改成无分类结果；正常产物 I/O 失败则显式返回 ARTIFACT_WRITE_FAILED。API 最终持久化提交仍先于向 follower 发布结果，ownership/permit 释放时机未提前。

| 新增/增强验证 | 实际结果 |
| --- | --- |
| test_legacy_overlapping_calls_share_execution，短需求、120000 与 140000 字符参数 | 3 个参数均通过；覆盖 128 KiB 上下的 manifest，引用非空、相同且 10 个产物完整 |
| 原独立 A01 复现脚本 | 1 passed in 1.00s；manifest_bytes=140985，两个退出码为 4，两个引用均存在，evidence_executions=1，active_count=0 |
| RunResult 的整数兼容、只读字段、metadata 副本与终态分类 | 5 个通过场景 |
| artifact I/O 三个失败点、缺失完成标志、诊断写入失败后原错误保留 | 5 个通过场景 |
| 当前源码下独立 API/真实 worker 取消与跨入口补验 | 3 passed in 1.58s |
| 独立注入 API owner 最终 Session.commit OSError | follower 保存 failed_runtime/RUNNER_FAILED、无成功引用；owner 回滚为 running 由原启动恢复处理；coordinator=0，permit 可重新取得 |

开发红测试实际记录：长 manifest/新结果分类等出现 6 failed、2 passed；三个 artifact I/O 分类出现 3 failed。完成最小修复后全部通过，未削弱原断言。独立只读修复复核未发现阻塞问题。

A01 对原 head 的审查报告保持为历史证据；本段只记录本轮修复与复验，不自行合并或关闭 T-070。

## REQ/AC → 实现 → 测试证据

| REQ / AC | 实现 | 测试名称（参数化场景见源码） |
| --- | --- | --- |
| REQ-070-1；AC-070-2 | prepare_run / repository_snapshot | test_semantic_key_changes_never_join_existing_owner；test_each_behavior_contract_version_is_part_of_key；test_legacy_live_requested_model_changes_do_not_coalesce；test_key_includes_summary_directory_existence；test_different_direct_inputs_execute_as_two_overlapping_owners |
| REQ-070-1/8 | 有界快照及安全错误 | test_snapshot_covers_raw_search_input_not_only_redacted_file_hash；test_snapshot_does_not_expand_the_tool_read_window；test_snapshot_ignores_sensitive_and_excluded_files；test_unsafe_snapshot_fails_before_evidence_or_ownership |
| REQ-070-2；AC-070-1 | coordinator / runner wrapper | test_direct_overlapping_calls_share_execution_and_audit：owner evidence 被 Event 阻塞，follower 在释放前加入；实际一套 evidence、6 次正常 mock enrichment、4 次 scheduler、9 个各写一次的产物 |
| REQ-070-3；AC-070-4 | RunRead / state_payload / _finish_run | test_api_single_flight_dto_is_durable_without_new_columns；test_overlapping_api_requests_keep_audit_security_and_capacity：两个 running 行、不同 UUID、相同 owner、安全共享目录；test_api_cannot_share_direct_owner_artifacts_outside_its_root |
| REQ-070-4/8；AC-070-3 | Flight.wait / RunResult / 安全分类 | test_owner_terminal_paths_release_followers_and_allow_later_execution；API 重叠的 success/reject/classified/exception/artifact/evidence 六场景；test_partial_artifact_failure_is_not_shared_as_completed |
| REQ-070-3/4/7；A01 | owned runner 直接结果 / completed_artifact_directory | 长 legacy 并发参数、test_run_result_keeps_int_compatibility_and_is_immutable、test_run_result_carries_terminal_classification、test_artifact_io_failure_is_an_explicit_runtime_result、test_missing_completion_marker_cannot_publish_success、test_primary_failure_survives_unavailable_diagnostic_artifacts |
| REQ-070-5；AC-070-3/5 | owner finally 移除、发布与释放 | test_follower_exit_keeps_the_owner_and_later_follower；test_api_follower_timeout_is_durable_and_does_not_release_owner；test_caller_cancellation_keeps_running_api_work_and_permit；test_completed_results_are_not_cached |
| REQ-070-6；AC-070-4/6 | admit_single_flight / count_request | test_single_flight_followers_count_without_a_second_permit；API 重叠时 401、旧项目越权 403、不同键 429、同键第三请求计数 429；既有 quota 测试 |
| REQ-070-7；AC-070-6 | legacy wrapper / multi-agent CLI | test_legacy_overlapping_calls_share_execution；test_cli.py、test_cli_multi_agent.py、test_runner_dlp.py、安装 wheel/API mock 冒烟、12 案例 benchmark |
| REQ-070-9；AC-070-7/8 | 限定文件 diff / 本报告 / 聚焦提交 | git diff --check、提交前 cached 检查、全回归与 Ruff；本轮未触碰冻结规范、数据库列或范围外生产模块 |

并发测试使用 Event/线程池和明确的 owner 阻塞点，等待超时仅防止挂死。timeout 测试注入零等待界限时 owner 已被同步点保持；取消等待测试通过 asyncio Future 取消观察者，断言底层 future 仍运行。测试结束释放所有 Event、等待线程池退出、关闭 DB/TestClient，并通过协调器公开 active_count 检查清理。

## 执行验证

初始实现基线为上述 IMPLEMENTATION_BASE；下表最新回归使用 7856e3a 加本轮四个生产文件及现有测试的 A01 修复。依赖使用既有锁定环境；uv.lock/pyproject 未变化。live provider 没有调用。

| 阶段与命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| 基线 `uv run pytest -v` | 0 | 771 passed, 3 skipped, 3 warnings in 15.57s |
| 基线 `uv run ruff check .` | 0 | All checks passed；既有 test_coordinator.py:113 invalid noqa warning |
| 基线 `uv run ruff format --check .` | 0 | 208 files already formatted |
| 基线 `git diff --check` | 0 | 无输出 |
| 初始交付完整 pytest | 0 | 828 passed, 3 skipped, 3 warnings in 16.06s；后续独立验收仍发现 A01 |
| 定向检查（完整命令见下） | 0 | 208 passed, 2 skipped, 1 warning in 12.42s |
| `uv run pytest -v` | 0 | 840 passed, 3 skipped, 3 warnings in 18.05s；较修复起点新增 12 个通过场景 |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 210 files already formatted |
| `git diff --check` | 0 | 无输出 |
| `uv build` | 0 | 成功生成 1.1.1 sdist 与 wheel |
| `uv run specflow --version` | 0 | specflow 1.1.1 |
| `uv run specflow run --help` | 0 | 既有 legacy/multi-agent CLI 参数可用 |
| `uv run python scripts/check_secrets.py` | 0 | 无发现 |
| benchmark 执行与 baseline 比对 | 0 / 0 | 12 案例 mock，baseline 无差异 |
| `uv run python scripts/smoke_installed_wheel.py` | 0 | clean venv install、version、artifact import、API + mock run + artifact read 四项 PASS |
| 加锁定依赖约束的 wheel smoke | 0 | 四项 PASS；约束从现有 uv.lock 导出，不更新依赖 |
| `git diff --cached --check` | 0 | 提交前通过，无空白错误 |

定向测试完整命令：

```text
uv run pytest tests/test_run_single_flight.py tests/test_runs.py tests/test_api_security.py tests/test_cli_multi_agent.py tests/test_cli.py tests/test_runner_dlp.py tests/test_execution_policy.py tests/test_repository_tools.py -v
uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/t070-a01-fix --baseline artifacts/t070-a01-fix/baseline.json
git diff --no-index --exit-code benchmarks/results/mock-baseline.json artifacts/t070-a01-fix/baseline.json
uv export --locked --no-dev --no-emit-project --no-hashes --format requirements-txt --output-file <temporary-constraints.txt>
PIP_CONSTRAINT=<temporary-constraints.txt> uv run python scripts/smoke_installed_wheel.py
uv run pytest C:\Users\50469\temp\t070-acceptance-20260912\test_independent_artifact_reference.py -v -s --tb=short
```

PIP_CONSTRAINT 在 Windows 本轮命令进程内赋值；最后一行是其简写。工作区验证日志保存在本机 TEMP 的 specflow-t070-* 日志文件，不作为可移植持久化契约。

开发轮包含预期红测试及已修正的测试装配问题。实际捕获并修正：DTO 缺失、legacy 未集成、pyproject 摘要输入遗漏、异常日志原文、取消状态传播、部分产物共享与 live legacy model-key 覆盖遗漏。最后一项来自一次只读独立代码检查，已先补红测试复现后修复。该审查已复查修复，未发现其他有实际证据的重要问题；它没有运行完整回归，也不代表独立验收通过。

暂存后的扫描首次覆盖新增测试文件，曾以退出码 1 报告其中的假凭据样式；已把该合成配置改为仓库规则允许的 test- 前缀，未修改扫描器或忽略规则，随后重验。首次 git add 对三个新增文本文件输出 LF 转 CRLF 的仓库配置提示；未改 Git 配置，diff 检查单独执行。

没有新增 skip：三个既有 Windows symlink/reparse 相关 skip 来自 test_repository_tools、test_runs、test_scanner。三个既有 pytest warnings 为 TestStrategyAgent/TestStrategyOutput 收集警告与 Starlette/httpx 弃用警告；未通过新增依赖消除警告。

## 本地验证与远端 CI 的分界

本地门禁结果如上；不是远端 CI 证据。PR #8 已存在，修复推送前远端仍为 7856e3a。当前 `.github/workflows/ci.yml` 的 pull_request 触发分支仅为 main，而本次 base 为 docs/m10-runtime-assurance-spec；此前实际查询为未触发。修复推送后再次按实际查询结果报告，不推断成功，不为本任务修改 CI 配置。

## 已验证范围、剩余边界与停止点

已验证单进程 Python mock、直接调用、legacy 和 multi-agent、同步 HTTP Run API，及合成 provider 配置的等价性变化。没有 live provider、生产容量、多进程、分布式幂等、跨重启恢复、任意代码热替换或仓库执行中修改的验证。

这是 in-flight 协调：同键注册在锁内只产生一个 owner，follower 只等待它；超时分支不会重新 claim。entry 随 owner 实际终态清理，后续请求重新执行，所以不是结果缓存。状态只存在当前进程内，所以不是分布式幂等。

实现提交和独立 PR 交付后停止；不继续 T-071、T-077 或任何 M10 实现。不自行宣布独立验收通过。

## 2026-09-13 关闭登记：T-070 — CLOSED

本次用户明确要求核验七项 closure 条件，全部可证明时登记关闭。登记仅针对
已经合并的 T-070，在下述固定版本及单进程边界内完成；不修改运行时代码，不
以 PR #12 的规范 findings 关闭替代 T-070 实现证据。

### 固定版本与证据归属

- 规范来源：`02c1d3fe9bcd8c95d6bb7cf3959328844598e473` 中的
  [T-070 规范](../tasks/T-070-run-single-flight-and-early-idempotency.md)。
- 初始 implementation commit：`7856e3a1bff737282f7cf9cece2e38f2fe7895f9`。
- A01 修复/source commit：`c54aaf703313764cf4ea1605eb883d8263ae9e52`。
- 集成修复及外部被审候选：`04cd641a1c5178795fd92f205016e2e629097103`。
- integrated main commit：`2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0`；
  [PR #11](https://github.com/wsc0796/specflow-agent/pull/11) 于
  `2026-09-13T06:08:25Z` 合并，GitHub mergeCommit 与 main ref 均匹配。
- `04cd641` 与 integrated main 的完整 tree 同为
  `d4b76cd2cfd8fd0428886cadcb9e3a0f270e8d48`；二者不是仅文件名相同，而是
  Git 完整文件树相同。初始实现与 A01 提交均经 `merge-base --is-ancestor` 确认。
- [main 上的原完成报告](https://github.com/wsc0796/specflow-agent/blob/2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0/docs/reports/T-070-completion-report.md)
  与 A01 source commit 中的报告无差异；本章节在该历史报告之后追加。
- [main 上的集成报告](https://github.com/wsc0796/specflow-agent/blob/2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0/docs/reports/runtime-repairs-integration-2026-09-13.md)
  保存组合失败、适配、INT-01 与 R1 修复过程，不把其中待发布状态当成当前远端事实。

### 七项 closure 检查

| 检查 | 核验结果及证据 |
| --- | --- |
| 1. 实现已进入 main | **满足**：`7856e3a`、`c54aaf7` 为 `2959a2f` 祖先；PR #11 已合并 |
| 2. completion report 可读 | **满足**：上述 main 固定链接可读取原报告；原有 REQ/AC 映射、真实测试记录和限制保留 |
| 3. REQ/AC 组合证据适用于 main | **满足**：被审候选与 main tree 完全一致；本轮源码/测试静态追溯无断链，定向回归覆盖原 T-070 与组合路径；main 自身 CI 全量通过 |
| 4. A01 后续修复已包含 | **满足**：直接 RunResult、整数兼容和冻结结果、只检验完成定位均保留；legacy 0/120000/140000 字符三档并发回归通过 |
| 5. 独立发现已处置 | **满足**：初始 model-key 遗漏及 A01 已修复复核；集成 INT-01 的过宽关闭经 R1 修复纠正；`04cd641` 外部复审明确关闭已复现 R1/P2，本地锁定 32 探针通过 |
| 6. CI/benchmark/smoke/security 可读 | **满足**：main CI `34742011953` 的元数据、步骤和完整日志本轮已读取，四 job 均 success；benchmark 基线比对和 installed smoke 步骤均成功 |
| 7. 无未处理的 T-070 blocking finding | **满足**：现有发现链均有上述处置；本轮独立只读源码/测试复核未发现未处理的 T-070 blocking finding，不扩为任意攻击面的完整证明 |

### 组合契约与复审证据

本轮独立只读复核以 `main=2959a2f` 的源码/测试为对象，核对 `prepare_run()` /
`repository_snapshot()`、协调器 `claim()` / `Flight.wait()`、两个 owned runner、
RunService、API admission 和 scheduler 的等待清理。未修改文件，也未把静态
检查当成执行结果。原 REQ/AC 表仍有效，组合回归补充如下：

| REQ / AC | main 上的实现及测试证据 |
| --- | --- |
| REQ-070-1；AC-070-2 | `single_flight.py` 的完整语义键、安全有界快照；`test_run_single_flight.py` 的差异键/版本/读取边界及重叠 owner 测试 |
| REQ-070-2/-3/-6；AC-070-1/-4 | 锁内 claim/admission、独立 WorkflowRun 身份和安全共享引用；`test_runs.py`、`test_api_security.py`、跨入口双向集成回归 |
| REQ-070-4/-5/-8；AC-070-3/-5 | 安全终态、超时、不重复执行、finally 清理；`test_runtime_repair_integration.py` 的真实 worker 取消与 peer 退栈后释放，及无证据/无效输出/失信 payload 组合失败 |
| REQ-070-7；AC-070-6 | 两条 CLI/mock、API 认证/allowlist/限流、DLP、产物及启动恢复的既有回归；main CI 的 benchmark 和安装 smoke |
| REQ-070-9；AC-070-7/-8 | 本报告、聚焦实现及 A01 commit、最新集成提交、定向与全量门禁；关闭登记不改变产品实现面 |

外部复审来源为用户此前提供的 `specflow-review-04cd641-evidence.zip`，报告
`specflow-review-04cd641/REVIEW-04cd641.md` 的 SHA-256 为
`5250665ebd65f7056cceb830e09b73717b748769bc966f495a7620242fdeca6d`。
报告绑定 `04cd641`，结论为复审通过、原 R1/P2 已复现缺陷关闭、未发现新的可复现
阻塞项。其 Linux/Python 3.13 非锁定结果作为补充证据，不冒充 Windows 锁定验证。
原证据包及报告保留于本机；本章节登记其结论、身份与边界，供远端审查追溯。

本地历史锁定复验记录在
`C:/Users/50469/temp/specflow-04cd641-review-recheck-20260913/LOCKED-RECHECK.md`：
5 个原探针与 27 个跨阶段探针共 **32 passed、1 warning、3.67s、exit 0**。
这是当时新执行的复验，本轮只核对其记录及树适用性，不将其记为本轮重新运行。
API owner 最终 `Session.commit` 失败的独立注入结果来自本报告 A01 证据表；本轮
源码仍是 `_finish_run()` 先于 `flight.complete()`。该历史独立实验不称为仓库内
专门回归，也未在本轮重新执行；现有异常/清理测试与组合测试仍分别保留其覆盖。

### main CI 与本轮验证

[合并后 main CI](https://github.com/wsc0796/specflow-agent/actions/runs/34742011953)
为 push 事件，headSha 精确等于 `2959a2f`；quality、benchmark、security、smoke
均 completed/success。日志中的全量结果为 **923 passed、3 warnings、12.71s**，
Ruff 通过、213 files formatted；benchmark 生成结果后与既有基线比对成功。
这是 main 的历史 CI 执行记录，由本轮读取确认，不是本地新跑的测试数字。
候选 CI `34740864163` 与规范分支 CI `34746093700` 也已核对 success，但不以
它们替代 main 自身的 CI 证据。

本轮定向回归运行在文档分支的 `c14e038` 加关闭登记文档上；其 `src/`、`tests/`、
benchmark、scripts、prompts、依赖与 main 比对无差异。使用 Windows / Python
3.12.10、现有 `uv.lock`、`UV_FROZEN=true`，没有 live provider 调用。

```text
uv run pytest tests/test_run_single_flight.py tests/test_runs.py tests/test_api_security.py tests/test_runtime_repair_integration.py tests/test_cli.py tests/test_cli_multi_agent.py tests/test_runner_dlp.py tests/test_handoff_validator.py -v
```

实际结果：**175 passed、1 skipped、1 warning、23.96s，exit 0**。skip 为
Windows symlink 权限，warning 为 Starlette/httpx 弃用提示，没有新增 skip。
本次登记后的完整质量门及最终工作区状态见
[规范结算与开工门报告](T-071-T-080-spec-review-entry.md) 的“本次登记验证”。
本轮日志保存于 `C:/Users/50469/temp/specflow-t071-gate-closure-20260913/`。

### 关闭范围与下一门

**T-070 — CLOSED**，仅指以上固定实现、证据和范围的任务关闭。已知限制不变：
单进程 in-flight 合并，无跨进程/分布式协调、无跨重启保障、无完成结果缓存；
follower 超时不强停同步 owner，运行中的仓库 mutation 不受支持；没有 live-provider
语义质量或生产容量结论。bounded Python evidence snapshot 不宣称全仓库原子快照。

本次不关闭来源 PR #8、不合并 PR #12、不启动 T-071。T-071 仍须使用已通过
静态复审的权威 amendment，在干净、独立分支上的新 focused session 单独开工。
