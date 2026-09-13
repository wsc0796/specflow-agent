# T-071～T-080 统一规范审查入口

日期：2026-09-13。审查基线：`2959a2f9ac8c7d0d3b5a2217102d0ce0ed223ed0`。

> 当前工作区包含针对 PR #12 固定提交 `558004b2bfc46ddcf76317ba30123a12f486445f`
> 的四项规范修订，状态为 **AMENDMENT PROPOSED / 待重审**。下文初次交付与发布
> 验证记录保留为历史；本轮修改及新执行的验证见“外部重审修订结算”，不代表实现放行。

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
