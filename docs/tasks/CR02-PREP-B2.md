# CR02 PREP-B2：正式项目记忆与冲突专项执行单 v0.3

日期：2026-11-04（Asia/Shanghai）。状态：**保留六项协议并完成三处局部判据补强；候选v0.3待独立复核、未冻结，B2代码与真实模型均未启动。**

## 1. 目标与当前事实

目标是验证正式项目规则跨review的采用、冲突、部分替代／撤回与局部答案隔离。
B1已完成F02/H01/H02受控离线链路：全库1715 passed/3 skipped/3 warnings，另有10次受控adapter输入与投影相等证据。
这是既有结果，本轮不重跑，也不把它计为记忆业务验证。

产品HEAD为`99a8baa0c2de38751a6ccce48d8b97e85ad1ec90`。B1五文件仍是工作树新增，HEAD本身不包含B1。
保留AGENTS.md、CR02-CURRENT.md与B1全部本地修改，不提交／推送。
原合同E§6的R02/R03/R04/R05/H03及C§4.4是业务依据，原case/trial/sample身份保持不变。
原manifest的D3-B／排除记忆项是历史准备快照；本候选按后续已选D3-A设计，不回写旧记录。

## 2. 本轮实际新增文件与后续允许文件

本轮更新本执行单并新建`benchmarks/contract_review/candidates/b2-v0.3/`，v0.1/v0.2候选资料保持原内容。
新版本包括原八份候选资料及两个静态模板：review-freeze.template.json、result-record.template.json。
保留六项协议，本次只拆分H03判定、补充AC10完整性和历史规则负控制；五例业务目标、材料正文及后续三个实现文件范围不变。
v0.3判据文本有局部增补，不声称与v0.1字面完全一致；历史版本差异见本轮对照记录。
不修改src、现有脚本／测试、B1、原24例manifest或六例判据；不调用API、制作运行数据库或执行模型。
候选材料的静态检查是准备证据，不是产品测试。

后续若明确启动B2离线实现，首批只新增以下三个文件：

| 文件 | 职责 | 直接验收 |
| --- | --- | --- |
| `scripts/contract_review/run_memory_case_prep.py` | 固定五例与独立演示的材料准备／API编排；独立b2-offline-memory-v2测试profile；默认CLI只准备 | 不读认证、不启动真实Provider；同case内复用project/DB，按真实响应解析引用；缺参数／错身份明确停止 |
| `tests/contract_review/test_memory_case_prep.py` | 测试内受控adapter与临时API环境，覆盖五例、复合链路及错误路径 | 实际发布／取证／答题／派生／历史流程和调用计数；不把替身语义当真实模型效果 |
| `docs/reports/CR02-PREP-B2-offline-readiness.md` | 一份实际结果、证据索引、缺口、旧证据和新增验证的报告 | case逐项与demo分开；原始命令／日志／payload可查；真实语义保持NOT_RUN |

候选目录在未来实现阶段默认只读。材料／oracle如需修订，列出差异和原因，经独立复核后再冻结新版本，
不得看到被测失败后放宽判据。本执行单目前不授权上述三个文件的代码实施。
不添加依赖、公共API、数据迁移、语义预检、语义去重、自动经验记忆、条件写入或旧DAG改造。

## 3. 复用与依赖边界

- 复用现有正式发布／规则版本列表、Review／状态／报告／问题、resolution-batches及事件详情API。
- 只复用B1的`ReviewEvidence`采集能力，维持其现有证据格式；B2可附加phase/case元数据。
- **不复用B1的run_case或submit_answers运行入口**：它们只接受固定公开三例及关闭project_memory的B1 profile。
  不为跑记忆而放宽B1 guard。B2在新脚本内实现小型、明确的记忆流程，使用独立profile。
- B2 profile：engine v2、execution_mode=test、project_memory=true；write/delegate/replay=false。
  后续受控执行仅接受进程内TestClient、该固定profile及test adapter，禁止自动选择真实模型。
- B1采集器能取规则版本视图和逐输入报告／请求，不能提供完整历史InputRevision GET。
  每轮答题前保存状态及input ID/hash/profile，202后保存后继；完整持久输入不变复用现有Store级回归。

实现接点：decisions.py的publish/list/adopt；checkpoints.py的answer；service.py的get/enqueue_revision；
execution.py的commit_report；scripts/contract_review/review_evidence.py的ruleset/capture。
已有相关回归位于test_project_memory.py、test_decision_scope.py、test_checkpoints.py和B1两个测试文件。

## 4. 候选案例、材料与独立判据

目录：[候选案例导览](../../benchmarks/contract_review/candidates/b2-v0.3/README.md)，
[候选判据](../../benchmarks/contract_review/candidates/b2-v0.3/oracles.json)。五例分别使用原manifest身份。
cases.json中的alias只用于步骤关联，不能成为模型资源ID或假冒HTTP请求字段。
后续runner从实际发布响应得到project_decision_id，从实际状态／报告／请求投影映射review/input/job/report/target/adoption/question身份。

| case | 规则集与操作 | 决定性预期 |
| --- | --- | --- |
| R02 | confirm允许queued→1；confirm拒绝queued→2；Review A采用2 | 相同API版本／接口／目标／条件，规则无优先关系；报告conflict与blocking rule_conflict，等待裁决 |
| R03 | confirm允许queued→1；A/B独立采用1 | 同一正式决定及原文在新review可用，adoption各绑本次input；无冲突，不重复批准 |
| R04 | joint旧规则→1，保存A旧报告；supersede仅取消→2，创建B | 创建201/job_id仍正确；取消queued实现放行但新规则要求拒绝，应指出取消偏离；旧报告／视图不改 |
| R05 | joint旧规则→1；withdraw仅取消→2 | 创建仍有效；取消无其他规范，明确不足；禁止“撤回=禁止取消”或用实现/旧片段强判 |
| H03 | 正式规则仅覆盖实现创建，规则集1；A0提归属问题→本次答v1→A1；独立B采用1 | A1排除本例v2漂移；B没有A的答案和等价正式归属决定，重新待澄清；规则集不因回答增加 |

R04/R05的新contract-create-only.json只包含创建201/job_id，不含取消规范。
两例旧joint规则正文不会被剪改，取消切片的有效性由正式效力关系决定。
H03复用原H01四来源，但正式规则scope只覆盖src/api.py；不能用其批准examples/client.py版本归属。

oracles.json逐例写明必要结论、禁止结论、允许未知、需要的材料与规则原文。
同义准确解释可接受，不能靠目录、ID、hash、Reviewer accept或字符串命中判语义PASS。
公开候选不是Holdout；判据先独立复核，真实试验后不按结果挑删样本。

## 5. 独立A/B/C演示

demo-abc.json是独立编排草稿，尚无正式case/trial/sample身份，不加入五例统计：

1. 同一隔离project发布allow和deny，规则集达到2。
2. A0采用2，正式报告指出冲突；读取合法问题并提交this_review答案。
3. A1由最后阻塞答案的202自动派生，仍采用2；本次选择允许queued，原A0报告保留。
4. B同材料／同规则集2，但不带A答案，应仍面对冲突。
5. 独立发布withdraw移除deny，规则集达到3；本次答案不触发这个步骤。
6. C采用3及仍有效的allow，当前fixture取消实现与该规则一致；读回规则集2/3和各历史报告。

该演示不能代替R04部分supersede、R05撤回后无其他依据或H03独立版本归属场景。
B2-AC-07属于完整B2离线工程门禁：demo失败／未完成时整体B2不能签完成，但不自动把五例语义结果全部改为失败。
“冲突已解决”与“实现已符合最终规则”分开检查。API v2、ruleset_version和review.version是三种不同版本。

## 6. 输入与操作规则

材料读取允许集只来自每例materials的repo_fixture；后续复制到新隔离Git仓库，生成并冻结实际commit。
不执行api-v2-static.py，不改被查应用，不借材料链接扩展读取范围。
模型可见：已授权密封材料、适用正式规则原文、实际观察与合法提交的本次答案。
模型不可见：oracle、预期标签、未触发答案、其他review局部答案及演示脚本。

每个新case创建独立project/DB试验上下文，case内多review共用同一上下文；原已用身份只作来源，真实试次另行冻结。
expected_ruleset_version在明确版本序列上校验；HTTP更新的expected_version总从最新状态取，不硬编码。
正式发布使用每个逻辑操作独立幂等键；同键同载荷重放应同结果，不能当作不同请求的语义去重。

答案必须绑定当前正式report/input和真实question_id，且符合allowed_answer_types。
非唯一问题、不接受候选答案类型、缺正文或跨input引用时停止自动答题，不伪造问题或放宽报告。
部分200仍等待；最后202保存并跟踪自动派生job，禁止额外revisions重复入队。
显式revisions只用于有真实输入／规则采用变化的后续任务，本批默认流程不需要该额外操作。

## 7. 离线验收及拟新增测试

当前以下均是待实施验收，不是本轮通过结果：

| 验收 | 拟测试节点 | 通过证据 |
| --- | --- | --- |
| B2-AC-01 准备零副作用 | test_memory_preparation_is_side_effect_free_and_has_no_live_entry | 准备不读认证、不启动Provider、不发业务HTTP；候选身份／材料不匹配在受理前拒绝 |
| B2-AC-02 真冲突承载 | test_r02_reports_mutually_exclusive_rules_before_answer | 按§9.3核对同一冻结input/规则版本/目标/条件内的有效规则互斥；正确关联本次adoption和合法问题，不把跨历史版本差异当冲突 |
| B2-AC-03 跨review复用 | test_r03_reuses_confirmed_rule_without_reapproval | 同project_decision/version/body，各input独立采用与请求；无多余批准操作 |
| B2-AC-04 部分替代 | test_r04_replaces_only_cancel_and_preserves_old_view | 创建保留、取消新效力准确，正文／历史不改；不得仅因旧取消文本保留而报告当前冲突，见§10.3 |
| B2-AC-05 撤回缺依据 | test_r05_withdrawal_leaves_cancel_unknown_and_create_effective | 检查全部规范入口，withdraw不生成反向规则；取消确无有效依据、创建保留；区分正确业务不足与采集缺证 |
| B2-AC-06 本次答案隔离 | test_h03_local_answer_is_absent_from_review_b | §9.2三组工程证据齐全，隔离独立判定；B输入干净却独立猜错版本，不自动判污染；语义歧义另按H03-3.ambiguity判定 |
| B2-AC-07 复合演示 | test_abc_demo_keeps_local_answer_and_formal_update_separate | A/B规则集2、C规则集3；202/发布顺序正确；C不得把已撤回deny当当前冲突；本项仍是整体工程门禁，demo不增语义case数 |
| B2-AC-08 幂等/CAS | test_publication_cas_and_same_key_replay_preserve_version | 同键同载荷只一条正式记录，旧版本/错归属明确拒绝，失败不污染下一操作 |
| B2-AC-09 问题与引用归属 | test_answers_use_report_ids_and_auto_derived_job | 当前report/input/target/规则引用和允许答案类型正确，错误路径零答案／零多余revision |
| B2-AC-10 一致/完整/无泄漏 | test_each_input_adoption_matches_actual_delivered_payload | 三组断言分别记录：同次payload精确相等、相关判断/复核收到必需原文、oracle及未触发/跨review答案不泄漏；不能以同漏后的相等替代完整性，见§10.2 |
| B2-AC-11 缺证/未知 | test_history_gap_and_unknown_prevent_complete_verdict | 按§9.4分离执行、证据、工作流、语义与业务判断；按§9.6记录阻塞/重测，不删计划槽位或抹掉硬失败 |

受控adapter只验证程序工作流，不得用其按预设输出签发真实语义正确。
真正语义验收须独立复核oracle并取得真实模型授权后，对原始输出逐criterion判断。
即使以后模型静态审查正确，被查业务应用未执行时execution_verification仍为NOT_RUN。

后续实际新增脚本／测试时，先运行新模块及相关B1/记忆/检查点模块，再完成仓库全量门禁：

```powershell
uv run --offline --no-sync pytest -q tests/contract_review/test_memory_case_prep.py tests/contract_review/test_public_case_prep.py tests/contract_review/test_review_evidence.py tests/contract_review/test_project_memory.py tests/contract_review/test_decision_scope.py tests/contract_review/test_checkpoints.py -p no:cacheprovider
uv run --offline --no-sync pytest -v
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
```

测试按变量名移除真实Provider／服务认证配置，不读／打印值；注入假认证和test adapter，阻断真实HTTP。
本轮仅文档／候选资料准备，不运行以上未来命令。

## 8. 开始、完成与停止条件

本轮资料交付：五例身份与原定义对应、材料文件齐全、JSON/源码语法和引用闭合、判据明确，保持待独立复核；
已有七处工作树文件不变，src／旧案例无差异。本轮检查结果写在本节末尾。

后续B2实施开始：用户明确启动这三个文件切片；基线与B1状态核对；候选schema/材料契约明确。
候选oracle未人工冻结不阻止工程替身测试，但不得进行真实语义验收。
后续离线完成：B2-AC-01~11有实际证据，必要门禁通过，零真实模型HTTP，历史／失败保留，报告逐case与demo分开。
真实模型开始：oracle独立复核／冻结、模型/profile、case/trial、调用/Token/费用/窗口、跨review累计费用和输出目录全部明确获准。
case可包含多个review，现有宿主账本以review累计，未来真实试验的case/整批总额度必须另行汇总，不能靠新review重置授权。

发现候选自相矛盾、额外有效取消依据、错误归属、不可兼容profile或既有产品缺陷时保留反例并停止对应操作，
不修改src、不放宽B1 guard、不自行新增API或自动发布真实规则。
E03/AC-10、完整TASK-09、条件写入、自动经验记忆和真实价值对照继续保留原状态。

### 本轮准备检查

已完成候选资料静态检查：

- v0.1已完成六份JSON及引用检查；v0.2新增两个静态模板，补强后的八份JSON与全部引用重新检查，原case/trial/sample保持不变。
- 12条材料关联指向6份实际源文件，路径均在仓库内；Python源材料只做AST解析，未执行应用。
  新api-v2-static.py与原api-correct.py字节相同。
- Target、Scope、AuthorityBinding、ConfirmDecision可检查部分通过当前本地模型校验；
  effect中的真实资源ID尚未解析，未据此声称完整HTTP请求或API归属已通过。
- 通过现有纯函数核对：R02双规则命中同目标；R04/R05只移除取消切片且创建保留；
  H03正式创建规则不命中示例归属目标；R05材料允许集中没有原完整取消规范。
- 演示不带正式case/trial/sample，不入五例分母；人工脚本和oracle均保持待独立复核，真实语义NOT_RUN。
- B1五文件、AGENTS.md、CR02-CURRENT.md与v0.1候选目录不变；本任务单更新、v0.2候选目录新建。后续三个实现文件尚未创建，src和原manifest/六例保持原状。

这些检查证明候选资料的结构与设计关系一致，不证明Agent语义判断或产品运行正确。
本轮未运行pytest、模型或业务API，未创建案例Git快照／运行数据库，未提交或推送。

## 9. 六项审查补强（评审与验收约定，不新增运行架构）

### 9.1 oracle复核、内容绑定与变更

- 复核人为用户本人或用户指定的独立复核者。未有明确确认时保持PENDING_INDEPENDENT_REVIEW，
  不由oracle生成者自填“独立复核完成”。签收使用review-freeze.template.json，填写人、时间、范围及明确批准依据。
- 从模板复制到仓库外试验输出中的review-freeze.json再签收，不原地填写模板或回写已固定候选包。
  候选manifest中的状态只是打包时快照；后续批准以引用该snapshot_id的外部签收记录为准。
  执行绑定另存execution-binding.json并引用freeze_id，避免签收记录或绑定内容改变自身所批准的文件指纹。
- 本次打包生成候选文件清单和内容指纹／candidate_snapshot_id，均**不等于人工批准或已冻结**。
  产品commit与未提交B1/B2工作树内容分别记录，不能称99a8baa0已包含B1/B2。
- 两步绑定：先确认case/oracle/材料内容版本；实际运行前再绑定真实材料Git快照、产品/工作树版本、
  profile及获准trial配置。当前尚未生成这些执行快照；缺必需绑定不做真实语义试验。
- 复核后需要纠错：保留旧oracle/冻结记录/原始输出，记录diff、原因、受影响criterion及复核依据，
  新版本使用新freeze_id。禁止覆盖旧版本追认PASS。
- 若仅判据纠错，可对固定旧输出建立新eval_run重评，保留旧结论；不自动重跑模型或增加独立样本。
  内容指纹用于发现变更，不能单独证明复核真实发生，也不承诺防御有写权限者重写；不建设签名服务。

### 9.2 隔离与实际调用证据标准

H03工程隔离必须同时具备：

| 证据 | 证明什么 | 缺失处理 |
| --- | --- | --- |
| A正控制：同次测试中A的resolution真实持久保存，A1冻结输入和实际调用含完整答案 | 不是A答案本来就没保存/没送达 | 不能签AC06通过 |
| B存储控制：测试内部Store读取同次B冻结输入，确认无A的resolution/局部答案 | 区分系统隔离与采集器没读到 | 记录证据缺口；无需新增公开InputRevision GET或让runner直连产品DB |
| B调用控制：所有相关分析/固定复核及纠错/重试的实收payload完整采集，与实际派发调用一一对应 | 不是只查看片段就声称答案不存在 | 无法判定项UNDETERMINED；已有硬失败仍保留FAIL |

runner保留各轮状态、input ID/hash/profile、请求及报告；测试可使用已有Store读取完整冻结输入。
历史GET能力与持久存储存在性分开。A答案应该在checkpoint/派生revision内持久保存，归属仍限A；
新B不得自动注入或采用。此处不承诺授权操作者不能查询A历史，也不是多用户ACL验收。

AC10只比较**同一次实际派发调用**：

```python
saved_projection["payload"] == captured_adapter_payload
```

配对使用review/input/job及账本物理调用标识，或经计数核对的角色/物理调用顺序。
左侧为adapter.prepare后的完整请求体；右侧为adapter.complete实际实收体。
JSON对象成员顺序可规范化，字段集合/类型/值/数组顺序及原文必须一致；**不设置payload忽略字段名单**。
投影外层projection_id/created_at等本来不属于比较对象；动态值若在payload内，同次也必须相等。
未派发意图、拒绝、超时、UNKNOWN分别留证，不能冒充送达；不拿不同review或attempt请求体互相比。
其中“同次相等”只证明传递，不能替代语义判据；完整B2-AC-10还须通过§10.2的材料完整和无泄漏检查。

### 9.3 R02冲突域与R04/R05效力定义

冲突单元是`(input_revision_id, adopted_ruleset_version, 同一目标, 同一业务条件)`。
在该冻结视图内，两条仍有效规范提出不可同时满足的要求，且没有适用优先/替代关系，才构成本例冲突。
adopted表示选入视图，不保证语义相容；发布接口不承担新增的语义预检。
旧任务冻结规则集2仍可能有冲突，新任务采用3可已解决；跨历史版本差异本身不自动构成冲突。
本阶段按introduced/removal版本与冻结视图确定效力，不新增日历生效窗口。

- supersede：引入新决定，同时仅从旧决定移除指定effective_scope；旧正文、其他切片、旧视图不改。
- withdraw：只移除指定切片，不生成替代规则或反向禁止，不删除原正文。
- 范围匹配：同维OR、跨维AND必须落在同一目标；缺维度保留scope_unresolved。
- 生效差集：base非match保留该结果；base=match且任一removal=match则no_match；
  无命中但有unresolved则仍未确定，其余才match。未知不能当false后继续采用旧规则。
- R04中创建保留、取消由新规则支配；R05中创建保留、取消无其他规范，因此诚实不足是预期结果。

相同定义已内嵌oracles.json的semantic_definitions，复核者不必靠记忆补齐。
来源为inputs.py的match_scope/match_effective_scope及decisions.py的views/adopt。
这类评审元规则不加入逐例业务source文件；逐例oracle/期望标签不得泄漏给模型。

### 9.4 结果多轴记录

result-record.template.json只是本地报告模板，不新增宿主API状态或数据库Schema。

| 轴 | 记录方式 |
| --- | --- |
| 服务执行与远端结果 | 原样保存status/job_status/error_code/remote_outcome/usage等既有值 |
| 证据 | NOT_COLLECTED / COMPLETE / INCOMPLETE，附真实缺口，不把采集缺页叫业务规则不足 |
| 工程工作流 | NOT_RUN / PASS / FAIL / UNDETERMINED |
| 模型语义判据 | NOT_RUN / PASS / FAIL / UNDETERMINED；受控替身阶段始终NOT_RUN |
| 业务判断 | 原样保留needs_decision / insufficient_evidence / no_deviation等报告判断 |

R05在证据完整时正确说明取消无有效规范，可以满足语义oracle；缺事件/报告则不能据此签通过。
缺采不抹掉已证实硬失败；未运行、执行失败、远端UNKNOWN、业务允许的未知分别保留。

### 9.5 demo与整体门禁

demo不增加五例语义样本，但B2-AC-07是当前完整B2离线工程门禁必需项。
失败或未完成时整体B2不能签完成；五例各自已有判据结果仍分别保留，不一并改成失败或剔除。
演示可支持共享编排/采集机制证据，不能替代R04/R05/H03等独有的业务条件。
若决定后移demo，须显式修订任务范围，不能静默跳过AC07。

### 9.6 阻塞、保留与重测

停止对应操作后，在结果清单blocking记录reason、受影响case/demo、phase、evidence_refs、
local_defect_reference、resume_conditions和attempt_history；无需创建通用工作流状态机或外部issue。
保留已冻结计划槽位和已有失败/未知/消耗，不删case美化分母；未批准真实批次不计算真实成功率。
阻塞前没执行的语义仍NOT_RUN；已证实失败保留FAIL，不能改成“待办”掩盖。

满足修复、版本、输入/oracle/profile及授权条件后，追加新尝试，旧证据不覆盖。
纯离线重跑只增加测试运行记录；判据纠错重评固定产物使用新eval_run；真实重跑的身份和额度按获准计划，
不得自动重抽到PASS。若需改src，先保留最小反例并另行界定修复范围，本执行单不自动授权。

### 已有机制引用与当前阶段

ExecutionProfile已有test/live字段，worker核对冻结模式与adapter；B1 require_test_runtime拒绝外部client、
非test配置及任何开启的选项（包括project_memory）。B2仍需按本单实现和测试，不能把声明当现成实现。
confirm是publish的分支，正式adoption在创建/修订事务内计算；publish/create/answer已有幂等，失败重试保留原逻辑请求体。
这些引用用于避免重复造机制，不额外新增live开关、审批平台、adopt接口或计费系统。
真实阶段的review/case/整批额度与未知预留继续留在真实试验准入卡，不在本轮实现计费机制。

### v0.2历史复核结果（保留）

已重新检查八份JSON、五例身份与判据集合、12条材料关联、文档链接与11项AC编号。五例业务criterion/禁止结论及材料正文与v0.1一致；仅新增六项评审约定。
复核冻结模板仍PENDING_INDEPENDENT_REVIEW/NOT_FROZEN，结果模板仍NOT_RUN；没有代替用户签收或生成真实运行快照。
src、B1及其他既有文件保持原内容，v0.1候选资料保留；三个B2实现文件未创建。本轮只有静态结构检查，没有运行产品API、模型或pytest。

## 10. 三处局部验收补强

### 10.1 H03：工程隔离与语义歧义独立判定

H03-3保留父criterion身份，新增两个独立子检查：
`H03-3.isolation`检查存储及实际输入的来源隔离；`H03-3.ambiguity`检查B能否认识版本归属未知。
两个结果分别保存，不用输出相似来推定污染。

| 观察 | 工程隔离 | 语义歧义判断 |
| --- | --- | --- |
| B完整输入无A答案，B仍无依据独立猜v1 | 可PASS | FAIL |
| B完整输入无A答案，B正确请求澄清 | 可PASS | 可PASS |
| A正控制/B完整输入证据缺失 | UNDETERMINED，不能宣称隔离正确 | 独立保留可判定结果；已有硬失败不抹掉 |
| 实际发现A局部答案被注入B | FAIL | 单独评估，不能因此把所有输出判定自动改成同一结果 |

该表是判定口径示例，不是真实模型结果；受控离线阶段semantic_verdict仍NOT_RUN。
B可以看到原业务材料中的v1/id等事实；检查A resolution/裁决的实际来源与注入链，
不能因B输出“v1”或与A文字相似，就认定跨review污染。

### 10.2 AC10：相等之外还要完整、无泄漏

在原test_each_input_adoption_matches_actual_delivered_payload内补三组断言，不新增AC编号或运行架构：

1. 一致性：按§9.2比同一次实际调用的完整payload，不能过滤字段制造命中。
2. 材料完整：按本次input/目标/效力状态，预先列明必需原文和元数据，再检查决定性父分析与固定复核实际收到。
   数据库和adapter同时漏了同一规则时，一致性可以PASS，完整性必须失败。
3. 输入无泄漏：oracle/逐criterion期望/预设判分标签、未触发答案脚本、其他review的局部裁决不能混入输入。
   A1合法提交的答案属于业务事实；不能把它误判为未触发脚本。

| 场景 | 必须核对的本次依据 |
| --- | --- |
| R02 | allow与deny两个有效规则全文及当前adoption/目标/版本；所需取消源码 |
| R03 | A/B各自input中的allow全文、同一正式决定及精确版本；不能只有名称/hash |
| R04新视图 | 创建保留joint_old，取消采用cancel_new；旧取消切片失效关系明确，源码可核对 |
| R05新视图 | 创建依据完整；取消有效规范为空有withdraw/scope证据，不要求不存在的新取消规范全文 |
| H03 | A1父分析/复核含完整原答案；B只有原歧义材料与本次依据，无A局部答案 |

探索首轮可尚未取得全部目标正文；产生决定性判断与固定复核时才按对应必需材料核对。
规则全文、adoption_records、rule_materials、resolutions等有现成构建接点，B2应取案例级实收证据，
不能只引用dynamic_context.py存在就签PASS。材料完整性也不证明模型正确理解，语义仍独立。

### 10.3 历史规则不应造成当前误报冲突

R04：旧joint规则全文因创建/历史审计可保留，但取消切片已supersede，不能与cancel_new并列为当前冲突。
Review C：deny已withdraw，不能继续充当当前取消规范或让C因该历史文本产生blocking rule_conflict。
可以描述历史曾有冲突；是否违规取决于当前目标/版本的效力和用途，不是禁止文本里出现“冲突”二字。

负控制写入R04现有criterion和demo的C阶段，复用原测试节点；不新增正式case数，
也不要求删除历史原文。R02的真正当前冲突与R04/C的非冲突分别验证。

### 10.4 版本差异与当前范围

在真实工作区逐文件比较v0.1/v0.2/v0.3：
v0.1→v0.2的原五例业务criterion保持一致；v0.2→v0.3有上述局部判定/证据增补，
不再宣称oracle文本与v0.1完全相同。所有原case/trial/sample、输入步骤、规范/源码材料保持不变（仅候选目录引用换版）。
打包附三版本候选资料、机器对照摘要及oracle unified diff，供独立复核，不依赖口头记录。
历史版本不计入当前五例分母，以v0.3 manifest为当前候选入口。

本次仅修订文档和候选判据，不创建三个B2实现文件，不改src/B1，不跑产品API、pytest或真实模型。
后续若启动实现，建议先R03最小复用，再验证R02/H03/ABC，最后R04/R05；该顺序不构成启动授权。

### v0.3本轮复核结果

已在真实工作区比较三版本候选文件，并生成SHA清单及oracle unified diff。v0.1→v0.2原业务criterion一致；v0.2→v0.3局部增补，H03-3文本拆分、R04/C负控制和AC10完整性新增，未宣称字面完全一致。
五例身份、11项AC、输入步骤/材料/人工答案和三个未来实现文件范围保持不变；八份JSON及引用检查通过，旧版本和B1/src未改。B2代码、产品API、pytest和模型均未运行，仍待独立复核/未冻结。
