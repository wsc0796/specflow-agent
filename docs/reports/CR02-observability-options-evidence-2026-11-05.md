# SPEC-FLOW 可观测性方案选型与证据

日期：2026-11-05（Asia/Shanghai）。性质：源码与既有验证记录对照、选型建议；不是实施批准或完成报告。

## 结论

**当前推荐方案 A：复用现有调用入口与事务账本，补齐证据诊断和明确缺失的采集字段。方案 B 保留为有条件的演进方向，方案 C 暂缓。**

用户提供的方案末尾提出“先用 A 的最小切片验证必要性”，这一点适合当前项目；开头“默认推荐 B”的判断则需要根据当前源码调整。身份关联、调用拦截接点和持久事件入口已经存在，没有证据要求现在再建立 ObservationContext、Instrumentation、EventRecorder、ObservabilitySink 四项新抽象。

A 可以包含一个职责清楚的诊断导出模块。是否有独立文件或目录，不是 A/B 的实质分界；分界在于是否引入新的横切采集体系、上下文传播机制和统一投递抽象。当前首先需要让现有证据可解释、可复查，而不是替换其生产方式。

## 范围与证据版本

- 唯一产品 checkout：`C:/Users/50469/specflow-h04-f03-20261023`。
- 核对 HEAD：`99a8baa0c2de38751a6ccce48d8b97e85ad1ec90`；当前分支沿用 `codex/h04-f03-offline-verification`。
- B1/B2 脚本、测试及部分文档是未提交工作树内容，不属于该 HEAD。B2 实现窗口仍在更新其三个文件；本报告记录读取时状态。
- 用户方案来源：[三套候选方案原文](C:/Users/50469/.codex/attachments/ab4a4adf-6760-47ad-aecb-316ee57233b5/已粘贴的文本.txt)。原文自述尚未做当前源码验证；其中相对评分不当作实测数据或工期。
- 本次授权：将技术合伙人原则落实到整个项目，收集证据并判断方案。本次只补明根 AGENTS.md 的适用范围并新增本报告，不实施可观测性功能，不改 B2、src、候选判据或依赖，不运行模型，不提交或推送。
- 根 AGENTS.md 原已包含用户给出的九项完整原则，本次保留原文并补明全项目覆盖，不重复粘贴九项内容。检查时未发现仓库内其他 AGENTS.md / AGENTS.override.md。

## 已核实的源码事实

下表中的“已有”表示检查到相应实现或测试定义；不表示本次重新运行过测试。

| 编号 | 证据 | 事实及其选型影响 |
| --- | --- | --- |
| E01 | [Store.event](../../src/specflow/contract_review/store.py#L248) | Review 事件统一包含 review/input/job、event_seq、时间、payload 引用/指纹及完整性信息，并使用调用方传入的数据库连接。跨模块事件不是各写一套无关联日志。payload 仍需按事件类型解释，统一外层不等于所有业务内容都有统一强类型校验。 |
| E02 | [ReviewWorker.model_call](../../src/specflow/contract_review/worker.py#L232)、[perform_io](../../src/specflow/contract_review/worker.py#L163) | 模型准备、预留调用、重试和物理执行已有集中接点；工具也经过 perform_io。无需先引入通用 AOP 框架才能记录调用。 |
| E03 | [DynamicLedger.reserve_call](../../src/specflow/contract_review/dynamic_ledger.py#L130) | 已保存 payload、material_entries、input/profile hash、逻辑调用、物理执行、父子身份。应映射已有 review_id/input_revision_id/job_id/call_id/logical_call_id，避免另造一套 Run/Call 身份源。 |
| E04 | [RunState.build](../../src/specflow/contract_review/dynamic_context.py#L80)、[上下文测试](../../tests/contract_review/test_dynamic_context.py#L66) | 必需规则原文先装载；必保留内容超预算即失败，可选观察另按预算选择并记录省略。现有目标不是任意裁掉关键规则后继续成功。 |
| E05 | [父方验收](../../src/specflow/contract_review/dynamic_ledger.py#L406)、[验收提交测试](../../tests/contract_review/test_dynamic_workflow.py#L360) | 父请求须实际包含完整子结果，验收记录与接受动作一起处理；已有失败动作不得留下验收结果的测试。不能把函数正常返回直接等同于父方验收。 |
| E06 | [commit_report](../../src/specflow/contract_review/execution.py#L807)、[项目决定发布](../../src/specflow/contract_review/decisions.py#L210) | 正式报告提交使用事务；规则发布也在事务内保存决定、版本及幂等响应。Review 事件与项目决定记录是不同业务记录，不能假设所有正式动作都只来自同一事件流，也不能把必需审计改成异步尽力投递。 |
| E07 | [Queries.diagnostics](../../src/specflow/contract_review/queries.py#L171)、[ReviewEvidence](../../scripts/contract_review/review_evidence.py#L22)、[CLI](../../src/specflow/contract_review/cli.py#L42) | 已有状态、步骤、期限、最后调用、事件和报告查询，以及证据 JSON 采集。缺口主要在按报告联查、解释与完整历史输入复查，而非从零增加查询。 |
| E08 | [输入身份采集](../../scripts/contract_review/review_evidence.py#L221)、[B2 交付断言](../../tests/contract_review/test_memory_case_prep.py#L550) | 脚本保存输入身份，B2 测试另外读取完整 Store 输入；测试中的完整输入证明不能自动当作生产诊断导出能力。AC10 分别检查实收一致、正文完整和无泄漏，应该继续保留。 |
| E09 | [工具拒绝路径](../../src/specflow/contract_review/dynamic_runner.py#L320)、[Provider](../../src/specflow/contract_review/provider.py#L54) | 无效工具结果被归为 TOOL_RESULT_INVALID，原结果不可用；Provider 对外主要返回 content/model/usage。失败阶段、字段级原因、上游请求 ID、HTTP 状态和 finish_reason 等可复查信息存在补充空间。 |
| E10 | [用量结算](../../src/specflow/contract_review/execution.py#L611)、[F01 试验账本](../../scripts/contract_review/f01_trial_guard.py#L135) | 已有 Review 累计 Token 和未知/预留量；F01 专用账本另有运输层请求校验、时间与费用上限。需要的是按 B2 case/trial 跨多个 Review 汇总及身份关联，不是新建一切计费逻辑。旧 F01 模型、费率和时间窗口不能直接沿用为新试验授权。 |
| E11 | [HTTP 请求投影测试](../../tests/contract_review/test_dynamic_workflow.py#L678)、[Provider 离线测试](../../tests/contract_review/test_dynamic_provider.py#L37) | 已有 MockTransport 下 HTTP JSON 与请求投影对应的测试定义。因此不能说项目完全没有传输边界验证；仍须区分受控传输证据和真实远端收讫/语义效果。 |
| E12 | [共享账本](../../src/specflow/contract_review/shared_ledger.py#L1) | 影响发现与 Review 已共用部分调用生命周期入口。存在多种业务不等于必须新建通用 Observability 平台；先验证现有业务身份到诊断视图的映射。 |

另核对了 pyproject.toml 与 uv.lock，未找到 OpenTelemetry 或 Prometheus 依赖声明。根 AGENTS.md 已明确后置完整 OTel/Grafana/Tempo/Jaeger 平台工作；这不等于永久禁止薄 OTel 接入，但当前任务没有新增依赖需求。

## 既有运行证据与边界

来源：[B2 实施报告](CR02-PREP-B2-offline-readiness.md)、[原始命令退出记录](D:/Downloads/agent学习/AI_HANDOFF/2026-11-05-B2-离线验证产物/command-results.jsonl)。

- B2 报告记录定向回归通过，并记录五例及独立 demo 的 62 次核心受控模型调用。它们是工程传递证据，不是真实模型语义结果，也不是 62 个独立业务样本。
- 读取时报告记录首轮全库 1743 passed / 3 skipped / 3 warnings，退出记录包含 full-suite-01 exit 0；随后修正了证据轴同步问题，第二轮全库仍在运行。首轮结果不用于签署修正后候选完成。
- 最新反例：补采发现缺证后，collection_complete=false，但 evidence_status 仍为 COMPLETE。报告记录原始失败、修正和定向回归。该事实说明采集器输出之间的一致性值得优先验证；增加 Span 数量不会自动消除此类问题。
- Oracle 保持待独立复核/未冻结，真实语义 NOT_RUN。本次没有重跑上述测试，也没有接管 B2 运行进程。

## 对三套方案的取舍

| 方案 | 当前新增价值 | 当前成本与风险 | 选择 |
| --- | --- | --- | --- |
| A：复用现有机制补缺口 | 可直接改善错误报告复查、历史输入证据和失败归因 | 局部改动仍需明确事件类型及诊断一致性，不能继续散落临时解析逻辑 | **当前推荐；首个切片完成后可以停止，不以进入 B 为验收** |
| B：统一横切模块与 OTel | 多入口重复埋点或需要标准 Trace 导出时，能降低重复维护 | 当前四项职责与已有 context/worker/store/ledger 部分重叠；新增线程传播、生命周期和投递失败语义需要验证 | **保留条件性演进，暂不实施全套** |
| C：独立观测平台 | 多服务、多团队及大规模运营查询的统一设施 | 新存储、运维、访问治理、事件版本与一致性负担 | **暂缓；未发现当前容量或组织需求证据** |

原文指出“统一业务身份、区分运行观测与审计、显式记录业务决策”，这些原则适用于 A，也应保留。它们不专属于方案 B。原文列举的低耦合与扩展性是潜在收益，尚无本项目维护成本或性能数据证明值得立即支付新增抽象成本。

## AOP 接入最需要纠正的三个假设

### 函数结束不等于物理调用结束

perform_io 启动独立线程，等待超时时抛出 CALL_RESULT_UNKNOWN，而线程可能仍活跃。外层装饰器结束只能代表这段等待结束；底层调用收尾、晚到结果、usage 结算由已有账本处理。未来接 OTel 时，应分别表达逻辑尝试、物理调用和等待超时，使用已有调用身份关联，保留 UNKNOWN。

OpenTelemetry 官方文档确认装饰器 Span 与被包裹函数的执行范围一致；线程 instrumentation 负责传播上下文，本身不会生成遥测数据。因此“加装饰器”不能自动解决本项目的线程收尾或业务状态问题。[Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)、[Threading instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/threading/threading.html)（2026-11-05 查阅）

### 观测故障不阻断业务，只适用于可选遥测

Span 导出可采取尽力方式，必需审计与正式状态仍须保持既有提交保证。不能把两者藏进一个统一 Sink 后共享“失败吞掉”的策略；也不需要为当前同库事务预先引入 Outbox。

### 通用拦截器不知道规则效力和父方采用理由

规则是否适用、子结果是否被父方采用、报告是否符合 Oracle，必须从业务确定的事实和独立评测中读取。拦截器最多补调用信息，不能根据方法名或返回成功推导这些决定。项目现有 child_accepted 事件也可携带 failed=true；统计必须读取具体状态与后续父方验收。

## B2 后建议的最小工作顺序

第一项选“按固定报告导出诊断证据”：复用既有 API/账本与采集器，串起冻结身份、规则效力、实际请求、工具观察、父方验收和正式报告；明确指出断链，不新增权威状态。历史完整输入若现有授权接口不足，再限定补一个受控导出接点，不能用测试内 Store 读取冒充运行时能力。

第二项在真实模型试验前补最小失败信息：失败阶段、字段/条件、原始 HTTP 状态、可获得的上游请求 ID、finish_reason、响应完整性与本地耗时。日志不默认收集认证头、隐藏推理或所有原始敏感结果。若仅需完成第一项诊断，不把这项变成强制前置大改造。

第三项随独立业务评测落地：固定 Oracle/报告/输入版本与 criterion 证据引用，保留旧判定；跨 Review trial 汇总已知、预留、未知消费。该项复用现有模板和 F01 的机制，不自动批准真实调用或继承旧费率。

以上是选型建议，不是已批准开发执行单。后续每个切片可独立交付，不要求先做 OTel、仪表盘或服务迁移。

## 建议验收：检验诊断能力，不检验日志数量

1. 给定固定 report_id，复查者能定位本次输入、规则版本、每次实际调用和结果引用；缺失时列出具体证据及受影响判断。
2. 区分“必需材料过预算而被阻断”“投影与实收不同”“双方一起漏正文”。规则完整送达但输出错误时，不误判成组装丢失。
3. 工具结果未投影、子结果失败或父方拒绝可区分；业务报告不能仅凭工具/函数成功升级为通过。
4. 模拟缺失历史事件或畸形记录时，各个证据完整性字段一致降级，原有 FAIL 不被改成未知或通过。
5. 如果增加可选 Trace 导出，关闭/故障不改变正式结果；必需审计落库失败继续遵守原有失败边界。此项只在实际接入导出器时执行。
6. 同一个真实 trial 内的不同 Review、派生 job、重试与 UNKNOWN 调用不漏记、不重复累计；无用量证据时不记零费用。此项在真实多 Review 试验前验收。

现有上下文、动态工作流、证据采集和 B2 回归可以作为验证基础；未来按实际改动选择相关测试，再遵守仓库规定完成必要门禁。本次文档更新不运行 pytest/Ruff 或业务试验。

## 何时改选 B 或 C

改选 B 的依据应是实际重复和使用需求：多个独立入口反复修同一埋点问题；已有事件映射无法维持一致性；或真实用户需要跨服务的标准 Trace 查询。届时先把现有身份与生命周期映射到 OTel，保留业务事务和现有账本，不同时改编排与审计存储。

改选 C 需要进一步证明多团队/多产品共享、查询容量或长期运营需求，并有维护资源。仅仅 Agent 数量增加或出现新的正式规则，不足以触发 C。

本推荐的关键前提是：现有持久身份与事件能支撑首个诊断切片。若导出时发现关键正文从未保存，A 必须扩大到该处采集边界；增加一个只读展示层不能补造证据。只有这种缺口在多个独立生产者中反复出现，才有充分理由提炼 B 的统一采集组件。

## 本次交付检查

本次仅修改 AGENTS.md 中适用范围的一段并新增此报告。九项原则和上下文交接规则保留；代码、依赖及 B2 产物不由本会话修改。最终检查为文本差异、九项标题完整性及本报告本地链接，不把文档检查当产品运行验证。
