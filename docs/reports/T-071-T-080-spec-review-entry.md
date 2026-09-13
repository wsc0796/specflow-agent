# T-071～T-080 统一规范审查入口

日期：2026-09-13。审查基线：`2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0`。

> 最新状态：固定提交 `c14e0380b6daa1be9fa49101bfd79ccb582cd46c` 的外部静态
> 规范复审已结案，见文末“c14e038 规范结案与 T-071 开工门”。此前待重审、验证和
> 发布记录保留为历史；规范 findings 关闭不代表任何运行时任务已实现或验收。

## 初次交付与审查对象（558004b 历史记录）

本次应用户要求，将后续十项 T 任务集中到独立分支，供 GPT 审查规范。
十项规范已经存在于上述 `main` 基线，本次只新增这个审查入口；规范正文、
源码、测试、依赖与学习进度均未修改。因此请阅读下面链接的完整规范及其
依赖文档，不能仅依据本 PR 的新增 Diff 判断十项规范是否合理。

这是规范审查材料，不是十项功能的实现报告，也不宣告任务关闭、实施门禁
通过或 M9/M10 验收通过。后续发现的问题应先复验，再在本分支追加相应的
规范修订提交；涉及产品实现的问题应明确归属及实施范围。

## 规范清单与依赖

下表是阅读导航，具体门禁和验收条款以链接的规范原文为准。

| 任务 | 完整规范 | 关键实施前置条件 |
| --- | --- | --- |
| T-071 | [Provider Resilience Guard](../tasks/T-071-provider-resilience-guard.md) | T-070 关闭 |
| T-072 | [Execution Lanes and Bounded Admission](../tasks/T-072-execution-lanes-and-bounded-admission.md) | T-071 关闭 |
| T-073 | [Runtime Saturation and Latency Metrics](../tasks/T-073-runtime-saturation-and-latency-metrics.md) | T-072 关闭 |
| T-074 | [Content-Addressed Evidence and Context Cache](../tasks/T-074-content-addressed-evidence-and-context-cache.md) | T-073 关闭 |
| T-075 | [Unified Run Preflight Validator](../tasks/T-075-unified-run-preflight-validator.md) | T-074 关闭 |
| T-076 | [Java/Maven Repository Profile and cms-flow Benchmark](../tasks/T-076-java-maven-repository-profile-and-cms-flow-benchmark.md) | T-070～T-075 关闭且 runtime review 通过 |
| T-077 | [Guarantee Boundary Ledger and Declaration Registry](../tasks/T-077-guarantee-boundary-ledger.md) | 完整 REQ-M10-12 门禁，包括 M10 冻结批准、声明来源可读、T-070～T-075 各自关闭证据 |
| T-078 | [Deterministic Failpoint Interface and Interrupt Matrix](../tasks/T-078-deterministic-failpoints.md) | T-077 关闭 |
| T-080 | [Evidence and Artifact Integrity Contract Audit](../tasks/T-080-evidence-and-artifact-integrity-audit.md) | T-078 关闭，并完成本任务字段级细化与冻结 |
| T-079 | [Run-Local and Project-Level Assurance Reporting](../tasks/T-079-run-local-and-project-assurance-reporting.md) | T-078、T-080 关闭，并完成本任务字段级细化与冻结 |

M9 顺序为 T-071 → T-072 → T-073 → T-074 → T-075 → runtime review → T-076，
其中入口还要求 T-070 关闭。M10 顺序为 T-077 → T-078 → T-080 → T-079 →
milestone assurance review；T-076 不是 M10 的前置条件。

## 配套材料与版本解释

- [M9 总规范](../tasks/M9-runtime-resilience-efficiency.md)与[M9 冻结报告](M9-specification-freeze-report.md)。
- [M10 总规范](../tasks/M10-runtime-assurance-verification.md)与[M10 冻结报告](M10-specification-freeze-report.md)。
- [任务编号映射](../tasks/TASK-IDENTITY-MAP-2026-09-13.md)：本入口的 T-072/T-073 使用 M9 含义；PR #9 的历史同号修复已映射为 T-083/T-084，学习任务使用 LEARN 编号。
- [T-070 完成报告](T-070-completion-report.md)与[运行时修复集成报告](runtime-repairs-integration-2026-09-13.md)，用于核对前置实现证据。

规范中的 START_HEAD、源代码行号和“当时依赖未满足”等描述属于各自冻结时的
历史快照。审查时应区分声明来源提交、当前审查基线和实际测试提交；若与当前
代码不一致，请记录具体差异，不能把历史观察自动当成当前事实。
PR #11 已合并不等于所有任务的独立关闭门禁已经通过，仍需逐项检查报告与提交。

T-079/T-080 目前冻结的是范围、入口和判断标准，字段级细节保留到前置任务
关闭后细化。请分别判断“当前冻结层级是否足够”和“实施前尚需补齐什么”。

## 给 GPT 的审查请求

请审查本提交中的十项完整规范、两个里程碑规范及配套冻结报告，并结合上述
代码基线检查方案是否仍适用。审查重点如下：

1. 每项任务的目标、允许改动范围、失败语义和验收条件是否一致且可验证。
2. 熔断、重试、执行槽位、single-flight、缓存与 preflight 的责任边界是否
   冲突；异常、超时和取消路径是否有明确归属，是否会重复执行或遗漏释放。
3. legacy、multi-agent、mock 与 Run API 的适用范围是否明确，是否保留既有
   schema、DLP、fail-closed 与产物契约。
4. 依赖链是否闭合，编号是否一致；M10 是否仅验证已有声明，是否清楚区分
   evidence hash、产物字节完整性、freshness，以及单次运行与项目级保证。
5. 规范承诺是否超出单进程边界，测试能否产生足以支持结论的可复现证据。

请按严重程度列出可操作发现，并给出文件/条款、触发条件或反例、影响和最小
修订建议。区分源码/规范发现、实际复现和未验证项；不能访问的材料请逐项列出。
没有执行实验时不要声称已复现；无法证明实施门禁满足时不要宣告可以开始实施。

## 初次发布验证记录（558004b 历史记录）

本节记录本次文档交付的实际验证结果，不代表未来任务的行为验证。

- `uv run pytest -v`：920 passed，3 skipped，3 warnings；3 项跳过均涉及
  Windows 符号链接创建权限。
- `uv run ruff check .`：通过；既有 `tests/test_coordinator.py:113` 的
  `noqa` 指令格式警告仍存在。
- `uv run ruff format --check .`：通过，213 files already formatted。
- 本文 17 个相对文件链接均可解析。
- 对比审查基线，`docs/tasks/`、`src/`、`tests/`、`uv.lock` 和
  `pyproject.toml` 无差异；本次交付仅新增本文。

## 外部重审修订结算

### 对象、范围和当前状态

- 日期：2026-09-13；来源：用户转交的 PR #12 外部规范重审 S12-01～S12-04，均为 P2。
- 仓库：`wsc0796/specflow-agent`；PR：[#12](https://github.com/wsc0796/specflow-agent/pull/12)。
- 工作分支：`docs/t071-t080-spec-review`。
- 固定审查提交及本轮修订起点 HEAD：`558004b2bfc46ddcf76317ba30123a12f486445f`。
- PR base：`main @ 2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0`；本地 merge-base 与其一致。
- 修改前 `git status --short` 无输出；工作分支、HEAD 与固定对象一致，没有混入用户改动。
- 修改对象仅为 T-071、T-075、T-076、T-077 四份规范和本报告，交付为该 HEAD 上的
  未提交文档 Diff。状态为 **AMENDMENT PROPOSED / 待重审**，四项发现尚待外部重审结案。

已读取 AGENTS、冻结基线、PR 正文、本入口及 T-071～T-080 的完整正文，同时交叉
读取 T-070、M9/M10 总规范、两份历史 freeze report、TASK-IDENTITY-MAP 和
`single_flight.py`。本轮是已确认规范问题的修订，不重开 handoff payload R1/P2，
不实现任何 T-071～T-080 功能。既有规范中的未来 implementation surface 和验收
测试描述，不是本轮生产代码或测试文件的修改授权。

### 四项发现与修订映射

| 发现 | 修改文件与条款 | 修订内容 | Disposition |
| --- | --- | --- | --- |
| S12-01 / P2 | [T-071](../tasks/T-071-provider-resilience-guard.md)：REQ-071-1/-7/-8、Boundaries、AC-071-2 | 使用有界不透明 provider-resource alias + effective model；身份区分 effective endpoint；同后端可共享、不同后端隔离；mock 不读写 live breaker；公开数据只用安全别名 | 已形成修订；AMENDMENT PROPOSED / 待重审，未宣告关闭 |
| S12-02 / P2 | [T-075](../tasks/T-075-unified-run-preflight-validator.md)：REQ-075-2/-7、AC-075-3 | 保留所有请求适用的安全、输入、速率计数及静态检查；先确认 ownership，再判断新容量；follower 仅有界等待；T-072 原子接纳负责 owner 饱和及竞争失败 | 已形成修订；AMENDMENT PROPOSED / 待重审，未宣告关闭 |
| S12-03 / P2 | [T-076](../tasks/T-076-java-maven-repository-profile-and-cms-flow-benchmark.md)：REQ-076-3/-5/-11、Boundaries、AC-076-6 | Java/POM/受支持配置的有效读取面同步 early snapshot、equivalence key、T-074 cache key/validation；补齐语义版本和未来实施文件；保持读取限额及 Python benchmark 含义 | 已形成修订；AMENDMENT PROPOSED / 待重审，未宣告关闭 |
| S12-04 / P2 | [T-077](../tasks/T-077-guarantee-boundary-ledger.md)：REQ-077-4/-8、AC-077-5 | 确定性绑定 declaration/source、tested-code/config、显式 evidence set、rules/schema；允许有效新证据改变判断；排除输出自反馈，保留有效反证及四条件验证 | 已形成修订；AMENDMENT PROPOSED / 待重审，未宣告关闭 |

四份规范顶部均标注本次日期、来源提交、待重审状态及实施门未因此满足。

### 关键反例与交叉契约核对

1. **S12-01：资源隔离。** AC-071-2 要求 same protocol/model + different backend
   时 A 熔断不阻断 B，same backend/effective model 时可共享；mock 不读写状态或
   消耗 probe。REQ-071-8 对齐 T-073 的有界别名和 DLP 要求，不把原始 URL、凭据或
   用户/仓库内容作为公开 metrics、trace、artifact 数据。M9 freeze report 中旧
   `(provider, model)` 表述保留为冻结时的历史决定，本次 amendment 明确提出替代身份。
2. **S12-02：follower 与容量。** AC-075-3 分别要求：饱和同 key 可加入 owner；饱和
   不同 key 由原子接纳拒绝；同 key 仍须通过认证、repo 授权及速率门；观察有容量但
   admission race 失败时显式返回 T-072 饱和结果。对应 T-070 REQ-070-2/-3/-6 和
   T-072 REQ-072-8，保留独立审计身份、既有计数与清理语义，没有第二份昂贵执行。
3. **S12-03：未来读取面的身份覆盖。** 在固定提交的
   `src/specflow/single_flight.py`，`_EVIDENCE_PATTERNS` 仅列 Python/Markdown/YAML/
   TOML/CFG；`repository_snapshot()` 依此筛选，`prepare_run()` 将其摘要与
   `CONTRACT_VERSIONS` 纳入 key。本轮源码阅读确认此过滤边界，未重新执行附件所述
   文件变更实验。当前 Python-only 读取面不据此判为现有运行时缺陷；Java 成为真实
   evidence 输入时，T-070 REQ-070-1 和 T-074 REQ-074-2/-3 要求同步覆盖。AC-076-6
   明确未来 POM/Java/properties/YAML 内容及语义版本变化的身份回归，保留无关/排除
   文件对照和 Python 12-case 原意。该约束不要求原子全仓库快照或运行期 mutation 支持。
4. **S12-04：完整确定性输入。** 相同 checkout 可以显式收到新的有效 execution
   evidence；此时 `declared` 依法变为 `verified` 不违反确定性。AC-077-5 改为
   比较完整输入相同的 normalized body，排除输出 ledger 隐式回流。skipped、
   version-mismatched、unexecuted evidence 不能验证声明，有效反证仍为 `refuted`，
   重跑或汇总不能隐去；REQ-M10-2 的四个独立条件全部保留。

依赖顺序保持：

- M9：T-070 → T-071 → T-072 → T-073 → T-074 → T-075 → runtime review → T-076。
- M10：T-077 → T-078 → T-080 → T-079 → assurance review；完整 REQ-M10-12 仍适用，
  T-079/T-080 的字段级细化与冻结要求不变，T-076 仍不是 M10 前置条件。

没有修改 TASK-IDENTITY-MAP、历史 M9/M10 freeze report 或其他 task spec；历史
“当时冻结/当时依赖未满足”记录不改写成本轮结论。没有宣告 T-071 可实施、T-077
解锁、M9/M10 完成、M10 assurance passed 或学习 Gate 完成。

### 本轮验证记录

本节仅记录本轮实际命令，不复用上方初次发布或历史 freeze report 的测试数量。
验证运行于 Windows、Python 3.12.10，使用现有 `uv.lock`，以 `UV_FROZEN=true`
避免锁文件更新；不升级依赖、不修改测试或增加 skip，不调用 live provider。

| 命令 / 检查 | Exit code | 本轮实际结果 |
| --- | --- | --- |
| `uv run python --version` | 0 | Python 3.12.10 |
| `uv run pytest -v` | 0 | 920 passed、0 failed、3 skipped、3 warnings，26.91s |
| `uv run ruff check .` | 0 | All checks passed!；本轮无 Ruff warning |
| `uv run ruff format --check .` | 0 | 213 files already formatted |
| `git diff --check` | 0 | 无空白错误；最终报告更新后再次检查 |
| `uv run python <本轮日志目录>/check_documents.py` | 0 | 仅五份允许文件；REQ/AC 定义及编号未改变，92 个引用、22 个相对链接及锚点解析通过；四项映射和依赖顺序通过 |
| `git branch --show-current` / `git rev-parse HEAD` | 0 | 分支与完整 HEAD 仍为上列固定对象 |
| `git status --short` | 0 | 恰有五份允许文档为未暂存 `M`；无暂存或未跟踪文件 |

三项 skip 分别为 `tests/test_repository_tools.py:238`、`tests/test_runs.py:566`、
`tests/test_scanner.py:148` 的 Windows symlink 权限限制。三项 warning 为
`TestStrategyAgent`、`TestStrategyOutput` 的 pytest collection warning，以及
Starlette/httpx deprecation warning。没有新增 skip 或修改任何测试。

一次性文档检查初次 exit 1 的原因是检查脚本未匹配带缩进的 Markdown 依赖表；
仅修正仓库外脚本的匹配规则后通过，没有为检查通过修改 M9/M10 依赖表。Git 曾
提示工作区 LF 将按既有配置转换为 CRLF；交付文件恢复该工作区换行形式，未修改
Git 配置。最终 `git diff --check` 无此提示及空白错误。

本轮原始 pytest 日志及文档检查脚本位于仓库外：
`C:/Users/50469/temp/specflow-pr12-amendment-20260913/`。本轮通过数量恰与旧记录
相同，以上数字来自新执行的 `pytest.log`，并非复制历史结果。既有回归通过只证明
当前测试套件通过，不证明尚未实现的 breaker/preflight/Java/ledger 新验收行为。

### 未决项与本地交付边界（发布授权前记录）

四项修订均已映射到 REQ/AC，仍等待外部重审；未来行为测试属于各自实施任务，
本轮文档修改和既有回归通过均不能代替它们。目前未发现需要第六份文档才能消除
的真实规范冲突，因此不请求扩大范围。未提交、推送、合并、APPROVE 或关闭 PR，
不自动启动下一任务。完成本地验证及 Diff 交付后停止。

### 后续发布授权（2026-09-13）

本地交付后，用户要求让 GPT 能访问本轮修订，因此授权将上述五份文档提交并
推送到现有 `docs/t071-t080-spec-review` 分支，更新现有 PR #12 的正文和固定
文件链接。上节“未提交、未推送”是该次本地交付时的状态，不代表后续发布状态。
发布提交的完整 SHA 及可访问性由 PR 正文和 GitHub 提交记录提供，避免在文档中
循环登记自身提交。PR 保持草稿，四项 amendment 仍待外部重审；发布不构成
规范批准、PR 合并或任何运行时任务的实施许可。

## a178735 复审结算与 R12 修订

### 固定对象与复审来源

- 日期：2026-09-13；分支：`docs/t071-t080-spec-review`。
- 固定复审提交、本轮起点及当前完整 HEAD：`a178735b335628d650e9755c91545c94af926c9b`。
- 修改前 `git status --short` 无输出，本地 HEAD 与 PR #12 远端 head 均匹配固定提交。
- 来源：用户转交的针对该固定提交的静态规范复审及修订指令；以下 S12 结算登记该
  复审结论，不冒充本执行者完成了独立运行时验证或 GitHub 正式 APPROVE。
- 本轮仅修改 [T-071](../tasks/T-071-provider-resilience-guard.md)、
  [T-077](../tasks/T-077-guarantee-boundary-ledger.md) 和本报告，交付为未提交 Diff。

审查使用 T-070～T-080 十一份完整规范及 AGENTS、冻结基线、PR 正文、M9/M10
总规范与冻结报告、编号映射和 `single_flight.py`。本会话此前已完整阅读的未改
材料，经 Git 比对确认与当前固定提交一致；T-071/T-077 和本入口重新读取完整
当前正文。T-075/T-076 沿用此前完整阅读及修订内容，本轮不重新修改其已关闭发现。

### 旧发现的最新 disposition

| 发现 | 固定提交 a178735 的静态复审结论 | 当前 disposition / 边界 |
| --- | --- | --- |
| S12-01 / P2 | endpoint 隔离方向正确，但遗漏 provider tenancy discriminator | superseded by R12-01 / P2；继续 open |
| S12-02 / P2 | preflight 与 follower 容量边界问题已解决 | **RESOLVED / CLOSED BY STATIC SPEC RE-REVIEW**；仅关闭规范发现，不代表 T-075 已实现 |
| S12-03 / P2 | Java 读取面同步 equivalence/cache identity 的规范问题已解决 | **RESOLVED / CLOSED BY STATIC SPEC RE-REVIEW**；仅关闭规范发现，不代表 T-076 已实现 |
| S12-04 / P2 | 核心 determinism 问题已解决，但跨运行 refutation anti-removal 的 source-of-truth 不明确 | superseded by R12-02 / P2；继续 open |

### R12 修订与验收映射

| 发现 | 修改条款 | 关键 Diff | 本轮 disposition |
| --- | --- | --- | --- |
| R12-01 / P2 | T-071 REQ-071-1/-7/-8、Boundaries、AC-071-2 | 内部 key 为 backend resource + effective model + provider tenancy discriminator；保留 endpoint 隔离，默认按凭据/tenancy 隔离配额域；公开 audit 只用安全别名，内部指纹不输出或持久化 | open；修订已形成，AMENDMENT PROPOSED / 待重审 |
| R12-02 / P2 | T-077 REQ-077-4/-6/-8、Boundaries、AC-077-5 | `refuted` 保留限定在同一显式 evidence snapshot 及其 lineage；manifest 派生的 evidence_set_id 进入输入与输出身份；不同集合的判断显式分开；删除无历史真相源的自动 anti-removal 承诺 | open；修订已形成，AMENDMENT PROPOSED / 待重审 |

**R12-01 的依据与预期验收。** 当前 `prepare_run()` 已将
`sha256(config.api_key.encode()).hexdigest()` 放入仅驻留进程内的 effective-provider
身份，源码说明不同凭据可能对应不同 provider tenancy。REQ-071-3 又允许 429
rate-limit failure 计入健康状态，因此同 endpoint/model 不足以证明可共享 breaker。
本轮 AC-071-2 要求 A/B tenancy 的失败计数隔离，A 熔断时健康 B 仍允许；同资源、
model、tenancy 可共享；raw credential 不进入 key，internal fingerprint/discriminator
不进入 metrics/trace/artifact/log；auth failure 仍不计入 breaker health。若不同
credentials 的 tenancy 要共享，须说明配额/可用性域可安全共享并有对应测试证据。
本轮仅依据源码与规范修订未来验收，未执行 live provider 或 breaker 实验。

**R12-02 的依据与预期验收。** 采用当前显式 evidence set 方案，不引入 cumulative
history。集合 X 含有效反证时，由 X 产生的每个 ledger/rollup/summary 都保留
`refuted`；集合 Y 的成员不同则其 `evidence_set_id` 必须不同。Y 可依法得出另一
判断，但不能冒充 X 的同一连续 evidence lineage，也不能重标记所展示的 X 反证。
仅给定 Y 不能知道 X 是否曾存在，因此移除“必须自动检测/报告过去反证缺失”的
强要求。AC-077-5 同时验证相同完整输入的确定性、集合 ID 的可见变化、反证在
同一谱系中的保留，以及输出 ledger 不自动成为后续输入；无效或未执行证据仍
不能产生 `verified`。M10 的四条件验证及 summary/rollup 不隐藏反证的规则不变。

### 本轮独立验证记录

环境为 Windows、Python 3.12.10，现有 `uv.lock` 与 `.venv` 可用，设置
`UV_FROZEN=true`。下面只填本轮实际执行结果，不复用先前 26.91s 的测试记录。

| 命令 / 检查 | Exit code | 本轮实际输出 |
| --- | --- | --- |
| `uv run python --version` | 0 | Python 3.12.10 |
| `uv run pytest -v` | 0 | 920 passed、0 failed、3 skipped、3 warnings，51.05s |
| `uv run ruff check .` | 0 | All checks passed!；本轮无 Ruff warning |
| `uv run ruff format --check .` | 0 | 213 files already formatted |
| `git diff --check` | 0 | 无空白错误，最终报告更新后复查 |
| `uv run python <本轮日志目录>/check_documents.py` | 0 | 恰好三份允许文件；REQ/AC 定义无丢失或重复；60 个引用及 24 个相对链接/锚点解析通过；两项 R12 映射和 M9/M10 顺序通过 |
| `git branch --show-current` / `git rev-parse HEAD` | 0 | `docs/t071-t080-spec-review` / `a178735b335628d650e9755c91545c94af926c9b` |
| `git status --short` | 0 | 仅 T-071、T-077、本报告为未暂存 `M`；无暂存或未跟踪文件 |

三项 skip 为 `tests/test_repository_tools.py:238`、`tests/test_runs.py:566`、
`tests/test_scanner.py:148` 的 Windows symlink 权限限制；三项 warning 为
`TestStrategyAgent`、`TestStrategyOutput` 的 pytest collection warning 和
Starlette/httpx deprecation warning。未修改测试或新增 skip。
Git 初次检查提示 LF 将按既有配置转为 CRLF；三份交付文件保留工作区 CRLF
形式，未修改 Git 配置，最终 diff 检查无空白问题。

本轮日志目录：`C:/Users/50469/temp/specflow-pr12-r12-20260913/`，包含新执行的
`pytest.log`、一次性文档检查脚本和交付 Diff。历史日志未覆盖，本轮数量取自
本轮原始输出。上述回归结果不替代尚未实施的 tenancy breaker 或 ledger 验收。

### 规范冲突与停止边界

未发现必须扩大到第四份文件才能消除的规范冲突。内部 tenancy 身份不公开，符合
M9/T-073 的安全观测边界；同一 evidence snapshot 的反证保留符合 M10 与
T-079 的汇总规则，不借新集合隐去旧结论。M9/M10 依赖顺序、编号映射及历史
freeze report 均保持不变，未修改 T-075/T-076，也未新增持久化系统。
R12-01/R12-02 保持 open 等待外部重审；规范修订和既有测试结果均不代表产品能力
已验证或依赖门满足。本轮按用户要求停在本地未提交 Diff，不 commit/push，
不 merge、APPROVE、关闭 PR 或启动任何运行时实现。

### R12 本地交付后的发布授权（2026-09-13）

用户随后明确约定：以后修改及验证完成后直接提交，方便 GPT 审查。本次据此将
R12 的三份文档提交并推送至现有审查分支，更新 PR #12 的固定提交与文件链接。
上节本地停止状态及验证时的 HEAD/status 保留为阶段记录；发布提交的完整 SHA
以 PR 正文和 GitHub 提交记录为准。PR 保持草稿；R12 两项仍待外部重审，
不因发布而关闭规范发现、合并 PR 或启动运行时实现。

## c14e038 规范结案与 T-071 开工门

### 外部静态规范复审登记（2026-09-13）

固定被审提交：`c14e0380b6daa1be9fa49101bfd79ccb582cd46c`；核对时 PR #12
为 OPEN / Draft，head 匹配。main 仍为 `2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0`。
以下登记用户本轮明确转交的外部静态复审结论，不冒充 GitHub 正式 APPROVE，
不将其解释为 breaker、preflight、Java profile 或 ledger 的运行时验证。

| 发现 | 外部复审 disposition |
| --- | --- |
| R12-01 / P2 | **RESOLVED / CLOSED BY STATIC SPEC RE-REVIEW** |
| R12-02 / P2 | **RESOLVED / CLOSED BY STATIC SPEC RE-REVIEW** |
| S12-01 | S12-01 → R12-01 → **CLOSED** |
| S12-02 | **CLOSED**，仅规范发现 |
| S12-03 | **CLOSED**，仅规范发现 |
| S12-04 | S12-04 → R12-02 → **CLOSED** |

外部静态复审结论：**未发现新的 P1/P2 规范阻塞项**。本轮不重写上述历史
disposition，不重新修订已通过的条款。T-071/T-077 顶部登记 amendment 冻结；
T-071 的权威 REQ/AC 是 `c14e038` 中包含 endpoint、tenancy 内部身份及公开
audit 隔离的完整版本，不使用 main 上尚未含 amendment 的旧正文作为实现依据。
T-075/T-076 的既有修订与静态结案保持原样，未改正文或旧冻结报告。

### T-070 关闭核验

详细七项核验、来源提交、集成主线、复审证据及单进程限制登记在
[T-070 完成报告的关闭章节](T-070-completion-report.md)。该登记是对已经合并的
T-070 实现结算，不新增运行时代码，也不由 PR #12 的规范复审代替实现证据。

### 最终开工门的解释

用户列出的四个检查条件逐项保留：权威 amendment、T-070 CLOSED、clean worktree、
新 focused session / branch。不得把文档修改期间的工作区称为 clean，也不得把
本次 gate-closure 会话自动当成新的 T-071 实现会话。

本次将规范冻结与 T-070 关闭登记提交、推送到审查分支后，核验干净状态，并可
从该登记提交准备独立的 T-071 分支。权威规范在命名提交上可读不等同于 PR #12
已合并；本轮不自动合并。新实现会话须检出包含该规范和关闭记录的独立分支，
重新核对其 HEAD/clean 状态，方可作出完整开工门通过结论。本轮停止于登记与
交付，不启动 T-071，不把仍未建立的新 focused session 宣称为已满足。

### 本次登记验证

本轮使用 Windows / Python 3.12.10、现有 `uv.lock` 和 `UV_FROZEN=true`。
执行对象为登记分支 `c14e038` 加本轮文档；与 main 的运行时代码、测试、基准、
脚本、prompt 和依赖无差异，因此下列本地结果可作为 main 同一实现的补充证据。
main 自身的 CI 结果及其精确 SHA 则单独记录在 T-070 关闭章节。

| 命令 / 检查 | Exit code | 本轮实际结果 |
| --- | --- | --- |
| 定向 `uv run pytest ... -v`（八文件完整命令见 T-070 关闭章节） | 0 | 175 passed、1 skipped、1 warning，23.96s |
| `uv run pytest -v` | 0 | 920 passed、3 skipped、3 warnings，22.64s |
| `uv run ruff check .` | 0 | All checks passed! |
| `uv run ruff format --check .` | 0 | 213 files already formatted |
| `uv run python scripts/check_secrets.py` | 0 | 无凭据模式发现 |
| `git diff --check` | 0 | 无空白错误，最终报告更新后再次检查 |
| 文档范围与契约静态核对 | 0 | 仅 T-071/T-077 状态登记、T-070 完成报告与本入口；REQ/AC 正文、历史报告、编号和依赖顺序保留，相对链接可解析 |

定向 skip 为 `test_runs.py:566` 的 Windows symlink 权限；全量另有
`test_repository_tools.py:238` 与 `test_scanner.py:148` 同类 skip。全量三个
warning 为 TestStrategyAgent/TestStrategyOutput 的收集警告及 Starlette/httpx
弃用提示；定向只有后者。未新增 skip、未修改依赖或测试。
证据目录：`C:/Users/50469/temp/specflow-t071-gate-closure-20260913/`。

本轮提交前四份文档为已知未暂存改动；提交推送后须再次确认 clean，并在 PR
正文记录实际登记提交及独立准备分支。文档自身不循环写入自己的提交 SHA。
