# F01 v3 下一次执行与验收卡

日期：2026-11-02（Asia/Shanghai）。状态：**离线准备完成；新真实试验未授权、未执行**。
产品 checkout：`C:/Users/50469/specflow-h04-f03-20261023`。

本卡供下一次试验前审阅，沿用原 F01 人工清单先导。先确认本卡判据及新试次参数，再冻结
可执行入口；不以本卡创建 trial、调用业务模型或关闭语义验收。候选影响发现仍可独立后续推进，
不作为这个已有明确人工范围案例的前置开发任务。

## 1. 当前证据与待验证问题

v3 代码基线为 `ee043085027fe16242c2e7bbb2aac6586b17dc86`，仅修改
`scripts/contract_review/run_f01_pilot.py` 和 `tests/contract_review/test_f01_pilot.py`。
新增内容是分析提示中的引用字段域说明及离线回归；原采用、投影、输入归属和适用性校验保留。
该提交记录 80 项聚焦验证和已关闭的 Astra 独立审查。全量日志确认
**1566 passed / 3 skipped / 2 warnings**；Ruff 280 文件通过见提交说明。
本卡整理未重跑这些门禁，也未重开该审查。

| 真实尝试 | profile | 已观察到的执行 | 结果及失败边界 |
| --- | --- | --- | --- |
| TR02-F01-COMMON-01 | pilot-f01-deepseek-flash-v1 | 2 次分析；工具 0；固定复核 0 | 未投影正文的 SourceRef 被拒；一次纠错后仍引用，`ACTION_PROTOCOL_ERROR`，无报告 |
| TR02-F01-COMMON-02 | pilot-f01-deepseek-flash-v2 | 4 次分析；2 次 read_source；固定复核 0 | 正文已投影，候选指出两处漂移；把 observation_id 填入外部核验字段，纠错后仍非法，`ACTION_PROTOCOL_ERROR`，无报告 |

这是同一公开已知回归案例的两次真实尝试，均保留为失败，不能算作两个独立 case 或 Holdout。
第二次被拒的候选提供了部分业务判断证据，尚未形成正式交付。v3 的新真实尝试数仍为 0；
离线通过尚不能证明真实模型会按新增说明使用引用。没有证据将前两次失败归因于摘要丢失。

## 2. 固定输入与运行配置

| 项目 | 固定值或待确认值 |
| --- | --- |
| case / sample | CR02-F01 / SP02-F01-COMMON-01 |
| 原材料身份 | source_trial_id = TR02-F01-COMMON-01 |
| 新执行身份 | **候选** TR02-F01-COMMON-03；尚未创建，执行前确认未占用 |
| 材料来源提交 | ef2c53af26f0a02f61b4e7c8fa07e1d767a17029 |
| 执行实现基线 | ee043085027fe16242c2e7bbb2aac6586b17dc86；若后续获准更新 guard，另记实际执行 HEAD 与差异 |
| profile | pilot-f01-deepseek-flash-v3 |
| 模型及通道提案 | DeepSeek 官方 `https://api.deepseek.com`；请求模型 `deepseek-v4-flash`，新授权时确认 |
| 协议 | contract-review-action.v2.1 / contract-review-report-payload.v2.1 |
| 行为开关 | 动态只读取证；delegate / project_memory / replay / write 均为 false；ruleset_usage.mode = none |
| 正式范围 | v2，POST /exports；文档与示例各一个 response_field check |

runner 从固定材料提交读取以下文件，复制到 checkout 外的全新隔离案例仓库并形成快照。
模型依据本次实际投影正文判断，不依据文件名、目录条目或本卡答案判断。

| 案例内路径 | 固定 fixture | 用途与已知内容 |
| --- | --- | --- |
| contracts/v2.json | contract-v2.json | 采用契约：POST /exports 的 201 响应字段要求 job_id |
| src/api.py | api-correct.py | 实现对照：返回 job_id；保留实现，非正式 target |
| docs/api.md | docs-id.md | 正式 target：标为 v2，响应示例仍使用 id |
| examples/client.py | example-id.py | 正式 target：标为 v2，仍读取 response["id"] |

Oracle 沿用固定提交 `benchmarks/contract_review/oracles.json` 的 F01 条目：两处漂移、
文档和示例改用 job_id、保留正确实现；不声称已修改或运行测试。本卡补明已有证据边界：
契约要求 job_id，并未明文禁止兼容 id，报告不得自行推导“禁止返回 id”。
Oracle 由 Codex 按规格整理，其来源不构成独立专家一致性证据。执行前由用户审阅判据；
`oracles.json`、`human-scripts.json`、本卡和两次历史答案均不加入模型 source groups 或提示。

## 3. v3 必须验证的行为

1. **先取得正文再引用。** 目录 source_id 可用于工具 arguments 选源；不证明正文已读。
   起始理由允许 `reason.evidence_refs=[]`。工具完成后，须等正文/观察进入后续模型请求，
   才能引用对应内容；selector 不超出实际投影片段。不要求固定读取顺序或固定工具次数。
2. **引用按字段身份域填写。** `reason.evidence_refs` 使用带 kind 的 MaterialRef；
   `source_refs` 使用 source_id 与 selector；`findings[].observation_refs` 和
   `check_results[].observation_refs` 使用已投影 observation_id。
   `rule_refs` / `rule_uses[].adoption_id` 属于规则采用身份。
3. **外部核验字段保留真实语义。** `findings[].verification_evidence_refs` 和
   `acceptance_items[].evidence_refs` 仅接受当前 input 已采用、已投影且满足适用性的外部
   evidence_id。本次不导入或采用外部核验记录，所以这两个字段为 `[]`。
   不把工具观察、规则采用或来源身份升级为外部证据，不为了填字段要求外部执行。
4. **反馈能修正错误引用。** 若实际出现 `Referenced body was not projected`，检查后续动作
   是否移除未读引用并补足所需正文；若出现 `Unknown adopted evidence`，检查两个外部字段
   是否移除错误身份。无错误反馈时直接通过本项，不为演示纠错故意注入错误。
5. **完成业务交接。** 正式报告覆盖两个 target/check，判断两处字段漂移，建议在文档响应和
   示例读取处使用 job_id；实现只作对照。交接列明对应工作项、修改范围、依赖/就绪状态、
   验收步骤和预期证据。所有业务 `execution_status` 保持 `NOT_RUN`。

离线四个跨域负例覆盖“观察/规则采用 ID × 两个外部字段”。外部绑定正例只是 validator
层的受控模拟，没有真实导入或真实模型成功证据；本轮不把该正例扩为新的真实验证目标。

## 4. 执行顺序与停止条件

1. 执行前完成第 7 节的新授权及 guard 更新门禁。核对 checkout 状态，保留用户维护的
   `docs/reports/CR02-CURRENT.md`，记录实际 HEAD、profile 与材料提交。
2. 只创建获准的一个新 trial，使用全新 checkout 外输出目录、独立案例仓库/数据库。
   新 trial_id 用作新请求的幂等身份；原 case/sample/source_trial 身份保留。
3. 经现有 runner、CreateReview API 与 worker 执行一次完整逻辑任务，包含正常协议纠错及
   固定最终复核。Reviewer 不调用工具、不委派；不调用 retry/revision 接口另开尝试。
4. 达到终态或监督超时后收集证据，并记录本地服务清理结果。核对实际请求、响应、引用、
   费用账与正式报告，再按第 5 节判定。保留错误、被拒候选、未知 usage 与未结算预留。

窗口外、费用预留不足、模型身份不符、依赖失败、未知 usage 等，均沿现有 guard 停止。
费用账保留未结算占用，不凭估计释放；不自动重跑或换模型。系统允许的一次协议纠错、
固定复核及有限返工属于同一次获准逻辑任务，不能借此扩大物理模型调用上限。
具体原有限制以冻结 profile 和 guard 为准，本卡不新增纠错额度。

## 5. 成功、失败与证据不足

**F01 本次 PASS** 须同时满足以下四项，由运行后证据复核登记，不能由退出码或
`run.json.status=OBSERVED` 代替：

- 有宿主接受的正式报告 JSON/Markdown，可追溯到候选及固定复核的接受结果；两个 target/check
  均完成所需检查，无影响本例判断的证据缺口。`completed_degraded` 须审查具体缺口，不自动通过。
  按原 F01 oracle 核对四份 required_source_paths 的正文送达；未读实现不能支持“实现正确”的断言。
- 两处漂移及修改方向正确，正确实现保留；没有把要求 job_id 解释成禁止兼容 id，没有把
  其他接口、取消行为或实现文件扩大为正式修改目标。工作项与验收内容可供后续执行。
- 使用的引用都有当时实际请求投影支持；无外部核验记录时两个外部字段为空，执行状态为
  NOT_RUN。固定复核 accept 只表示报告被接受，不代表测试或修改已经执行。
- 请求、响应、报告、费用和清理证据齐全；模型/通道、调用次数与费用处于新授权内。

有完整证据但协议失败、缺少正式报告、漏掉任一漂移、方向错误或虚构执行，登记对应失败；
候选内容部分正确不改为 PASS。模型未发生任何物理调用的前置拦截登记
`BLOCKED_BEFORE_DISPATCH / NOT_RUN`，不冒记为已跑成功或失败。
已经发生调用而遇到超时、用量/远端结果未知或证据缺失，保留已消耗尝试并登记具体
`UNKNOWN` / `NOT_ASSESSABLE`，不从统计记录移除、不自动续跑。

无论下一次结果如何，两次旧失败均保留。同一案例重复尝试只用于观察修复后行为；
单次通过不能证明稳定成功率、Holdout 泛化、上下文专项、记忆收益或完整方案验收。

## 6. 必须保留的实际请求与引用证据

优先复用现有文件和事件，不新增审计系统。下表均位于该试次全新输出目录。

| 载体 | 保留及复核内容 |
| --- | --- |
| run.json / frozen-request.json / accepted.json | case/sample/新旧 trial、材料与实现提交、工作区状态、profile、提交请求、review/input/job 身份、受理时间 |
| review-evidence.json 的 request_projected 事件 | projection_id、logical_call_id、input_hash、profile_hash、projection_hash；完整 payload.messages 和 material_entries 正文、source_ref、范围、保留/省略情况 |
| trial-ledger.jsonl | reserved_before_adapter_http 的实际 wire payload；http_transport_entered；原始响应模型身份、adapter_result、usage_accounted、未结算预留；按 wire 内容核对宿主模型请求投影 |
| 同一 review 的完整事件 | 只读工具参数和实际观察正文、observation_id、后续哪轮请求投影该观察；action_proposed、接受/拒绝、协议反馈、固定复核/返工、最终保存报告的关系 |
| 正式报告与 criteria-review.json | 报告 JSON/Markdown 原文；逐项判定与对应事件/引用位置；静态判断、运行核验状态分别记录，复核文件不冒充正式报告或用户验收 |
| reviews.sqlite / case-repo / cleanup.json | 原始持久记录与固定材料；本地进程是否退出、退出码、强制停止及清理耗时 |

“实际引用成立”须能沿 **模型动作字段 → 当时可用的正文/观察身份 → 模型请求中的实际正文**
逐项核对。仅有 hash、目录项、工具已完成、最后一轮看到正文，均不能倒推更早一轮已读。
tool 的 request_projected 事件不是模型 HTTP；投影总数不能直接当作付费调用数。
不得改写模型原始输出以修正引用。保留原始本地证据，不导出凭据或认证头。

## 7. 新真实运行尚缺的授权参数

当前 guard 的有效窗口写死为 **2026-11-01 18:00 ≤ 上海时间 < 2026-11-02 00:00**，
已过期。CLI 只有 `--output`、`--trial-id`、`--run`，没有新时间窗口/预算参数；
因此新的口头授权本身不会使现有脚本可运行。本轮不修改 guard，也不提供可直接运行的旧命令。

下一次至少需要用户明确以下内容；未确认值不得自动补为授权：

- **试次与范围**：确认一个新执行身份（候选 TR02-F01-COMMON-03）、固定 F01 材料与两目标、
  profile v3、本卡判据；允许同一次逻辑任务内的原有纠错与固定复核，不自动再开试次。
- **模型与认证通道**：确认 DeepSeek Flash 请求模型、官方通道，继续使用已配置认证；
  不读取/打印密钥，不调用 launcher EmitEnv/Verify，不解密 profiles，不作收费探针。
- **费用及硬上限**：新的本试次总 CNY 上限、物理模型调用上限和每调用输出上限。
  可供审阅的沿用提案为 CNY 2 / 最多 12 次 / 每次最多 8000 输出 Token，当前未获新授权。
- **新执行窗口**：明确上海日期、开始及截止时间，窗口结束不继续派发。
- **必要控制改动**：允许仅为新获准窗口/价格依据更新试验 guard 及必要测试；涉及新的代码
  改动时使用 gpt-6-astra / xhigh 独立审查，完成相应离线验证后才能派发。

现有 guard 以 1,048,576 输入 Token 保守上界和每次 8000 输出上限预留，旧价格常量得到
首预留 CNY 1.080576；这是代码内 2026-11-01 依据，**不是对新窗口实时价格的确认**。
执行前须以官方公开资料重新核对模型身份/别名、计价时段与费率，记录依据并确保硬预留覆盖。
不以字符数、近似 Token 或旧试次实际低费用替换该上界；预算不是已承诺能跑满 12 次。
新预算、模型、价格或控制改动若超出现有约束，另列具体差异，不在授权后暗中扩大。

授权模板（仅供用户以后填写，本轮不请求开跑）：

> 批准 F01 新试次 ___，固定材料/两目标及 profile v3，采用本卡验收判据；
> 模型/通道 ___；本试次总费用 ≤ CNY ___，物理模型调用 ≤ ___，每次输出 ≤ ___；
> 上海时间 ___ 至 ___；允许上述必要 guard/测试调整，经 Astra xhigh 独立审查及离线验证后
> 执行一次，保留失败/未知及费用占用，不自动追加试次。

## 8. 证据入口与本轮交付边界

- 当前实现：[runner](../../scripts/contract_review/run_f01_pilot.py)、[guard](../../scripts/contract_review/f01_trial_guard.py)、[离线回归](../../tests/contract_review/test_f01_pilot.py)。
- 第一次原始证据：`C:/Users/50469/AppData/Local/Temp/specflow-f01-deepseek-live-20261101-CNY2-001`。
- 第二次原始证据：`C:/Users/50469/AppData/Local/Temp/specflow-f01-deepseek-live-20261101-CNY2-trial02-001`。
- 最终全量日志：`C:/Users/50469/AppData/Local/Temp/specflow-f01-reference-domains-final-pytest-20261102.log`。
- 计划依据：`D:/Downloads/agent学习/AI_HANDOFF/2026-10-29-GPT讨论交接/SPEC_FLOW_PLAN_UPDATE_v0.2.3_2026-11-01.md` §4、§5、§7；原规格及修订仍按该入口引用。

本轮只新增本卡，不修改 `CR02-CURRENT.md`、产品代码、测试或 guard，不启动真实试验，
不恢复 f01-18 automation。TASK-IMPACT-01、TASK-08、TASK-W01—03、完整 TASK-09 及
上下文 C§6.5 / AC-10 / E01/E02、记忆专项继续保留原范围和待验收状态。
