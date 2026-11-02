# CR02-TASK-IMPACT-01：候选影响发现与显式采用

日期：2026-11-02（Asia/Shanghai）。版本：**v0.1，供审执行单；未获实现授权，未实现**。
产品 checkout：`C:/Users/50469/specflow-h04-f03-20261023`。
核对基线：`fbf47b697dc386b9b58f2aacf8416805defe052d`。

依据：`D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/SPEC_FLOW_PLAN_UPDATE_v0.2.3_2026-11-01.md`
§4、§5、§7，以及原 v0.2.2 规格及同目录修订说明。本文件把计划项具体化，
以下新增接口、表、协议和类名均为**提案**，不能当作当前已有功能或编码授权。
F01 人工清单先导仍优先，真实试验不等待本任务实现。

## 1. 目标、完成条件与范围

用户提供变更意图、项目、固定 commit、允许材料和已确认规则；系统通过有界只读取证，
生成“哪些对象值得检查、为什么、依据是什么、还有什么未知”的候选目录。
用户选择、补充、更正或排除后，宿主才冻结正式 targets/checks，进入现有审查。
候选相关性不等于已经确认偏离，更不等于已批准修改。

本任务实现后的完成条件：IMP-01—06 均有离线正反例；一个完整的“发现→人工采用→创建审查”
链路及一个“发现→显式修订”链路可复查；旧人工清单入口保持可用；共享物理 I/O、原子性与
失败隔离通过验证。离线替身不签发真实模型语义、召回率或维护收益结论。

本版候选阶段不委派、不写代码、不执行被查应用、不联网跟随来源链接，也不新增自动长期记忆、
摘要服务、通用 DAG、任务平台或恢复/回放。正式审查原有选项继续由其冻结 profile 控制。
真实模型、profile/试次/费用及试验窗口另行批准。

## 2. 源码接点与架构选择

| 已核实接点 | 当前约束 | 本任务提案 |
| --- | --- | --- |
| schemas.py / CreateReview | targets 至少 1 项，版本与 target 一致；最多 100 targets / 200 checks | 不放宽该契约；发现采用独立输入 |
| inputs.py / freeze_input | 从完整请求生成 target/check/adoption 身份 | 候选身份不直接复用为正式身份，采用后仍由宿主生成 |
| sources.py / GitSnapshotReader.prepare | 从完整 commit 的显式 groups 密封正文；受项目路径及容量控制 | 复用固定快照及权限验证，不读工作区替代 commit |
| snapshot_tools.py / SnapshotTools | 工具只访问密封 sources 与片段 grants | 复用五个工具及其参数/结果协议 |
| dynamic_context.py / RunState | 依赖正式 target_manifest、adoption_records | 只复用可分离的正文投影规则，不伪造正式输入 |
| service.py / create、checkpoints.py / revise | 短事务内保存正式 input/job；修订做 CAS 和归属核对 | 提取可接收已密封快照及采用记录的内部事务接点，保持旧入口行为 |
| store.py / schema v1—v5 | jobs/calls/events 依赖 review；runtime.slot_call_id 指向 review_calls | 新增发现归属记录，显式接共享调度与 I/O 槽，不塞占位 review |
| worker.py / ReviewWorker、execution.py | 一个持久 worker；未确认本地 I/O 收尾时不得派发下一调用 | 继续一个 worker、一个物理 I/O 槽，扩展两种任务归属 |

推荐选择：**独立发现资源，复用同一 worker 和密封工具；人工采用与正式创建/修订原子绑定**。
不以空 targets/占位 targets 冒充普通审查，也不另起一个可绕过现有槽位的 Provider worker。
这是本执行单待批准的架构选择；实现影响包括共享槽与事务接点，不是只加一段 prompt。

## 3. 输入与冻结边界

拟议 `CreateImpactDiscovery` 请求严格拒绝未知字段、显式 null 和非法类型：

| 字段 | 含义与约束 |
| --- | --- |
| project_id | 既有项目身份；仓库路径由服务查询，不接收任意文件系统路径 |
| change_request | 1..16000 字符的用户变更意图；不把来源文件内容当成授权 |
| source | 复用 GitSource：完整 commit_sha、明确 role/path groups；不要求预先给 targets/checks |
| authority_bindings | 1..100 个已明确采用的来源片段与声明范围；复用 AuthorityBinding，角色须为 contract/decision_reference |
| ruleset_usage | 复用 none 或 applicable_confirmed + 明确版本；第一案例为 none |
| execution_profile_id | 必须显式选择已登记的发现 profile，不默认套用 F01 profile |
| actor_label | 可选说明元数据，不代表身份认证或批准者证明 |

发现入队前冻结：项目归属、快照/允许片段、意图、规则原文和版本、profile 全文及 hash、
调用/工具/执行时间上限。不得在读取过程中自动增加 groups 或追随最新项目规则。
规则集合在发现阶段是已确认规则上下文，不假造逐 target 的 adoption_id；
采用为正式审查时仍执行原有规则适用性和版本核对。

未确认的版本/接口可保留未知；不因 CreateReview 要求 api_version 就替用户补造一个版本。
输入没有足够规则时应在受理阶段明确拒绝或要求补齐，而不是把未采用资料变成权威。

## 4. 模型动作与候选结果

拟议发现协议 `contract-impact-action.v1` 只含 `tool_call` 与 `submit_candidates`。
前者复用登记工具参数；后者提交候选目录和未决事项，不提交正式审查报告。
用独立发现 profile 构造实际请求；不能把新协议伪装成现有 ExecutionProfile 的 action_protocol。

动作理由使用本阶段已投影 SourceRef/observation MaterialRef。目录可选源但不是正文；
工具已执行但尚未进入后续请求仍不可引用。非法动作零工具派发，保留实际反馈及有界纠错。
不得使用其他发现、review、规则采用或外部核验身份补齐引用。

### 候选项字段

| 字段 | 归属与校验 |
| --- | --- |
| local_key | 模型输出内的唯一短标签，只用于本次列表关联，不是资源身份 |
| source_path | 必须能定位本允许快照内的对象；快照外提及只记录为缺口 |
| artifact_role | 必须属于该来源登记角色，不因模型自称改变角色 |
| api_version / endpoint | 可省略；给出时必须有已读材料或用户变更意图支持，未知不填 null |
| relation | observed 或 hypothesized；后者必须列明尚缺的关联依据 |
| rationale | 变更意图与观察到的对象关系；不能只因名称相似就断言受影响 |
| suggested_checks | 1..20 个 key/behavior 建议，不生成 check_id；合并采用时仍受现有总量限制 |
| source_refs | 至少 1 个实际投影正文片段；目录/路径/hash 不能单独满足 |
| observation_refs | 可选已投影观察 ID，用于追溯工具过程，不能变成外部 evidence_id |
| unknowns | 缺版本、归属、路径/调用关系或动态行为等明确缺口 |

宿主接受合法目录后生成 discovery_id 归属下的 candidate_id、不可变 catalog_hash，
保存 local_key 对应关系。目录最多 100 个候选，每候选建议检查最多 20 个；
采用结果另受 100 targets / 200 checks 上限。相同对象/版本/接口的重复项须合并或显式拒绝，
不能靠重复候选制造覆盖率。

规则和已符合变更的实现也可作为有依据的相关对象列入，并建议保留/核对；候选不要求每项都修改。
未发现候选时允许空目录加搜索范围、已读材料和缺口说明，不得外推“全仓库没有影响”。
中断/失败运行中尚未接受的半成候选不可通过采用入口升级成正式清单。

### 上下文与额度

先投影必要规则及意图，再按冻结预算选择观察；正文、范围、角色和省略记录均保留。
必需规则放不下明确失败，可选观察省略显式列出，不新增动态摘要/Token 压缩系统。
工具注册沿既有五项；本版不调用 delegate_task。

离线 test profile 的提案上界为 12 次模型调用、20 次工具动作、300 秒执行时间、
每次最多 8000 输出 Token；这些是工程上限提案，不构成真实模型费用授权。
一次连续协议失败只允许一次纠错，第二次连续非法终止；相同工具/参数且观察正文无新增信息
连续出现三次终止。第一次合法空查询不算失败。本版发现阶段依赖失败不自动物理重试，
候选完成不额外添加模型复核；后续正式审查仍走原固定复核流程。
发现与正式审查分别记资源账；若获准一个完整业务链，还须共同受该链总费用/物理调用授权约束，
不能因采用后新建 review 就重置总试验额度。真实输入费用上界另按获准通道核实。

## 5. 显式采用合同

拟议 `ImpactAdoption` 使用不可变 discovery_id + catalog_hash 和一个新幂等键。
对每个 candidate_id 明确选择 take、edit 或 exclude；exclude 必须说明理由，edit 保留前后值。
用户新增目标单独记为 manual_addition，不能伪装成模型成功发现。
提交全量目标候选到最终清单的映射；缺项、重复 disposition、跨 discovery 身份均拒绝。

采用请求还包含两种目的之一：

- `create`：完整、可由现有 CreateReview 校验的正式请求。
- `revise`：目标 review_id 和可由现有 RevisionRequest 校验的明确 patch，含
  expected_version、base_input_revision_id、change_reason。

两种目的都核对项目及发现快照；正式 source/权威片段只能使用本次明确允许的材料。
发现里未知的版本或接口必须由用户显式补充并保留说明，未补齐不能自动生成合法 target。
用户要扩大允许集合或使用另一个 commit 时，另做明确来源变更与取证，不能沿用旧证据宣称已覆盖。

### 原子保存与身份映射

1. 事务外准备/验证必要的快照字节；不在 SQLite 写事务内调用模型或工具。
2. 事务内重查项目路径/权限、候选归属/目录 hash、当前版本、容量和幂等状态。
3. 复用正式创建/修订校验；采用记录、正式冻结 input、唯一 job 及幂等响应同事务提交。
   不使用“先 HTTP 创建 review，再补记采用”的两次提交做法。
4. 保存 candidate_id/local_key → 正式 target_id/check_id 的映射、人工新增/修改/排除理由、
   discovery/catalog/input 关系。任一步失败全部回滚，不留下无采用记录的半个新 input/job。
5. 发现 SourceRef 只在其快照身份域有效；若正式冻结产生新 source_id，按相同项目、commit、
   路径和密封正文/selector 重新校验并映射，不能直接搬用旧 source_id。

采用成功同事务追加 adoption_recorded 事件，详情包含完整处置及身份映射；通过该发现的
事件分页与详情接口可取回，不依赖读取本地数据库，也不在 GET 中无界展开全部历史采用。

同 key 同正文返回原响应，不再次派发；同 key 不同正文冲突。新的显式采用命令可以产生另一个
合法 review/修订，须单独记录，不能把“幂等”误解成禁止用户主动复用一个候选目录。
若全部排除且没有人工新增，允许只保存采用决定，不创建空目标 review 或空 revision。

正式审查开始后，模型不能修改清单。后续新增/删除/更正只走已有显式 revision；
未变化目标/check 身份、人工答案适用性和历史报告继续遵守 TASK-05 语义。
候选及其人工采用记录是范围来源，不是业务偏离结论、项目规则或外部核验证据。

## 6. 入口与持久化提案

### API

| 拟议接口 | 行为 |
| --- | --- |
| POST /api/v1/contract-impact-discoveries | 202；只校验、密封、持久受理和入队，不在 HTTP 中调用模型 |
| GET /api/v1/contract-impact-discoveries/{id} | 当前状态、冻结身份、完成目录/缺口、运行诊断；不暴露本地仓库绝对路径 |
| GET /api/v1/contract-impact-discoveries/{id}/events | 有界分页元数据；按所属发现校验游标和事件 |
| GET /api/v1/contract-impact-discoveries/{id}/events/{event_id} | 请求投影、动作、工具观察及接受/拒绝详情，保留实际正文 |
| POST /api/v1/contract-impact-discoveries/{id}/adoptions | 只保存决定时 201；生成正式 input/job 时 202；原子返回采用与正式身份 |

所有新路由沿现有认证、严格查询/请求、幂等错误和容量边界；BodyLimitMiddleware 须覆盖新前缀。
不添加模型任意 URL、任意目录导入、自动发 PR 或跨项目复制规则入口。

### 记录归属

在 store.py 追加下一版本迁移（本基线为 v6），保留 v1—v5 checksum：

- `contract_impact_discoveries`：project/snapshot、冻结输入/profile/规则版本、状态/版本、
  预算累计与未知用量、不可变完成目录及 hash、失败/时间信息；一条发现只有一次执行，不提供 retry/resume。
- `contract_impact_calls`：发现归属、步骤/物理调用身份、实际投影与传输身份、原始结果/usage、
  本地 I/O 收尾和远端结果状态；不能引用伪造 review job。
- `contract_impact_events`：单发现递增序号及调用/观察关联、完整正文或可取回正文绑定。
- `contract_impact_adoptions`：候选目录、全部处置、正式 input 及身份映射、幂等请求/响应；
  与正式创建/修订同事务，记录容量纳入既有总账。

密封正文仍复用 contract_review_snapshots/source_blobs 的项目归属和容量账；内部快照复用
要核对已有记录，不重复 INSERT 同一身份或重复扣容量。不能向已有冻结 input 事后追加采用记录；
关联内容随新 input 一起冻结，或由不可变关联记录指向该 input。

### 单 worker 与物理槽

发现排队记录由现有单 worker 的有界调度分支领取，不增加第二个 Provider worker。
待领取总量沿既有上限 20 统一核对；两类 queued 记录按创建时间及稳定身份排序。
既有实例锁、owner/attempt、deadline 和维护门禁继续生效。

runtime 追加发现调用租约引用；既有 review-call FK 不改指向。两类派发都必须在同一事务确认
两种租约均为空后占用，释放须匹配调用及执行实例。现有分析与新发现的 claim、释放、维护、
dispatch_gate 必须一起适配；不能只让新流程检查旧槽、却让旧流程绕过发现槽。
数据库写入失败零外部派发；未确认本地退出时两类流程都不新派发。业务失败不等于物理 I/O 已结束。
重启只分类 interrupted/unknown 并处理原有收尾证据，不恢复或重放发现调用。

## 7. 首个变更案例与人工采用预期

本任务使用独立开发夹具标签 **IMP-FIELD-01**；它不是原 24 case 的新增试次，
本轮未创建 fixture、trial 或模型输出。最小案例复用 F01 四份固定正文，增加两份任务局部
静态夹具以验证测试角色与相似名称负控制，原 F01 六例资产保持不变。

变更意图：“本次采用 API v2 的 POST /exports 创建响应 job_id 规则，梳理允许材料中需要核对的对象。”
允许材料仅为下列六项；不含 Oracle、人工预期或历史模型答案。

| 材料 | 预期候选/证据用途 | 首次人工采用决定 |
| --- | --- | --- |
| contracts/v2.json（原 contract-v2.json） | 当前规则，说明 201/job_id；不建议反向改契约 | exclude：规则已明确采用，本次不改 |
| src/api.py（原 api-correct.py） | 创建实现已返回 job_id；应保留 | exclude：实现已符合本次字段要求 |
| docs/api.md（原 docs-id.md） | v2 文档仍用 id；建议检查响应字段 | take：response_field |
| examples/client.py（原 example-id.py） | v2 示例读取 id；建议检查字段消费 | take：response_field |
| tests/test_create_export.py（拟新增） | 显式断言响应字段集合恰为 {id}，与要求 job_id 冲突 | exclude：记录后续测试工作，本次采用范围只含文档和示例 |
| src/metrics.py（拟新增） | 仅有同名参数，没有 /exports 或响应消费关系 | 不应凭词命中认定受影响；若模型列入，人工排除并计假阳性 |

拟新增测试角色夹具仅作静态读取，正文约定为：

```python
def test_create_export(client):
    response = client.post("/exports")
    assert response.status_code == 201
    assert set(response.json()) == {"id"}
```

拟新增负控制约定为一个 `record_metric(job_id)` 函数，仅把参数放入 metric 标签；
没有导出 API 调用或响应处理。实现获准后固定确切字节，再写独立 Oracle，不根据模型输出改预期。
测试集合“恰为 {id}”刻意区别于“兼容 id”：当前契约没有明文禁止额外兼容字段。

采用出口：产生一个 v2 审查，正式目标恰为 docs/api.md 和 examples/client.py，各一个
response_field；规则/实现/测试均不成为该 input 的正式修改目标，排除理由完整保存。
这张采用清单是后续人工操作材料，不进入发现模型的初始提示。

补充 revise 链路：基于一个只含文档目标的既有可修订输入，采用示例目标并显式给出 patch；
原文档/check 身份保持，新增示例身份由宿主生成，旧 input/report 不变。不得用修改当前运行清单代替 revision。

## 8. 离线验收矩阵

| 原计划出口 | 必需证明 | 关键反例 |
| --- | --- | --- |
| IMP-01 | 上例五种角色均能表达有证据的相关/保留/核对候选；正式采用仅两目标 | 相似名称无关系；兼容字段不能推导禁止；测试不加入本次正式范围 |
| IMP-02 | 工具只读允许快照/片段；规则来源不带来额外读取权 | 越界、跨项目、未授权路径、来源自称批准、提示注入与联网链接均不扩权 |
| IMP-03 | 未知版本/接口/调用关系保留缺口；可由用户明确补充 | 不猜版本、不伪造资源身份，不因空搜索声称全仓库无影响 |
| IMP-04 | take/edit/exclude/manual_addition 可追溯；create/revise 原子绑定 | 漏处置/跨目录ID/陈旧CAS/同key异正文/范围扩大拒绝，零半成 input/job |
| IMP-05 | 动作→工具观察→后续实际请求→接受目录可关联 | 未投影正文、尚未投影观察、越界selector、其他发现ID、外部证据混用均拒绝 |
| IMP-06 | 失败/中断发现不改已有 review/input/report；手工 CreateReview 原流程可用 | 发现异常、存储/容量失败、未知usage、未收尾I/O；两类流程绝不绕过共享槽 |

工程反例采用受控 adapter/MockTransport，补充迁移升级/重入/失败回滚、旧 checksum、
两类任务竞争槽、迟到响应、重启分类、采用与输入事务故障注入、分页归属及正文完整性。
同任务的受控输出只证明协议和门禁，不称真实发现成功。

候选召回/误报按预先写出的候选真值与负控制统计；人工新增不计模型召回。
正式检查覆盖只对采用后 manifest 统计，不能用正式两目标闭合证明发现阶段全覆盖。
不设未经校准的“召回率≥某值”门槛，也不以一个开发夹具签发泛化结论。

## 9. 拟改范围、实施顺序与交付门禁

后续获准实现时，改动限于 contract_review 内的发现 schema/service/runner/ledger/API，
现有 service/checkpoints 的事务接点、store 追加迁移、worker/execution 的共享槽接线、
必要 main 注册和 tests/contract_review。旧 Run API/旧 Provider/旧评测与学习资产不改；不新增依赖。
可新增 impact_schemas.py、impact_service.py、impact_runner.py、impact_ledger.py、impact_api.py，
最终文件名在执行时按实际职责收敛，不为凑模块拆分。

实施依次为：输入/密封与独立记录 → 受控只读动作/实际投影及共享 I/O → 显式采用原子事务
与 create/revise 两条链 → 故障/兼容验证。中间切片须标 PARTIAL；不能只完成候选 JSON 就关闭本任务。
若为复用 worker 需要超出本节的通用调度重构，先列具体冲突与最小替代，不借本任务改造旧八路由。

新代码使用 gpt-6-astra / xhigh 独立审查；确认缺陷修复后只复核原发现。
通过任务聚焦测试、全量 pytest、Ruff check/format、diff 检查及既有离线构建门禁后，
记录固定提交、验证日志、未取得的真实证据及剩余范围。真实试验仍需单独批准。

## 10. 本次规格准备记录

本轮只创建本执行单，未新增任何接口/表/fixture/代码，未跑模型或重开旧门禁。
核对了 CreateReview、freeze_input、GitSnapshotReader、SnapshotTools、RunState、
ReviewService.create、CheckpointService.revise、ReviewStore v1—v5、ReviewWorker 与 execution 槽引用。
文档检查覆盖计划 IMP-01—06、首次采用两目标/两检查、相对链接/源码接点及 git diff --check。
用户维护的 docs/reports/CR02-CURRENT.md 修改保留，本轮只本地提交。

源码证据入口：

- [输入 Schema](../../src/specflow/contract_review/schemas.py)、[正式输入冻结](../../src/specflow/contract_review/inputs.py)。
- [密封快照](../../src/specflow/contract_review/sources.py)、[只读工具](../../src/specflow/contract_review/snapshot_tools.py)、[工具协议](../../src/specflow/contract_review/tool_protocol.py)。
- [当前投影状态](../../src/specflow/contract_review/dynamic_context.py)、[审查创建事务](../../src/specflow/contract_review/service.py)、[显式修订](../../src/specflow/contract_review/checkpoints.py)。
- [表与迁移](../../src/specflow/contract_review/store.py)、[单 worker](../../src/specflow/contract_review/worker.py)、[物理调用槽](../../src/specflow/contract_review/execution.py)。
- [原 F01 输入](../../benchmarks/contract_review/cases.json)、[已有人工先导准备包](../reports/CR02-SIX-CASE-PILOT-READINESS-2026-11-02.md)。

本文件待审决策为第 2 节的独立发现资源/共享 worker 方案及对应第 6 节存储与槽接线。
批准前不进入实现；这不阻塞用户另行批准原 F01 人工先导，也不取消后续恢复、写入、上下文与记忆专项。
