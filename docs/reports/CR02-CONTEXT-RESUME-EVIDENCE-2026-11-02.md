# 上下文工程：简历表述与证据

日期：2026-11-02（Asia/Shanghai）。产品基线：`14209183929dd19a566803e04897d246efdc3cd8`。
状态：**工程版主/短表述及证据核对已完成，可使用；AC-10 未签整体 PASS。**
产品目录：`C:/Users/50469/specflow-h04-f03-20261023`。

## 可直接选用的表述

主版：

> 参与 SpecFlow Agent 的 AI 辅助开发，围绕契约审查冻结输入与执行配置，按轮构建上下文投影，以独立字段传递规则原文、内部复核反馈与人工答案；按字符预算装载观察并记录省略，在 Provider 边界保存实际请求和材料引用，支持事后核查。

短版：

> 参与实现契约审查上下文投影，支持输入冻结、反馈与人工答案分离、观察预算管理和实际请求核查。

这两版描述已有工程机制，不含未测收益、真实模型可靠性或个人独立主导主张。
项目中的代码与测试由 AI 协作生成/修复，用户已参与目标、范围和方案确认；
本轮不把这些记录升级为独立编码、生产负责或闭卷掌握的证明。
贡献部分沿用用户陈述与交接记录，不从代码存在推导个人独立主导；面试掌握程度未测。
两版的 Resume Status 均为 `Ready`，限于上述工程机制与参与范围，不代表业务语义验收完成。

“冻结”指 input revision 及其执行配置；每次模型请求仍按当时的观察、人工答案和内部反馈
构建投影。字符预算不是 Token 动态压缩，本轮没有实现摘要或滚动摘要。

## Claim 与现有证据

下表证据状态针对项目机制，个人贡献另按上节限定。核查方法：实现为 `inspected_source`；
既有门禁为 `inspected_report`；新增离线专项为本 Goal 前窗口实际执行的 `reproduced`，
本收口窗口只解析归档、核对正文与日志，没有重新执行测试。测试编号见下节日志定位。

| Claim | 实现与来源 | 测试、日志与实际请求 | 状态与边界 |
| --- | --- | --- | --- |
| C1 冻结输入与执行配置，按轮构建投影 | [freeze_input](../../src/specflow/contract_review/inputs.py#L47)，L133–151 保存输入、profile 及 hash；[claim](../../src/specflow/contract_review/execution.py#L113) 比对冻结配置；[build](../../src/specflow/contract_review/dynamic_context.py#L80) 逐请求构造 | T1、T2；三份归档的 `db_projections[*].input_hash/profile_hash` 绑定输入版本，请求正文见 C2/C3 | 已验证；`Validated` 限于离线程序。人工答案通过[新 input revision](../../src/specflow/contract_review/checkpoints.py#L235) 纳入，不是冻结整场会话 |
| C2 规则原文、人工答案与观察分开；按字符预算保留或省略 | [rule_materials/resolutions](../../src/specflow/contract_review/dynamic_context.py#L117)；[预算与省略](../../src/specflow/contract_review/dynamic_context.py#L191)；[mark_projected](../../src/specflow/contract_review/dynamic_context.py#L233) | T3–T6；[E01 归档](evidence/CR02-context-2026-11-02/E01-ordinary-tool-tail.json) 的请求索引 1/2：`messages[1].content` 解码后 `observations[0].body.text` 为完整 900 字符；E02 的 `resolutions[*].answer.text` 保留人工原文 | 已验证；`Validated` 限于所测装载/省略路径。旧规则尾部测试与新增普通工具观察变体分别记录，不据此声明任意长上下文均可容纳 |
| C3 内部反馈与人工答案独立传递、独立持久归属 | [内部 revision_feedback](../../src/specflow/contract_review/dynamic_runner.py#L201)；[人工答案入库](../../src/specflow/contract_review/checkpoints.py#L200)；[投影独立字段](../../src/specflow/contract_review/dynamic_context.py#L118) | T6、T7、N2、N3；[v1](evidence/CR02-context-2026-11-02/E02-human-v1-internal-feedback.json)/[v2](evidence/CR02-context-2026-11-02/E02-human-v2-internal-feedback.json) 索引 4/5 同时有独立 `revision_feedback` 和两条 `resolutions`；`db_resolutions` 各仅有两条准确人工答案 | 已验证；`Validated` 限于字段、送达与持久归属。不证明模型正确理解，也不把内部反馈作为人工授权 |
| C4 Provider 边界实际请求与材料引用可核查 | [model_call](../../src/specflow/contract_review/worker.py#L232) 在 L247 prepare 后预留；[RequestProjection](../../src/specflow/contract_review/dynamic_ledger.py#L129) 保存 payload/material_entries，L221 记录事件 | T8、N1–N3；三份 JSON 的 15 条 `wire_payloads` 与对应 `db_projections[*].payload` 逐条相等，完整保留 `messages` | 已验证；`Validated` 限于 OpenAIReviewAdapter + MockTransport 边界。材料身份/hash 不单独证明正文送达；真实模型正确使用未测 |
| C5 缺证防护的已实现部分（不进入主/短版的结果承诺） | [必需材料完整性](../../src/specflow/contract_review/dynamic_context.py#L93)、[超限硬失败](../../src/specflow/contract_review/dynamic_context.py#L199)、[gap 禁止 no_deviation](../../src/specflow/contract_review/report_validation.py#L296) | T5、T9–T12 支持部分程序边界；**没有**原 E03 完整场景的“实际请求＋最终目标级不足报告”归档 | 已验证仅指上述 guard；guard 为 `Implemented`，已跑边界为范围受限的 `Validated`。原 E03 仍为 `MISSING_EVIDENCE`，不能写“缺证时总能正确报不足” |

### 准确测试与日志定位

既有日志：[最终全库日志](C:/Users/50469/AppData/Local/Temp/specflow-impact-final-fixed-pytest-20261102-152722-485.log)。
下表行号已与原日志逐项核对，均为 `PASSED`；本轮复用而未重跑。
长参数化节点名保留在原日志，不在本报告重复展开前文填充字符。

| 编号 | 测试函数与参数范围 | 源码 | 原日志行 |
| --- | --- | --- | --- |
| T1 | `test_accepted_input_is_durable_and_replay_returns_original_response` | [test_intake.py](../../tests/contract_review/test_intake.py#L19) | 349 |
| T2 | `test_deployment_profile_drift_requires_explicit_selection`：same_request / changed_request / explicit_profile | [test_checkpoint_review_fixes.py](../../tests/contract_review/test_checkpoint_review_fixes.py#L24) | 8–10 |
| T3 | `test_critical_rule_tail_is_kept_in_full_and_catalog_is_not_a_read` | [test_dynamic_context.py](../../tests/contract_review/test_dynamic_context.py#L66) | 142 |
| T4 | `test_omitted_observation_is_explicit_and_cannot_claim_source_was_read` | [test_dynamic_context.py](../../tests/contract_review/test_dynamic_context.py#L76) | 143 |
| T5 | `test_mandatory_material_failure_is_not_summarized_away`：oversize / hash | [test_dynamic_context.py](../../tests/contract_review/test_dynamic_context.py#L100) | 144–145 |
| T6 | `test_full_human_answer_reaches_next_analysis_and_fixed_review`：4 个参数化节点 | [test_checkpoints.py](../../tests/contract_review/test_checkpoints.py#L552) | 49–52 |
| T7 | `test_revision_directive_is_preserved_in_both_model_roles` | [test_checkpoints.py](../../tests/contract_review/test_checkpoints.py#L770) | 65 |
| T8 | `test_http_adapter_wire_payload_equals_durable_projection` | [test_dynamic_workflow.py](../../tests/contract_review/test_dynamic_workflow.py#L678) | 237 |
| T9 | `test_mark_insufficient_keeps_related_work_not_ready`：ready / not_ready | [test_checkpoints.py](../../tests/contract_review/test_checkpoints.py#L598) | 55–56 |
| T10 | `test_reask_after_mark_insufficient_stops_as_protocol_failure`：False / True | [test_checkpoints.py](../../tests/contract_review/test_checkpoints.py#L577) | 53–54 |
| T11 | `test_gap_projection_is_deterministic_and_cannot_hide_behind_covered` | [test_contract_classification.py](../../tests/contract_review/test_contract_classification.py#L133) | 79 |
| T12 | `test_rejects_structural_and_ownership_counterexamples`：unread_source | [test_contract_classification.py](../../tests/contract_review/test_contract_classification.py) | 75 |

T3–T8 合计 10 个既有通过节点；T9–T12 另有 6 个边界节点，不替代原 E03 场景。
尤其不能将源码中的 gap guard 或 unread_source 反例写成已独立运行了
`unsupported → positive` 专门负例；当前没有识别到该专门运行证据。

新增专项的实际运行记录为 [pytest-probes-02.log](evidence/CR02-context-2026-11-02/pytest-probes-02.log)：

| 编号 | TEMP 程序用例 | 归档夹具定位 | 日志行 |
| --- | --- | --- | --- |
| N1 | `test_E01_ordinary_tool_observation_tail_reaches_actual_wire` | [test_context_evidence_probe.py.txt](evidence/CR02-context-2026-11-02/test_context_evidence_probe.py.txt#L56) | 6 |
| N2 | `test_E02_human_resolutions_and_internal_feedback_coexist_on_wire[v1]` | [同一夹具](evidence/CR02-context-2026-11-02/test_context_evidence_probe.py.txt#L133) | 7 |
| N3 | `test_E02_human_resolutions_and_internal_feedback_coexist_on_wire[v2]` | [同一夹具](evidence/CR02-context-2026-11-02/test_context_evidence_probe.py.txt#L133) | 8 |

最终 **3 passed / 0 failed / 0 skipped / 0 warnings，5.16 秒，exit 0**。
15 是捕获的模型请求 JSON 数，27 是三个夹具内的细检查数；均不是独立语义 case 数或成功率分母。

## 原验收与专项口径

规格：[v0.2.2](D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/SPEC_FLOW_CONTRACT_MAINTENANCE_DRAFT_v0.2.2.md)：
C§6.5 为 L1315–1323，AC-10 为 L3083，E01/E02/E03 为 L3416–3418，映射为 L3442；
结合同目录[修订说明](D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/V0_2_2_REVISION_AND_CHECKS_2026-10-30.md) §6（L69 起）勘误，不恢复未选范围。
原规格的程序与语义要求分栏核对，不用新程序夹具冒充已运行的 CR02-E01/02/03 正式真实 trial。

| 原案例 | 必须核对 | 程序结果 | 真实模型语义 |
| --- | --- | --- | --- |
| E01 | 普通前序内容 500 字符后的关键条件进入实际判断请求；与必保留规则尾部区分 | **PASS，仅普通工具观察关联变体 N1**：`read_source` 正文 900 字符，关键 `API v2: only queued jobs may cancel` 在正文自身 offset 841（0-based，第 842 字符），完整进入索引 1 analysis / 2 review | **NOT_RUN**；正式 CR02-E01 trial 未跑，脚本完成状态不证明判断与 oracle 一致 |
| E02 | 内部 revision_feedback 与不同人工 resolution 各自投影，身份/持久归属分开 | **PASS，关联变体 N2/N3**：人工 v1/v2 各 6 条 wire，索引 4 analysis / 5 review 同时包含两条准确人工答案和不同的内部反馈；DB 各两条 resolutions 无内部反馈污染 | **NOT_RUN**；正式 CR02-E02 trial 未跑，不证明模型正确使用或识别授权身份 |
| E03 | 必需材料无法取得时明确不足，不确定宣称 no_deviation | **缺证（MISSING_EVIDENCE）**：T5 的 oversize → BUDGET_EXHAUSTED、hash mismatch → SOURCE_INTEGRITY_FAILED，以及 T9–T12 仅为关联边界 PASS；缺原场景实际请求及最终目标级不足报告 | **NOT_RUN**；正式 CR02-E03 trial 未跑，硬失败不等于已产出业务缺口报告 |

C§6.5/AC-10 当前结论为 **PARTIAL_PROGRAM_EVIDENCE**。没有可复现产品缺陷的证据，
本轮没有因此扩展实现；也不以缺证当作产品失败。原 AC-10 的程序＋语义整体不能签 PASS。

证据层次依次为：材料存在 → 被读取/选中 → material_entries 登记 → 实际 payload.messages
含对应正文 → 真实模型正确使用。前一层不自动证明后一层。工具/子结果的有界程序验证与
人工答案送达验证均不签发真实语义 PASS。

## 归档与复查

仓库内保留以下 9 份原始证据，归档 JSON 的 TEMP 路径保留生成时来源；
日后检查请求正文优先使用下列仓库文件，不依赖 TEMP 中的同名副本：

- [context-evidence-summary.json](evidence/CR02-context-2026-11-02/context-evidence-summary.json)：状态、口径、运行环境及精确命令。
- [E01-ordinary-tool-tail.json](evidence/CR02-context-2026-11-02/E01-ordinary-tool-tail.json)：原正文、3 条完整 wire payload/messages 和 DB projections。
- [E02-human-v1-internal-feedback.json](evidence/CR02-context-2026-11-02/E02-human-v1-internal-feedback.json) 与 [E02-human-v2-internal-feedback.json](evidence/CR02-context-2026-11-02/E02-human-v2-internal-feedback.json)：各 6 条 wire、DB projections、原人工 resolutions 及独立反馈。
- [run-metadata.json](evidence/CR02-context-2026-11-02/run-metadata.json)：执行身份与 MockTransport 边界。
- [pytest-probes-02.log](evidence/CR02-context-2026-11-02/pytest-probes-02.log)：最终 3 项通过记录。
- [test_context_evidence_probe.py.txt](evidence/CR02-context-2026-11-02/test_context_evidence_probe.py.txt)、[conftest.py.txt](evidence/CR02-context-2026-11-02/conftest.py.txt)、[run-probes.py.txt](evidence/CR02-context-2026-11-02/run-probes.py.txt)：原 TEMP 夹具、阻断真实 HTTP 的 autouse fixture 和启动脚本，以文本归档，不是新增产品代码。

请求正文定位均为 `wire_payloads[i].messages[1].content`（JSON 字符串解码后）：
E01 检查 `observations[0].body.text`；E02 检查 `resolutions[*].answer.text` 与
`revision_feedback.revision_feedback`，并与顶层原人工文本、内部反馈及 `db_resolutions` 比对。
全部 15 条 wire 与 DB payload 逐条相等，归档内 27 个细检查均为 true；本窗口已重新解析核对。
静态复查通过 46 个文件链接（含所用行号锚点）与 5 份 JSON 解析。
默认 `git diff --cached --check` 仅报告原归档夹具 `test_context_evidence_probe.py.txt:180`
的末尾空行；为保留原件不改写该夹具，报告正文的空白检查单独通过。此提示不是 pytest warning。

原执行目录为 `C:/Users/50469/AppData/Local/Temp/specflow-context-evidence-20261102-160602-310`。
其中 `reused-prior-program-evidence.json` 的原 10 项及 E03 关联 6 项记录，
已与既有日志的精确行逐项核对；可直接按本报告 T3–T12 的函数、参数及行号复查。
首轮 `pytest-probes-01.log` 的 3 个失败是 TEMP 夹具的 CRLF 比较与 profile/provider timeout
不匹配，修正后得到上述最终结果；原日志保留，不作为产品缺陷或语义失败统计。

如后续需要复跑，将三个 `.py.txt` 恢复为新 TEMP 目录中的同名 `.py`，
按 summary 的 `exact_execution` 配置执行；产品 checkout 仍显式作为 workdir，
`PYTHONPATH` 需有产品 `src` 和归档记录的构建依赖，保持禁止真实 HTTP。
不能在产品源码目录直接运行归档生成物，也不能将旧 profile/收费窗口视为新授权。
本轮已有最终通过记录，无需复跑。

## 已有门禁与本轮交付范围

复用上轮最终日志：
`C:/Users/50469/AppData/Local/Temp/specflow-impact-final-fixed-pytest-20261102-152722-485.log`。
原日志 L1643 为全库 **1617 passed / 3 已有 skipped / 2 已有 warnings**，
其中 `tests/contract_review/` 的 PASSED 节点逐行计数为 **505**。
这两个数字是工程测试总数，不是本轮上下文专项样本数或真实模型成功率。

本 Goal 只补上述离线专项并导出实际请求正文，收口窗口只修改本报告；
产品 Python 源码、既有 tests、benchmarks 均未因本 Goal 改动。
交付限定为本报告与 9 份归档的一次本地聚焦提交，排除并保留用户 `CR02-CURRENT.md` 修改。
复用既有门禁，不重跑全库/模块，不重开已关闭审查，不推送。
没有运行真实业务模型、读取凭据/Holdout、使用过期费用授权或恢复旧 automation。

## 强化版尚缺的证据

要写“模型正确处理长上下文”“可靠性提升”或具体收益，仍需先冻结 E01/02/03 的业务材料与
独立 oracle，再单独批准模型/profile、trial 身份及数量、总费用/调用/输出上限、上海执行窗口。
需保留实际请求、结果、失败/未知及分母，并做预先确定的可比验证。
当前不为强化版承诺完成时间，也不据此推迟上面的工程版表述。

F01 两次真实失败仍保留，v3 未跑；没有证据将其归因为摘要丢失。
本轮不实现摘要、滚动摘要、Token 动态压缩、候选发现扩展、恢复或条件写入。
