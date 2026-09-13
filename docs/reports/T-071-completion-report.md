# T-071 — Provider Resilience Guard 完成报告

日期：2026-09-13。状态：实现及本地质量门通过，独立只读代码复核无阻塞；
交付待外部独立审查，不自动关闭 T-071。

## 基线与实施授权

- 仓库：`wsc0796/specflow-agent`。
- 工作分支：`feat/t071-provider-resilience-guard`。
- implementation base / 开始时 HEAD：`339e6e28e1d8c7bd79ac6e7303c0e1c5717c45da`。
- `git branch --show-current`、`rev-parse HEAD` 与指定对象匹配；开始时
  `git status --short` 无输出，`merge-base --is-ancestor 339e6e2 HEAD` exit 0。
- 用户本轮任务明确指定这是新的 focused implementation session。
  T-070 CLOSED、规范 findings CLOSED、权威 amendment 可读、正确分支与 clean
  基线均满足，因此本轮开始时 **T-071 implementation gate satisfied**。
- 已完整读取 AGENTS、冻结基线、M9、T-070 规范及关闭报告、T-071 完整规范与
  规范复审登记。T-071 正文包含 endpoint/model/tenancy 内部身份及公开审计分离。
- 最终 implementation HEAD 在聚焦提交后由 PR 正文和交付记录给出，避免报告
  循环登记自身 SHA。PR #12 规范与关闭登记是本分支祖先，本轮不自行合并它。

## 实际调用链与最小接入设计

| 对象 | 实际 file:symbol 与职责 |
| --- | --- |
| CLI | `src/specflow/cli.py:main` 分派 legacy/multi-agent |
| legacy client 与预算 | `src/specflow/runner.py:_run_owned` / `_create_llm_client` / `_PolicyBoundLLMClient.complete`，构建共享真实 client，保留原调用预算 |
| legacy retry/fallback owner | `src/specflow/fallback/manager.py:FallbackManager.execute` 调用 `strategies.py:RetryStrategy.run`；终态异常经 `RuleBaselineStrategy.build` 返回 degraded、requires_review；未新增重试层 |
| multi-agent client | `src/specflow/runner_multi.py:_create_real_llm_client` 使用准备好的 config，timeout 仍受 run deadline 上限约束 |
| multi-agent retry / failure envelope | `src/specflow/agents/adapter.py:AgentRunner.execute` 保留原 `_max_retries` 循环和 fail-closed envelope；默认调用仍不额外增加 retry |
| planning fallback | `src/specflow/plan/enricher.py:SemanticPlanEnricher.enrich` 对失败的 enrichment 生成既有 degraded brief，无重试；与 AgentRunner 使用同一 provider client |
| 公共实际 transport | `src/specflow/llm/providers/openai_compatible.py:OpenAICompatibleLLMClient.complete` → `_complete_once` → `httpx.Client.post`，每次被允许的调用至多一次 HTTP POST |
| 有效配置 | `src/specflow/llm/providers/config.py:OpenAICompatibleConfig.from_env` / `__post_init__` / `completions_url`；显式 config 或 `SPECFLOW_LLM_*` 环境，wire model 使用 config.model，而非 request.model |
| mock | legacy `_create_mock_clients`、multi-agent `_make_mock_llm_client` 与直接 mock Agent 执行均独立于真实 provider；无需触碰 guard registry |
| 错误分类 | `src/specflow/policy/errors.py:ErrorCode` / `is_retryable`；provider 在已知 transport/status 分支赋予可选 ErrorCode，guard 不分析任意异常文本 |

状态由唯一默认进程级 `ProviderResilienceGuard` 拥有，也允许构造时注入独立 guard
及 monotonic clock。没有新增 run 配置字段、policy hash 变更或 T-070 key 变更；
固定状态机默认配置属于进程 guard，runner 沿用原配置与 budget。两条真实 pipeline
自然复用 provider 接入点，legacy runner 不需要修改。

## 内部身份与公开数据

内部 key 为三个固定长度 SHA-256：规范化实际 `completions_url`、effective model、
credential。URL 使用实际 HTTP URL 的规范化表示；已有 config 已去尾斜线并拒绝
嵌入凭据/query/fragment。key 不含 raw API key、endpoint 或 model 字符串，repr
隐藏摘要；所有状态只在进程内，不落盘、不写日志或产物。

默认按 credential fingerprint 隔离 tenancy；本轮未引入跨 credentials 的共享
alias 配置。不同 endpoint、model 或 credential 分离；同配置的多个 client/Agent
共享同一状态。timeout 和请求 model 标签不改变实际后端/tenancy 身份。

`CircuitSnapshot` 只包含有界的 `resource-N` / `model-N` 别名、状态、健康失败计数、
连续失败数、活动调用/probe 数、拒绝数和迁移数。这些别名只标识当前 registry 中
的驻留槽位，可在安全回收后复用，不是跨重启或持久化身份，不能反推内部指纹。
本轮只提供只读安全观察接口，不实现 T-073 metrics 字段或 exporter。

## 状态机、释放及 registry 上限

- `ResilienceSettings` 提供正整数 failure_threshold（默认 5）、half-open probe
  上限（默认 1）、registry 上限（默认 128）及正且有限的 open_seconds（默认 30）。
  配置通过 guard 构造注入，不增加依赖、CLI 参数或后台配置系统。
- `attempt()` 在锁内领取；CLOSED 连续可计数失败达到阈值进入 OPEN；未过冷却期
  明确拒绝且不执行 transport。冷却后由下一次真实调用触发 HALF_OPEN，不依赖 timer。
- HALF_OPEN 许可受配置上限约束。有效 probe 的 availability failure 重新 OPEN；
  最后一个活动 probe 成功后才 CLOSED，避免较早成功掩盖同批尚未返回的失败。
- 每次 attempt 的 `finally` 释放活动调用/probe，覆盖成功、已分类失败、普通异常、
  SystemExit、KeyboardInterrupt。排除错误不改变健康判断；HALF_OPEN 槽释放后可再探测。
- generation 防止旧 CLOSED/probe 结果覆盖后续代次；旧调用仍释放资源，真实已分类
  availability failure 仍只累计一次。失败总数与阈值用的连续失败数分开。
- 满 registry 只回收无活动调用、无连续失败的健康 CLOSED 条目。OPEN、HALF_OPEN、
  仍执行或已累积失败的条目不被驱逐；无可回收槽时明确拒绝新资源，不创建无界状态。
- 冷却后的 probe 必须经正常请求触发；没有外部探测、后台线程、分布式状态或重启恢复。

## 分类、重试与失败产物

只计入 `PROVIDER_TIMEOUT`、`PROVIDER_RATE_LIMITED`、`PROVIDER_SERVER_ERROR`、
`PROVIDER_CONNECTION_ERROR`。provider 在 httpx timeout/request-error 和 HTTP
429/5xx 分支显式赋值；任意 transport coding error 的文本即使含 `500/rate/timeout`
也不会误计入。auth、404 model-not-found、JSON、schema、安全、policy、internal
错误均不计入 health；下游 JSON/schema 校验仍由原组件负责。

`LLMError` 增加可选 code，原异常类型和安全消息保持兼容。AgentRunner 优先消费
明确 ErrorCode，未标注的旧 provider/fake 仍走原分类器。这也使真实 HTTP 404
使用现有 MODEL_NOT_FOUND、其他 5xx 使用现有 SERVER_ERROR，而不被旧字符串
匹配遗漏。legacy `RetryStrategy` 的原分类逻辑、预算和 backoff 没有修改。

新 `LLMCircuitError` 使用 `PROVIDER_CIRCUIT_REJECTED`，归入既有不可重试类别，
reason 仅为 `open`、`probe_limit`、`registry_capacity`。既有 legacy retry owner
遇到该安全异常立即停止；FallbackManager 可按原契约返回明确 degraded baseline，
不伪装成 provider 成功。multi-agent 阶段结果检查只对该新错误保留安全 SpecFlowError，
经已有失败 writer 写入；不让它丢失为通用错误，也不放行失败 Agent 输出到 handoff。

## 改动范围与验收映射

生产文件仅为 `llm/resilience.py`、`llm/exceptions.py`、
`llm/providers/openai_compatible.py`、`policy/errors.py`、`agents/adapter.py`、
`runner_multi.py`。测试为新增 `tests/test_provider_resilience.py` 及现有 provider
单测的独立 guard 注入；原断言保留。未修改其他 task spec、数据库、拓扑、schema、
DLP、revision、学习记录、依赖、benchmark baseline 或后续任务实现。

| AC | 行为证据 |
| --- | --- |
| AC-071-1 | threshold/open/clock/probe 恢复与失败重开、真实双 probe 上限及较早成功不能掩盖晚失败 |
| AC-071-2 | endpoint/model/tenancy 隔离、同资源共享、8 个并发失败只创建一个 entry、registry 回收/满容量拒绝 |
| AC-071-3 | 参数化 transport/status 分类、auth/model/JSON/schema/security/policy/internal 排除、half-open auth 释放 |
| AC-071-4 | FallbackManager 原重试次数与真实 POST 次数；circuit 后不再 retry，baseline 明确 degraded；AgentRunner 保留 circuit code |
| AC-071-5 | 两条真实 mock CLI 在 guard/key 构造被禁止的测试中仍成功；所有 HTTP 使用 MockTransport 或既有离线阻断 |
| AC-071-6 | provider、fallback、CLI、T-070 并发、安全/schema/DLP 及完整回归，结果见下 |
| AC-071-7 | 定向、全量 pytest、Ruff、diff，以及补充 benchmark 和 installed-wheel smoke，结果见下 |
| AC-071-8 | 本报告、独立只读复核、聚焦 implementation commit 与独立审查 PR；交付后停止 |

## 本轮验证记录

环境：Windows / Python 3.12.10，原 `uv.lock`，命令设置 `UV_FROZEN=true`。
原始日志目录：`C:/Users/50469/temp/specflow-t071-implementation-20260913/`。

- 初始红阶段：42 failed，exit 1，因尚无 resilience 模块；随后核心 42 passed。
- 集成红阶段：修正测试夹具调用的 registry 方法后，3 failed / 49 passed，确认
  AgentRunner 丢失 circuit/404 分类及 multi-agent 失败产物丢失 circuit code。
  最小分类/失败映射后 52 passed。
- 双半开 probe 红阶段：1 failed，较早成功错误关闭 circuit；改为等待活动 probe
  结束后恢复，新增混合结果及并发计数回归。

| 命令 / 验证 | Exit code | 本轮实际结果 |
| --- | --- | --- |
| T-071 + provider 独立只读复核 | 0 | 81 passed，1.09s；复核者另用 Event 验证同批半开 probe 先成功、后失败仍重开，未发现剩余 blocking finding |
| 受影响十二文件定向 pytest | 0 | 295 passed、1 skipped、1 warning，16.80s |
| `uv run pytest -v` | 0 | 975 passed、3 skipped、3 warnings，22.58s；含 55 个新增 T-071 场景 |
| `uv run ruff check .` | 0 | All checks passed! |
| `uv run ruff format --check .` | 0 | 215 files already formatted |
| `uv run python scripts/check_secrets.py` | 0 | 无发现；暂存新文件后再次扫描 |
| `git diff --check` / `git diff --cached --check` | 0 | 提交前检查无空白错误 |
| 12-case benchmark / normalized baseline 比对 | 0 / 0 | case_count=12、status=passed；既有 baseline 无差异 |
| 首轮 installed smoke | 1 | 环境阻塞：pip 获取锁定 annotated-doc==0.0.4 时 TLS EOF；两轮运行检查均未启动，不计为通过 |
| 指定官方 PyPI 后重跑 installed smoke | 0 | 新 wheel 与 standalone sdist-rebuilt wheel 各 10 项 PASS，非 editable 安装 |

定向命令：

```text
uv run pytest tests/test_provider_resilience.py tests/test_openai_compatible_provider.py tests/test_fallback.py tests/test_agent_adapter.py tests/test_cli.py tests/test_cli_multi_agent.py tests/test_run_single_flight.py tests/test_runs.py tests/test_api_security.py tests/test_runner_dlp.py tests/test_required_output_validity.py tests/test_runtime_repair_integration.py -v
uv run specflow benchmark --suite benchmarks/cases --repo benchmarks/fixtures/portfolio-python --output artifacts/t071-validation-20260913 --baseline artifacts/t071-validation-20260913/baseline.json
git diff --no-index --exit-code benchmarks/results/mock-baseline.json artifacts/t071-validation-20260913/baseline.json
uv run python scripts/smoke_installed_wheel.py
```

smoke 恢复只设置本次命令进程的 `PIP_CONFIG_FILE=NUL`、
`PIP_INDEX_URL=https://pypi.org/simple`、空 `PIP_EXTRA_INDEX_URL` 和关闭 pip
版本提示，未改系统配置、依赖版本、TLS 校验、锁文件或 smoke 脚本。预先从官方
源成功取得同版本 annotated-doc；smoke 仍按原脚本的 `--require-hashes` 安装。
首次失败日志 `smoke.log` 与恢复日志 `smoke-official-index.log` 均保留。

两轮 wheel SHA-256 均为
`813b438aba38013ff3be3414441d35debc924320d06b79cb4a034eea3c3b2b0f`；
sdist 为 `7a1c4f62fc8cbb58a976b033974accc33371679b7c1a3a7b824ae6c36bb93114`。
这些构建使用最终运行时代码、报告结算前的文档树，是安装验证产物，不是发布版本。

全量三项 skip 是 `test_repository_tools.py:238`、`test_runs.py:566`、
`test_scanner.py:148` 的既有 Windows symlink 权限限制；三项 warning 是
TestStrategyAgent/TestStrategyOutput 收集警告和 Starlette/httpx 弃用提示。
定向仅含 runs 的 skip 与后一个 warning。未新增 skip 或通过修改依赖隐藏警告。
格式检查曾要求调整 provider 单测 helper 排版，修正后 215 文件检查通过。

实现相对 `339e6e2` 仅九份授权文件；提交后发布独立 Draft PR 供外部审查。
若 PR 以 main 为 base，其累计 Diff 还会显示祖先 PR #12 的六份已审文档，
不是本轮新增规范修改；本轮实现提交自身仅包含上述九份文件。远端 CI 在推送后
按实际检查结果单独报告，不用本地结果冒充尚未执行的远端结果。

## 已知限制与停止点

只有当前进程中的同步 provider 调用共享状态。无跨进程/跨重启保障、credential
rotation 跨 tenancy 合并、live provider 验证或生产容量结论。registry 极端情况下
无可回收槽会明确拒绝新资源，需现有资源恢复或进程生命周期结束，不做后台清理。
本轮保证公开 guard snapshot、分类错误和应用产物不携带内部身份；不声称抵御
进程内任意对象反射、调试器内存读取或外部日志系统自行记录 transport 请求。
不开始 T-072/T-073/cache/preflight/Java/M10，不自动合并 PR，不自行宣布任务关闭。

## 2026-09-13 外部独立审查结算

**当前状态：T-071 — REVIEW PASSED / READY FOR MERGE。** 本节追加最新登记，
前文“待外部独立审查”及实现阶段验证保留为历史。本轮只登记审查结论，不修改
T-071 运行时代码，不开始 T-072，也不宣布 T-071 CLOSED。

### 固定对象与 disposition

- External independent review target：
  `a69e15ee9aaaad9a0bedb8a6c7b645f2c82e4eec`。
- implementation base / 权威规范与 T-070 closure：
  `339e6e28e1d8c7bd79ac6e7303c0e1c5717c45da`。
- 仓库：`wsc0796/specflow-agent`；[PR #13](https://github.com/wsc0796/specflow-agent/pull/13)；
  分支：`feat/t071-provider-resilience-guard`。
- 开始登记时 HEAD 精确等于被审提交，`git status --short` 无输出；PR 远端 head
  同样匹配，状态 OPEN / Draft，mergeCommit 为空。main 核对为
  `2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0`。
- 结论来源：用户转交的固定提交外部独立静态实现复审；本执行者负责登记，
  不冒充再次独立审查或 GitHub 正式 APPROVE。
- **Disposition：PASS / no P1-P2 blocking finding found in reviewed T-071 scope.**

外部复审在已审 T-071 范围内确认：

- endpoint/model/provider-tenancy breaker identity 符合规范，guard 位于真实
  OpenAI-compatible provider attempt 边界。
- 未增加第二套 retry/fallback owner；legacy 与 multi-agent live pipeline
  复用同一 guard contract，mock 不触碰 live breaker。
- HALF_OPEN probe bound、generation 与许可释放逻辑符合冻结契约；availability
  failure 与排除错误分类保持分离。
- `PROVIDER_CIRCUIT_REJECTED` 在 multi-agent handoff 前 fail closed。
- registry 保持有界、单进程；未发现内部 credential/resource identity 进入
  已检查公开应用产物的路径。
- 本次审查范围内未发现新的 P1/P2 blocking correctness finding。

### 四类证据分开记录

| 证据类型 | 对象与结论 | 不能替代的事实 |
| --- | --- | --- |
| implementation evidence | 本报告此前记录的 `a69e15e` 实现、55 个新增场景、定向/全量回归、benchmark 与安装 smoke | 不把旧执行数量当成本次文档登记新执行结果 |
| external static review | 上述固定 SHA 的外部静态复审 PASS，由用户转交并在本节登记 | 不冒充审查者执行了未声明的测试，也不等于 GitHub APPROVE 或合并 |
| remote CI | [CI 34751160302](https://github.com/wsc0796/specflow-agent/actions/runs/34751160302) 的 headSha 为 `a69e15ee9aaaad9a0bedb8a6c7b645f2c82e4eec`；quality、benchmark、security、smoke 全部 success，本轮已重新读取状态 | 该记录绑定 implementation 提交；登记提交推送后的新 CI 另看 PR checks |
| live-provider validation | 未执行 | 不证明 live provider 质量、真实生产 rate-limit/latency、多进程协调、重启持久化或生产容量 |

### 非阻塞 T-073 alias note

`CircuitSnapshot.provider_resource_alias` / `model_alias` 当前是 **registry
resident-slot scoped aliases**。这不阻塞 T-071 closure，不登记为 T-071 blocking
finding。T-073 实施 metrics 时，未经定义不得将其解释为跨 entry / 跨运行稳定的
provider/model identity。本轮只记录该约束，不修改 T-073 规范或实现 metrics。

### 关闭规则与当前停留状态

已读取的 `AGENTS.md` Mandatory workflow 第 4–6 项、M9 REQ-M9-3 及 T-071
AC-071-7/-8 要求质量门、报告、聚焦提交和停止点，但没有明确授权“仅凭静态审查
PASS 就自动 CLOSED”。规范审查入口又明确区分审批、实现关闭和实际合并；既有
T-070 的关闭记录是在合入 main 后核验 integrated tree、报告及 CI，不能把该个案
表述为未写明的全仓库硬性规则。

因此，本轮依用户给定的结论边界登记 **REVIEW PASSED / READY FOR MERGE**。
这里的 READY FOR MERGE 表示审查处置，不自动改变 GitHub Draft 状态，也不授权
合并。PR #13 实际进入 main 后，仍须核对 integrated tree、对应 CI、可读完成报告
及未处理阻塞项，再单独登记 T-071 — CLOSED。本轮不执行该后续登记，不启动 T-072，
不声称 M9 完成、live provider validated 或 production ready。

### 本次文档登记验证

依据 `AGENTS.md` Mandatory workflow 第 4 项，即使本轮仅追加报告，仍执行
完整 pytest 与 Ruff 门禁，另检查 diff 和单文件范围。使用 Windows / Python
3.12.10、现有 `uv.lock`，设置 `UV_FROZEN=true`，结果如下：

| 命令 / 检查 | Exit code | 本次文档登记的实际结果 |
| --- | --- | --- |
| `uv run pytest -v` | 0 | 975 passed、3 skipped、3 warnings，23.80s |
| `uv run ruff check .` | 0 | All checks passed! |
| `uv run ruff format --check .` | 0 | 215 files already formatted |
| `git diff --check` | 0 | 无空白错误，最终追加内容完成后再次检查 |
| `git diff --name-only` 与 append-only 核对 | 0 | 只有本报告；被审提交的原报告正文保留为完整前缀 |
| 对被审 SHA 比较源码、测试、依赖与基准 | 0 | `src/`、`tests/`、`pyproject.toml`、`uv.lock`、`benchmarks/` 无差异 |

三个 skip 为既有 Windows symlink 权限限制；三个 warning 为两项 pytest class
收集警告和 Starlette/httpx 弃用提示，未新增 skip。此处 23.80s 是本轮新执行结果，
不是前文 implementation 阶段 22.58s 的重复引用。原始日志保存在
`C:/Users/50469/temp/specflow-t071-review-registration-20260913/pytest.log`。

依用户长期交付约定，本次只提交并推送该报告登记，更新现有 PR 供 GPT 读取；
登记提交 SHA 在 PR 正文与交付回复记录。implementation 审查目标始终固定为
`a69e15ee9aaaad9a0bedb8a6c7b645f2c82e4eec`，不因追加报告改变被审对象。

## T-071 closure

日期：2026-09-13。**状态：T-071 — CLOSED。** 本节是 PR #13 实际合并并通过
集成核验后的关闭登记。前文 REVIEW PASSED / READY FOR MERGE 保留为历史阶段，
不改写成当时已经关闭；本次不修改任何运行时代码或开始 T-072。

### 固定版本与合并证据

- authoritative spec / gate base：`339e6e28e1d8c7bd79ac6e7303c0e1c5717c45da`。
- implementation commit：`a69e15ee9aaaad9a0bedb8a6c7b645f2c82e4eec`。
- independent review registration：`8ded8a4d568d131082cf5b0664a63d80741cbf88`。
- integrated main SHA：`129783b24f2222d98e099d2184ed4108b75a606d`。
- [PR #13](https://github.com/wsc0796/specflow-agent/pull/13)：GitHub 状态 MERGED，
  mergedAt=`2026-09-13T11:19:30Z`，mergeCommit 与上述 integrated main SHA 一致。
  合并前 head 精确匹配 `8ded8a4`，四项 PR 检查通过、无冲突；依据用户随后明确
  授权执行 merge commit，未 squash/rebase、强推或改写已审历史。
- `git switch main` / `git pull --ff-only` 成功，更新后 `git status --short` 无输出。
  implementation 与 review-registration 两条 `merge-base --is-ancestor ... HEAD`
  检查均 exit 0。此前合并前检查的 exit 1 保留为先前阶段事实，本次不复用它。

### Integrated-tree 与契约核对

`git diff --exit-code 8ded8a4d568d131082cf5b0664a63d80741cbf88 HEAD` 返回 0：
审查登记提交与 integrated main 的**完整 tree** 同为
`3ae2ad7178f2c04993fdf8947d8244df3d7db885`，没有合并时额外修改。

另与 implementation `a69e15e` 比较 `src/`、`tests/`、`pyproject.toml`、
`uv.lock`、`benchmarks/`、`scripts/`、`prompts/`，diff exit 0。包括用户指定的
`llm/resilience.py`、`llm/exceptions.py`、`llm/providers/openai_compatible.py`、
`policy/errors.py`、`agents/adapter.py`、`runner_multi.py` 与
`tests/test_provider_resilience.py`，均保留被审字节，没有未经审查的语义增量。

已结合 main 源码核对以下契约仍适用：endpoint/model/tenancy 内部身份；
PROVIDER_CIRCUIT_REJECTED 不可重试；原 retry/fallback owner；mock bypass；
HALF_OPEN probe 上限与 generation；finally 许可释放；仅计入明确 availability
failure；multi-agent 在 handoff 前 fail closed；有界进程内 registry。
未重新开发测试矩阵，也未借 closure 修改任何上述实现。

### 合并后 main CI

[CI run 34754138442](https://github.com/wsc0796/specflow-agent/actions/runs/34754138442)
是 **main push** 事件，headSha 精确为
`129783b24f2222d98e099d2184ed4108b75a606d`，总体 conclusion=success。

| Job | Conclusion |
| --- | --- |
| quality | success |
| benchmark | success |
| security | success |
| smoke | success |

该记录是本次实际读取的 merge-after CI；前文 PR #13 的合并前 CI 不作为它的
替代。main 上的权威规范、完成报告及独立审查登记均可读，外部静态复审 PASS
继续适用于相同实现 tree；已审 T-071 范围内没有未处理 P1/P2 finding。

### 本地 closure 验证与登记范围

依据 AGENTS 的本地质量门，使用 Windows / Python 3.12.10、原 `uv.lock`、
`UV_FROZEN=true` 在上述 integrated main 上新执行：

| 命令 | Exit code | 本次实际结果 |
| --- | --- | --- |
| `uv run pytest -v` | 0 | 975 passed、3 skipped、3 warnings，23.83s |
| `uv run ruff check .` | 0 | All checks passed! |
| `uv run ruff format --check .` | 0 | 215 files already formatted |
| `git diff --check` | 0 | 无空白错误；追加 closure 后再次检查 |

三项 skip 为既有 Windows symlink 权限限制，三项 warning 为两项 pytest class
收集警告和 Starlette/httpx 弃用提示。没有新增 skip、修改测试或升级依赖。
本轮日志：`C:/Users/50469/temp/specflow-t071-main-closure-20260913/pytest.log`。

关闭登记从已核验 main 创建 `docs/t071-closure-20260913` 分支，只追加本报告。
按既有交付约定提交、推送并发布单独文档 PR；closure commit SHA 在交付及 PR
正文提供，不循环写入自身提交。该文档 PR 的后续处理与已合并的 T-071 实现
分开记录，本轮不自动合并新的文档 PR。

### 保留限制与停止点

- no live-provider quality claim；本次未执行 live-provider validation。
- no production rate-limit/latency/capacity claim。
- no multi-process guarantee；仅进程内同步 provider attempt 协调。
- no restart persistence。
- CircuitSnapshot 的 provider_resource_alias / model_alias 仍为 resident-slot
  aliases；未来 T-073 不得自动将其解释为跨 entry / 跨运行稳定 provider/model
  identity。该非阻塞说明不被关闭登记抹去。

本次 **T-071 — CLOSED** 只结算已审、已集成并有上述证据的任务范围，不代表 M9
或 M10 完成。登记后停止，不实现 execution lanes、T-073 metrics 或其他后续功能。
只有下一次新的 focused session 才评估 T-072 开工门。
